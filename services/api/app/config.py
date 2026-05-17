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
    # Two-tier bg-removal routing.
    #
    # Standard tier: 851-labs/background-remover (transparent-background, MIT).
    # ~$0.005/run, 3-8s. Fine for solid garments, struggles with hair and
    # wireframe accessories.
    #
    # Premium tier: configurable. Defaults to the standard model so a fresh
    # deployment doesn't break; swap to a higher-quality alternative
    # by setting REPLICATE_BG_REMOVAL_MODEL_PREMIUM once you've benchmarked it.
    #
    # How to pick a premium model:
    #   uv run scripts/benchmark_bg_removal.py --limit 8
    # Runs each candidate on real closet images, writes side-by-side outputs,
    # prints a CSV + Markdown report. Open the model folders in Finder, pick
    # the one with the cleanest hair / jewelry / fine-detail edges, paste
    # its full slug:version below.
    #
    # Candidates the benchmark script ships with:
    #   - 851-labs/background-remover (current standard, low cost, fast)
    #   - cjwbw/rembg                  (different rembg variant)
    #   - pollinations/modnet          (trimap-free portrait matting, best on
    #                                   hair edges; ~$0.02/run)
    #   - lucataco/rembg               (alternate rembg fork)
    #
    # Items are flagged via `wardrobe_items.quality_tier`. Default for new
    # uploads is "standard"; mobile can opt an item into "premium" either
    # explicitly or automatically if Claude Vision detects a model/skin in
    # the photo.
    replicate_bg_removal_model: str = (
        "851-labs/background-remover:"
        "a029dff38972b5fda4ec5d75d7d1cd25aeff621d2cf4946a41055d7db66b80bc"
    )
    replicate_bg_removal_model_premium: str = (
        "851-labs/background-remover:"
        "a029dff38972b5fda4ec5d75d7d1cd25aeff621d2cf4946a41055d7db66b80bc"
    )
    replicate_clip_model: str = (
        "krthr/clip-embeddings:"
        "1c0371070cb827ec3c7f2f28adcdde54b50dcd239aa6faea0bc98b174ef03fb4"
    )
    # Virtual try-on model.
    #
    # IDM-VTON is purpose-built for try-on — segments the person's clothing,
    # masks the target region, and inpaints the new garment while
    # preserving face, hair, body, and pose. Identity preservation is the
    # training objective, not a prompt-coaxing hope.
    #
    # The previous default (google/nano-banana) is a GENERAL image-edit
    # model. With person + garment photos it tended to GENERATE a new
    # person wearing the clothes — identity drifted severely in
    # production (a Black man in a bomber rendered every time, regardless
    # of who uploaded the base photo). Don't go back to it.
    replicate_tryon_model: str = (
        "cuuupid/idm-vton:"
        "c871bb9b046607b680449ecbae55fd8c6d945e0a1948644bf2361b3d021d3ff4"
    )

    # Modal-hosted FitDiT try-on endpoint. When set, the worker routes all
    # try-on requests here instead of Replicate IDM-VTON. FitDiT is ~3x
    # faster (~5s/garment vs ~17s) with comparable identity preservation,
    # and Modal lets us autoscale 0→10 GPUs without the per-account
    # serialized semaphore Replicate imposes. See infra/modal/README.md
    # for the one-time setup steps.
    modal_tryon_endpoint: str = ""

    openweather_api_key: str = ""

    cors_origins: list[str] = ["http://localhost:8081", "http://localhost:19006"]

    stylist_rate_limit: str = "30/minute"
    upload_rate_limit: str = "60/minute"

    ingest_inline: bool = False

    # Feature flags
    # Kid sub-profile creation is locked off until the VPC payment flow is wired
    # (see docs/legal/COPPA.md §3). Set to true ONLY in dev + post-legal-review.
    feature_kid_signup_enabled: bool = False


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    if settings.environment == "production" and settings.dev_auth_bypass:
        raise RuntimeError(
            "DEV_AUTH_BYPASS must be false in production. Refusing to start to "
            "prevent unauthenticated access to expensive AI endpoints."
        )
    return settings
