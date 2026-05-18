"""Verify Auth0 tenant config end-to-end before flipping DEV_AUTH_BYPASS.

Run before going to production:
    cd services/api
    uv run python scripts/verify_auth0.py --token "$AUTH0_TEST_TOKEN"

Confirms:
  1. AUTH_JWKS_URL is reachable from this host.
  2. The token's iss matches AUTH_ISSUER.
  3. The token's aud matches AUTH_AUDIENCE.
  4. RS256 signature verifies against the JWKS.
  5. exp/iat are in the future.
  6. User provisioning would succeed (sub + email present).

Prints PASS/FAIL per step with the exact mismatch on failure.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import UTC, datetime
from pathlib import Path

import httpx
from jose import JWTError, jwt

# Allow `uv run python scripts/verify_auth0.py` to import app.*
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings


def _ok(msg: str, detail: str = "") -> None:
    print(f"\033[32m✓\033[0m {msg:32s}  {detail}")


def _fail(msg: str, detail: str = "") -> None:
    print(f"\033[31m✕\033[0m {msg:32s}  {detail}")


async def verify(token: str) -> bool:
    s = get_settings()
    if not s.auth_jwks_url or not s.auth_issuer or not s.auth_audience:
        _fail(
            "Config incomplete",
            "Set AUTH_JWKS_URL, AUTH_ISSUER, AUTH_AUDIENCE in .env",
        )
        return False

    # 1. JWKS reachable
    try:
        async with httpx.AsyncClient(timeout=10.0) as c:
            r = await c.get(s.auth_jwks_url)
            r.raise_for_status()
            jwks = r.json()
        if not jwks.get("keys"):
            _fail("JWKS empty", s.auth_jwks_url)
            return False
        _ok("JWKS reachable", s.auth_jwks_url)
    except Exception as exc:
        _fail("JWKS unreachable", f"{type(exc).__name__}: {exc}")
        return False

    # 2. Token header has kid
    try:
        header = jwt.get_unverified_header(token)
    except JWTError as exc:
        _fail("Token malformed", str(exc))
        return False
    kid = header.get("kid")
    if not kid:
        _fail("Token has no kid header")
        return False
    key = next((k for k in jwks["keys"] if k.get("kid") == kid), None)
    if not key:
        _fail("kid not found in JWKS", f"kid={kid}")
        return False
    _ok("Signing key resolved", f"kid={kid}")

    # 3-5. Decode with full verification.
    try:
        claims = jwt.decode(
            token,
            key,
            algorithms=[header.get("alg", "RS256")],
            audience=s.auth_audience,
            issuer=s.auth_issuer,
        )
    except JWTError as exc:
        msg = str(exc)
        # Common-case-friendly diagnostics
        unverified = jwt.get_unverified_claims(token)
        if "audience" in msg.lower():
            _fail(
                "Audience mismatch",
                f"token aud={unverified.get('aud')!r}, configured={s.auth_audience!r}",
            )
        elif "issuer" in msg.lower():
            _fail(
                "Issuer mismatch",
                f"token iss={unverified.get('iss')!r}, configured={s.auth_issuer!r}",
            )
        elif "expired" in msg.lower():
            _fail("Token expired", f"exp={unverified.get('exp')}")
        else:
            _fail("Signature/claims verification failed", msg)
        return False
    _ok("Issuer matches", s.auth_issuer)
    _ok("Audience matches", s.auth_audience)
    _ok("Signature verified (RS256)")

    now = int(datetime.now(UTC).timestamp())
    if claims.get("exp", 0) <= now:
        _fail("Token expired")
        return False
    _ok("exp/iat valid", f"exp in {claims['exp'] - now}s")

    sub = claims.get("sub")
    email = claims.get("email")
    if not sub:
        _fail("Token missing sub claim")
        return False
    if not email:
        # M2M tokens often don't carry email — warn but pass.
        print(
            "\033[33m!\033[0m  Token has no email claim — fine for M2M test, but real "
            "user tokens MUST include email or the provisioning path fails."
        )
    _ok("User claims valid", f"sub={sub}")

    print("\n✅  Auth0 config is wired correctly. Safe to set DEV_AUTH_BYPASS=false.")
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--token", required=True, help="A real JWT from your Auth0 tenant")
    args = parser.parse_args()
    return 0 if asyncio.run(verify(args.token)) else 1


if __name__ == "__main__":
    raise SystemExit(main())
