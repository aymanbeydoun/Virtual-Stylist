import pytest

from app.config import Settings, get_settings


def test_production_with_dev_bypass_refuses_to_start(monkeypatch: pytest.MonkeyPatch) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("DEV_AUTH_BYPASS", "true")
    monkeypatch.setenv("SECRET_KEY", "x" * 32)
    with pytest.raises(RuntimeError, match="DEV_AUTH_BYPASS must be false in production"):
        get_settings()
    get_settings.cache_clear()


def test_production_with_real_auth_starts(monkeypatch: pytest.MonkeyPatch) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("DEV_AUTH_BYPASS", "false")
    monkeypatch.setenv("SECRET_KEY", "x" * 32)
    settings = get_settings()
    assert isinstance(settings, Settings)
    assert settings.dev_auth_bypass is False
    get_settings.cache_clear()
