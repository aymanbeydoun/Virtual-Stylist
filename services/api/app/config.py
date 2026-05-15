from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: Literal["development", "staging", "production"] = "development"
    secret_key: str = Field(default="dev-secret-change-me", min_length=16)

    database_url: str = "postgresql+asyncpg://stylist:stylist@localhost:5432/virtual_stylist"
    redis_url: str = "redis://localhost:6379/0"

    storage_backend: Literal["local", "gcs"] = "local"
    storage_local_path: str = "./storage"
    gcs_bucket: str = ""

    auth_issuer: str = ""
    auth_audience: str = ""
    auth_jwks_url: str = ""
    dev_auth_bypass: bool = True

    model_gateway_backend: Literal["stub", "anthropic", "vertex"] = "stub"
    anthropic_api_key: str = ""
    vertex_project: str = ""
    vertex_location: str = "us-central1"

    openweather_api_key: str = ""

    cors_origins: list[str] = ["http://localhost:8081", "http://localhost:19006"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
