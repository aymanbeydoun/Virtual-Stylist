import asyncio
import json
from pathlib import Path

import pytest
from PIL import Image
from tools.eval.run_eval import run


def _make_image(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (32, 32), color=(50, 50, 100)).save(path, "JPEG")


def _force_stub(monkeypatch: pytest.MonkeyPatch) -> None:
    """Eval tests must score the deterministic stub, never burn real API credits.
    Reset Settings + gateway singletons so the env override actually applies.
    """
    from app.config import get_settings
    from app.services.model_gateway import _reset_gateway_for_tests

    monkeypatch.setenv("MODEL_GATEWAY_BACKEND", "stub")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    monkeypatch.setenv("REPLICATE_API_TOKEN", "")
    get_settings.cache_clear()
    _reset_gateway_for_tests()


def test_eval_harness_runs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _force_stub(monkeypatch)
    img = tmp_path / "images" / "x.jpg"
    _make_image(img)
    dataset = tmp_path / "ds.jsonl"
    dataset.write_text(
        json.dumps(
            {
                "image": "images/x.jpg",
                "category": "mens.tops.tshirt",
                "pattern": "solid",
                "primary_color": "navy",
                "formality": 3,
                "seasonality": ["spring", "summer"],
            }
        )
        + "\n"
    )
    summary = asyncio.run(run(dataset, missing_ok=False))
    assert summary["scored"] == 1
    assert "category_exact_accuracy" in summary
    assert "per_category_exact_accuracy" in summary


def test_eval_harness_skips_missing_images(tmp_path: Path) -> None:
    dataset = tmp_path / "ds.jsonl"
    dataset.write_text(
        json.dumps(
            {
                "image": "images/does_not_exist.jpg",
                "category": "mens.tops.tshirt",
                "pattern": "solid",
                "primary_color": "navy",
                "formality": 3,
                "seasonality": ["spring"],
            }
        )
        + "\n"
    )
    summary = asyncio.run(run(dataset, missing_ok=True))
    assert summary["scored"] == 0
    assert "warning" in summary
