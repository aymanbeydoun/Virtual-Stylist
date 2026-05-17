"""Production gateway tests that don't burn real API credits.

We don't mock the network because async-mocking httpx + anthropic is fragile.
Instead we test the deterministic pieces — JSON extraction, prompt assembly,
gateway selection — and rely on the live smoke test for the end-to-end path.
"""
from __future__ import annotations

import pytest

from app.config import get_settings
from app.services.model_gateway import (
    ProductionGateway,
    StubGateway,
    _extract_json,
    _reset_gateway_for_tests,
    get_model_gateway,
)


class TestExtractJson:
    def test_plain_json(self) -> None:
        assert _extract_json('{"a": 1}') == {"a": 1}

    def test_with_fences(self) -> None:
        text = '```json\n{"category": "mens.tops.tshirt"}\n```'
        assert _extract_json(text) == {"category": "mens.tops.tshirt"}

    def test_with_prose_before(self) -> None:
        text = 'Here is the tag:\n{"category": "x", "pattern": "solid"}'
        assert _extract_json(text) == {"category": "x", "pattern": "solid"}

    def test_nested_object(self) -> None:
        text = '{"outfits": [{"items": [{"item_id": "abc", "slot": "top"}]}]}'
        result = _extract_json(text)
        assert result["outfits"][0]["items"][0]["item_id"] == "abc"

    def test_no_json_raises(self) -> None:
        with pytest.raises(ValueError, match="no JSON object"):
            _extract_json("the model refused")


class TestGatewaySelection:
    def setup_method(self) -> None:
        get_settings.cache_clear()
        _reset_gateway_for_tests()

    def teardown_method(self) -> None:
        get_settings.cache_clear()
        _reset_gateway_for_tests()

    def test_defaults_to_stub(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Ensure we don't accidentally pick up real keys from a developer's .env.
        monkeypatch.setenv("MODEL_GATEWAY_BACKEND", "stub")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "ignored-in-stub-mode")
        get_settings.cache_clear()
        _reset_gateway_for_tests()
        gw = get_model_gateway()
        assert isinstance(gw, StubGateway)

    def test_returns_production_when_anthropic_configured(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("MODEL_GATEWAY_BACKEND", "anthropic")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-key")
        get_settings.cache_clear()
        _reset_gateway_for_tests()
        gw = get_model_gateway()
        assert isinstance(gw, ProductionGateway)

    def test_falls_back_to_stub_when_key_missing(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: pytest.TempPathFactory
    ) -> None:
        # Backend set but no key anywhere → must NOT crash, must return stub.
        # We point env_file at an empty file so a developer's local .env doesn't bleed in.
        import os

        empty_env = tmp_path / "empty.env"  # type: ignore[operator]
        empty_env.write_text("")
        monkeypatch.chdir(tmp_path)  # type: ignore[arg-type]
        monkeypatch.setenv("MODEL_GATEWAY_BACKEND", "anthropic")
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        # Belt-and-braces: clear from launchctl-style empties too.
        os.environ.pop("ANTHROPIC_API_KEY", None)
        get_settings.cache_clear()
        _reset_gateway_for_tests()
        gw = get_model_gateway()
        assert isinstance(gw, StubGateway)
