"""Per-IP rate limiting for expensive endpoints.

Backed by slowapi. Uses an in-memory store by default; switch to Redis in
production by setting `RATELIMIT_STORAGE_URI` to a redis:// URL.
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.responses import JSONResponse

from app.core.auth import CurrentUser

limiter = Limiter(key_func=get_remote_address)


def user_or_ip(request: Request) -> str:
    """Prefer the authenticated principal as the rate-limit bucket, fall back to IP."""
    user: CurrentUser | None = getattr(request.state, "user", None)
    if user is not None:
        return f"user:{user.id}"
    return get_remote_address(request)


async def rate_limit_exceeded_handler(
    request: Request, exc: Exception
) -> Response:
    assert isinstance(exc, RateLimitExceeded)
    return JSONResponse(
        status_code=429,
        content={"detail": f"Rate limit exceeded: {exc.detail}"},
        headers={"Retry-After": "60"},
    )


__all__ = ["RateLimitExceeded", "limiter", "rate_limit_exceeded_handler", "user_or_ip"]


# Aliased to keep call sites short and the awaitable type explicit:
RateLimitHandler = Callable[[Request, Exception], Awaitable[Response]]
