"""Authentication: dev-bypass for local + Auth0/Clerk JWT verification for prod.

Dev mode (DEV_AUTH_BYPASS=true): the API trusts the X-Dev-User-Id header from
the mobile app and auto-provisions a User row. Convenient — never enabled in
production by config.py's startup check.

Prod mode (DEV_AUTH_BYPASS=false): every request needs a Bearer JWT signed by
the configured Auth0/Clerk tenant. We:
  1. Fetch the tenant's JWKS once and cache it for an hour.
  2. Verify signature, audience, issuer, and expiry on each request.
  3. Map the JWT 'sub' to a stable User row, creating it on first sign-in.

This keeps the protocol the same regardless of provider — Auth0, Clerk, Cognito,
or any other JWKS-publishing OIDC issuer will work as long as AUTH_JWKS_URL,
AUTH_ISSUER, and AUTH_AUDIENCE are configured.
"""
from __future__ import annotations

import time
import uuid
from typing import Annotated, Any

import httpx
from fastapi import Depends, Header, HTTPException, status
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_db
from app.models.users import User, UserRole

# JWKS cache: maps the JWKS URL to (keys, fetched_at_epoch). One JWKS per
# process is fine — rotation typically happens monthly and we refresh on miss.
_JWKS_CACHE: dict[str, tuple[dict[str, Any], float]] = {}
_JWKS_TTL_SECONDS = 3600


async def _get_jwks(jwks_url: str) -> dict[str, Any]:
    cached = _JWKS_CACHE.get(jwks_url)
    if cached and (time.time() - cached[1]) < _JWKS_TTL_SECONDS:
        return cached[0]
    async with httpx.AsyncClient(timeout=10.0) as c:
        resp = await c.get(jwks_url)
        resp.raise_for_status()
        jwks: dict[str, Any] = resp.json()
    _JWKS_CACHE[jwks_url] = (jwks, time.time())
    return jwks


def _key_for_kid(jwks: dict[str, Any], kid: str) -> dict[str, Any] | None:
    for k in jwks.get("keys", []):
        if k.get("kid") == kid:
            assert isinstance(k, dict)
            return k
    return None


async def _verify_jwt(token: str) -> dict[str, Any]:
    settings = get_settings()
    if not settings.auth_jwks_url or not settings.auth_issuer:
        raise HTTPException(
            status.HTTP_501_NOT_IMPLEMENTED,
            "AUTH_JWKS_URL and AUTH_ISSUER must be set for production auth.",
        )

    try:
        unverified_header = jwt.get_unverified_header(token)
    except JWTError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "malformed token") from exc

    kid = unverified_header.get("kid")
    if not kid:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "token missing kid")

    jwks = await _get_jwks(settings.auth_jwks_url)
    key = _key_for_kid(jwks, kid)
    if not key:
        # Force a refresh in case the tenant rotated keys.
        _JWKS_CACHE.pop(settings.auth_jwks_url, None)
        jwks = await _get_jwks(settings.auth_jwks_url)
        key = _key_for_kid(jwks, kid)
        if not key:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "unknown signing key")

    try:
        claims: dict[str, Any] = jwt.decode(
            token,
            key,
            algorithms=[unverified_header.get("alg", "RS256")],
            audience=settings.auth_audience or None,
            issuer=settings.auth_issuer,
        )
    except JWTError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"invalid token: {exc}") from exc
    return claims


async def _user_from_claims(db: AsyncSession, claims: dict[str, Any]) -> User:
    """Provision or return the User row keyed off the JWT 'sub'."""
    sub = claims.get("sub")
    if not sub:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "token missing sub")

    existing = (
        await db.execute(select(User).where(User.auth_provider_id == sub))
    ).scalar_one_or_none()
    if existing:
        return existing

    # First sign-in: create the row from claims. We require an email — most OIDC
    # providers (Auth0, Clerk, Cognito) include it by default.
    email = claims.get("email")
    if not email:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "id token must include 'email' claim"
        )

    # If an account already exists with this email (e.g. user re-signed up via
    # a different SSO provider), link instead of duplicating.
    by_email = (
        await db.execute(select(User).where(User.email == email))
    ).scalar_one_or_none()
    if by_email:
        by_email.auth_provider_id = sub
        await db.commit()
        await db.refresh(by_email)
        return by_email

    display_name = (
        claims.get("name")
        or claims.get("nickname")
        or claims.get("given_name")
        or email.split("@")[0]
    )
    user = User(
        id=uuid.uuid4(),
        email=email,
        auth_provider_id=sub,
        role=UserRole.guardian,
        display_name=display_name,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def _get_or_create_dev_user(db: AsyncSession, dev_user_id: str | None) -> User:
    if dev_user_id:
        try:
            uid = uuid.UUID(dev_user_id)
        except ValueError as e:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid X-Dev-User-Id") from e
        existing = (await db.execute(select(User).where(User.id == uid))).scalar_one_or_none()
        if existing:
            return existing

    email = f"dev+{(dev_user_id or 'default')}@virtual-stylist.local"
    existing = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if existing:
        return existing

    user = User(
        id=uuid.UUID(dev_user_id) if dev_user_id else uuid.uuid4(),
        email=email,
        role=UserRole.guardian,
        display_name="Dev User",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def _set_rls_user_id(db: AsyncSession, user_id: uuid.UUID) -> None:
    """Set the current user id for Postgres Row-Level Security policies.

    `SET LOCAL` is scoped to the current transaction, so subsequent queries on
    this session see the value. Safe no-op on databases without the policies
    (the setting is just an unused custom GUC).

    Note: SET LOCAL does NOT accept bind parameters, so we interpolate the
    UUID directly. SQL injection is impossible because `user_id` is a typed
    uuid.UUID — its string form is constrained to hex + dashes.
    """
    from sqlalchemy import text

    # Re-stringify via UUID to defensively reject any non-UUID input.
    safe_uid = str(uuid.UUID(str(user_id)))
    await db.execute(text(f"SET LOCAL app.current_user_id = '{safe_uid}'"))


async def get_current_user(
    db: Annotated[AsyncSession, Depends(get_db)],
    authorization: Annotated[str | None, Header()] = None,
    x_dev_user_id: Annotated[str | None, Header()] = None,
) -> User:
    """Resolve the current user, preferring real Auth0 tokens over the dev header.

    Precedence:
      1. If a Bearer token is present AND the issuer is configured, verify it.
         This wins even when DEV_AUTH_BYPASS=true, so a mobile build that's
         already migrated to Auth0 doesn't accidentally fall through to dev
         provisioning.
      2. Else, if DEV_AUTH_BYPASS=true, trust X-Dev-User-Id.
      3. Else, 401.
    """
    settings = get_settings()

    has_bearer = bool(
        authorization and authorization.lower().startswith("bearer ")
    )
    issuer_configured = bool(settings.auth_jwks_url and settings.auth_issuer)

    if has_bearer and issuer_configured:
        assert authorization is not None
        token = authorization.split(" ", 1)[1].strip()
        claims = await _verify_jwt(token)
        user = await _user_from_claims(db, claims)
        await _set_rls_user_id(db, user.id)
        return user

    if settings.dev_auth_bypass:
        user = await _get_or_create_dev_user(db, x_dev_user_id)
        await _set_rls_user_id(db, user.id)
        return user

    if not has_bearer:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing bearer token")
    # Bearer present but issuer not configured — config error, not user error.
    raise HTTPException(
        status.HTTP_501_NOT_IMPLEMENTED, "AUTH_JWKS_URL / AUTH_ISSUER not set"
    )


CurrentUser = Annotated[User, Depends(get_current_user)]
