"""Tests for the closet-gap analysis service.

We exercise the stub gateway path so CI never hits real API quotas.
Real-AI behavior is verified via the live smoke test against a seeded closet.
"""
from __future__ import annotations

import pytest

from app.services.model_gateway import (
    StubGateway,
    _reset_gateway_for_tests,
)


@pytest.fixture(autouse=True)
def _reset() -> None:
    _reset_gateway_for_tests()


@pytest.mark.asyncio
async def test_stub_finds_shoes_gap_when_only_tops_and_bottoms() -> None:
    gw = StubGateway()
    items = [
        {"slot": "top", "category": "mens.tops.t-shirt"},
        {"slot": "bottom", "category": "mens.bottoms.jeans"},
    ]
    result = await gw.analyze_gaps(items=items, owner_label="Ayman")
    slots = {f["slot"] for f in result.findings}
    assert "shoes" in slots, f"expected shoes gap, got {slots}"
    shoes_gap = next(f for f in result.findings if f["slot"] == "shoes")
    assert shoes_gap["severity"] == "high"


@pytest.mark.asyncio
async def test_stub_finds_belt_gap_when_no_belt() -> None:
    gw = StubGateway()
    items = [
        {"slot": "top", "category": "mens.tops.t-shirt"},
        {"slot": "bottom", "category": "mens.bottoms.jeans"},
        {"slot": "shoes", "category": "mens.shoes.sneaker"},
    ]
    result = await gw.analyze_gaps(items=items, owner_label="Ayman")
    titles = [f["title"] for f in result.findings]
    assert any("belt" in t.lower() for t in titles)


@pytest.mark.asyncio
async def test_stub_no_findings_for_complete_basic_wardrobe() -> None:
    gw = StubGateway()
    items = [
        {"slot": "top", "category": "mens.tops.t-shirt"},
        {"slot": "bottom", "category": "mens.bottoms.jeans"},
        {"slot": "shoes", "category": "mens.shoes.sneaker"},
        {"slot": "accessory", "category": "accessories.belts.leather"},
    ]
    result = await gw.analyze_gaps(items=items, owner_label="Ayman")
    assert result.findings == []
