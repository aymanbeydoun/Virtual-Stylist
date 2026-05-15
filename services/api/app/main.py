import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import family, health, stylist, wardrobe
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
