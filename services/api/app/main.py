import time
import uuid
from collections.abc import Awaitable, Callable

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.v1 import (
    family,
    gaps,
    health,
    preferences,
    refine,
    stylist,
    tryon,
    wardrobe,
)
from app.config import get_settings
from app.core.rate_limit import RateLimitExceeded, limiter, rate_limit_exceeded_handler

logger = structlog.get_logger()
settings = get_settings()

app = FastAPI(
    title="Virtual Stylist API",
    version="0.1.0",
    openapi_url="/api/v1/openapi.json",
    docs_url="/api/v1/docs",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Bind a request_id + timing into structlog's contextvar context.

    Lets us trace a single request end-to-end across the API + workers. The
    request_id is also echoed back on the `X-Request-Id` response header so
    the mobile can attach it to bug reports. Without this, a failed try-on
    surfaces in worker logs with no way to correlate to the originating
    request.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        from structlog.contextvars import bind_contextvars, clear_contextvars

        incoming = request.headers.get("X-Request-Id")
        rid = incoming or uuid.uuid4().hex[:12]
        started = time.monotonic()

        clear_contextvars()
        bind_contextvars(
            request_id=rid,
            method=request.method,
            path=request.url.path,
        )

        try:
            response = await call_next(request)
        except Exception:
            logger.exception(
                "http.unhandled",
                duration_ms=int((time.monotonic() - started) * 1000),
            )
            raise

        duration_ms = int((time.monotonic() - started) * 1000)
        # Only log non-trivial requests at info; 200s on health checks would
        # drown the signal we care about.
        if response.status_code >= 400 or duration_ms > 1000:
            logger.info(
                "http.request",
                status=response.status_code,
                duration_ms=duration_ms,
            )
        response.headers["X-Request-Id"] = rid
        return response


app.add_middleware(RequestContextMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api/v1")
app.include_router(wardrobe.router, prefix="/api/v1/wardrobe", tags=["wardrobe"])
app.include_router(stylist.router, prefix="/api/v1/stylist", tags=["stylist"])
app.include_router(family.router, prefix="/api/v1/family", tags=["family"])
app.include_router(gaps.router, prefix="/api/v1/gaps", tags=["gaps"])
app.include_router(tryon.router, prefix="/api/v1/tryon", tags=["tryon"])
app.include_router(refine.router, prefix="/api/v1/stylist", tags=["refine"])
app.include_router(preferences.router, prefix="/api/v1/preferences", tags=["preferences"])
