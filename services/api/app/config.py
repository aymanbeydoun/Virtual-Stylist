from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict


class _DotenvWinsOnEmpty(PydanticBaseSettingsSource):
    """Inverts pydantic-settings priority for the case where the OS exports an *empty*
    string for a known var (some sandboxed runtimes do this to scrub credentials).
    If env var is "" but .env has a real value, treat the .env value as authoritative.
    """

    def __init__(
        self,
        settings_cls: type[BaseSettings],
        env_source: PydanticBaseSettingsSource,
        dotenv_source: PydanticBaseSettingsSource,
    ) -> None:
        super().__init__(settings_cls)
        self._env = env_source
        self._dotenv = dotenv_source

    def get_field_value(
        self, field: object, field_name: str
    ) -> tuple[object, str, bool]:  # pragma: no cover - pydantic protocol
        return None, field_name, False

    def __call__(self) -> dict[str, object]:
        merged: dict[str, object] = dict(self._dotenv())
        for k, v in self._env().items():
            if isinstance(v, str) and v == "" and k in merged:
                continue
            merged[k] = v
        return merged


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (
            init_settings,
            _DotenvWinsOnEmpty(settings_cls, env_settings, dotenv_settings),
            file_secret_settings,
        )

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
    anthropic_model: str = "claude-sonnet-4-6"
    anthropic_vision_model: str = "claude-sonnet-4-6"
    vertex_project: str = ""
    vertex_location: str = "us-central1"

    replicate_api_token: str = ""
    # 851-labs/background-remover (transparent-background, MIT) — higher-quality
    # mattes than lucataco's bg-remover, still cheap (~$0.005/run). MIT-licensed
    # so commercial OK. Swap via env if needed.
    replicate_bg_removal_model: str = (
        "851-labs/background-remover:"
        "a029dff38972b5fda4ec5d75d7d1cd25aeff621d2cf4946a41055d7db66b80bc"
    )
    replicate_clip_model: str = (
        "krthr/clip-embeddings:"
        "1c0371070cb827ec3c7f2f28adcdde54b50dcd239aa6faea0bc98b174ef03fb4"
    )
    replicate_tryon_model: str = (
        "google/nano-banana:"
        "5bdc2c7cd642ae33611d8c33f79615f98ff02509ab8db9d8ec1cc6c36d378fba"
    )

    openweather_api_key: str = ""

    cors_origins: list[str] = ["http://localhost:8081", "http://localhost:19006"]

    stylist_rate_limit: str = "30/minute"
    upload_rate_limit: str = "60/minute"

    ingest_inline: bool = False


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    if settings.environment == "production" and settings.dev_auth_bypass:
        raise RuntimeError(
            "DEV_AUTH_BYPASS must be false in production. Refusing to start to "
            "prevent unauthenticated access to expensive AI endpoints."
        )
    return settings
