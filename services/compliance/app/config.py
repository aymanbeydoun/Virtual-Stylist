from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="COMPLIANCE_", extra="ignore")

    environment: Literal["development", "staging", "production"] = "development"

    # "stub" returns a deterministic canned report (dev/tests, no API key needed).
    # "anthropic" runs the real audit against the Claude API.
    audit_backend: Literal["stub", "anthropic"] = "stub"
    anthropic_api_key: str = ""
    audit_model: str = "claude-opus-4-8"
    audit_max_output_tokens: int = 32000

    max_files_per_audit: int = 15
    max_file_bytes: int = 20 * 1024 * 1024
    # The Claude API caps requests at 32 MB; base64 inflates payloads ~4/3,
    # so keep the raw total comfortably below that ceiling.
    max_total_bytes: int = 22 * 1024 * 1024

    cors_origins: list[str] = ["*"]


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    if settings.environment == "production" and settings.audit_backend == "stub":
        raise RuntimeError(
            "COMPLIANCE_AUDIT_BACKEND must be 'anthropic' in production. The stub "
            "backend produces canned reports and must never audit real purchases."
        )
    return settings
