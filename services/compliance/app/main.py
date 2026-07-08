from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import router
from app.config import get_settings

settings = get_settings()

app = FastAPI(
    title="BFL Compliance & Audit Agent",
    version="0.1.0",
    openapi_url="/api/v1/openapi.json",
    docs_url="/api/v1/docs",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/v1", tags=["audit"])

_WEB_DIR = Path(__file__).parent / "web"

app.mount("/static", StaticFiles(directory=_WEB_DIR / "static"), name="static")


@app.get("/", include_in_schema=False)
async def dashboard() -> FileResponse:
    return FileResponse(_WEB_DIR / "index.html")
