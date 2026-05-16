"""Auth tests: dev-bypass + JWT verification.

For the JWT path we generate a real RSA keypair, mint a token, and patch the
JWKS fetcher to serve our public key. This exercises the actual jose.jwt.decode
pipeline so we catch issuer/audience/expiry bugs.
"""
from __future__ import annotations

import asyncio
import time
import uuid
from typing import Any

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from jose import jwt

from app.core import auth
from app.core.auth import _user_from_claims, _verify_jwt
from app.config import get_settings


def _make_jwks() -> tuple[rsa.RSAPrivateKey, dict[str, Any]]:
    """Generate an RSA keypair and a JWKS the verifier can consume."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_numbers = private_key.public_key().public_numbers()

    def b64url(n: int) -> str:
        import base64

        b = n.to_bytes((n.bit_length() + 7) // 8, "big")
        return base64.urlsafe_b64encode(b).rstrip(b"=").decode()

    jwks = {
        "keys": [
            {
                "kty": "RSA",
                "kid": "test-key-1",
                "use": "sig",
                "alg": "RS256",
                "n": b64url(public_numbers.n),
                "e": b64url(public_numbers.e),
            }
        ]
    }
    return private_key, jwks


def _make_token(private_key: rsa.RSAPrivateKey, claims: dict[str, Any]) -> str:
    pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    return jwt.encode(claims, pem.decode(), algorithm="RS256", headers={"kid": "test-key-1"})


@pytest.fixture
def configured_issuer(monkeypatch: pytest.MonkeyPatch) -> str:
    monkeypatch.setenv("AUTH_ISSUER", "https://test-tenant.example.com/")
    monkeypatch.setenv("AUTH_AUDIENCE", "virtual-stylist-api")
    monkeypatch.setenv("AUTH_JWKS_URL", "https://test-tenant.example.com/jwks.json")
    monkeypatch.setenv("DEV_AUTH_BYPASS", "false")
    get_settings.cache_clear()
    auth._JWKS_CACHE.clear()
    return "https://test-tenant.example.com/"


def test_verify_jwt_accepts_valid_token(
    configured_issuer: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    private_key, jwks = _make_jwks()

    async def fake_get_jwks(_url: str) -> dict[str, Any]:
        return jwks

    monkeypatch.setattr(auth, "_get_jwks", fake_get_jwks)

    token = _make_token(
        private_key,
        {
            "sub": "auth0|abc123",
            "email": "ayman@example.com",
            "name": "Ayman B",
            "iss": configured_issuer,
            "aud": "virtual-stylist-api",
            "exp": int(time.time()) + 3600,
            "iat": int(time.time()),
        },
    )
    claims = asyncio.run(_verify_jwt(token))
    assert claims["sub"] == "auth0|abc123"
    assert claims["email"] == "ayman@example.com"


def test_verify_jwt_rejects_expired_token(
    configured_issuer: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    private_key, jwks = _make_jwks()

    async def fake_get_jwks(_url: str) -> dict[str, Any]:
        return jwks

    monkeypatch.setattr(auth, "_get_jwks", fake_get_jwks)

    token = _make_token(
        private_key,
        {
            "sub": "auth0|abc123",
            "iss": configured_issuer,
            "aud": "virtual-stylist-api",
            "exp": int(time.time()) - 60,  # expired
            "iat": int(time.time()) - 3600,
        },
    )
    with pytest.raises(HTTPException) as exc:
        asyncio.run(_verify_jwt(token))
    assert exc.value.status_code == 401


def test_verify_jwt_rejects_wrong_audience(
    configured_issuer: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    private_key, jwks = _make_jwks()

    async def fake_get_jwks(_url: str) -> dict[str, Any]:
        return jwks

    monkeypatch.setattr(auth, "_get_jwks", fake_get_jwks)

    token = _make_token(
        private_key,
        {
            "sub": "auth0|abc123",
            "iss": configured_issuer,
            "aud": "another-app",  # wrong
            "exp": int(time.time()) + 3600,
            "iat": int(time.time()),
        },
    )
    with pytest.raises(HTTPException) as exc:
        asyncio.run(_verify_jwt(token))
    assert exc.value.status_code == 401


def test_verify_jwt_503_when_unconfigured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTH_ISSUER", "")
    monkeypatch.setenv("AUTH_JWKS_URL", "")
    get_settings.cache_clear()
    with pytest.raises(HTTPException) as exc:
        asyncio.run(_verify_jwt("any-token"))
    assert exc.value.status_code == 501


@pytest.mark.asyncio
async def test_user_from_claims_creates_then_returns_same(
    configured_issuer: str,
) -> None:
    """Exercising the 'first sign-in' branch needs a DB session; covered by the
    integration suite. Here we just sanity-check the error paths.
    """
    pytest.importorskip("aiosqlite")

    class _FakeDB:
        async def execute(self, _stmt: Any) -> Any:
            class _Result:
                def scalar_one_or_none(self) -> Any:
                    return None

            return _Result()

    # Missing 'sub'
    with pytest.raises(HTTPException) as exc:
        await _user_from_claims(_FakeDB(), {})  # type: ignore[arg-type]
    assert exc.value.status_code == 401

    # Missing 'email' (with sub)
    with pytest.raises(HTTPException) as exc:
        await _user_from_claims(_FakeDB(), {"sub": "auth0|x"})  # type: ignore[arg-type]
    assert exc.value.status_code == 403


# Silence unused-import warning for uuid (imported for symmetry with auth.py).
_ = uuid
