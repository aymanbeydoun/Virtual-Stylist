import pytest

from app.services.model_gateway import StubGateway


@pytest.mark.asyncio
async def test_stub_tag_item_returns_full_payload() -> None:
    gw = StubGateway()
    result = await gw.tag_item(b"\x00" * 1024)
    assert result.category
    assert result.pattern in {"solid", "stripe", "floral", "graphic", "plaid", "other"}
    assert 0 <= result.formality <= 10
    assert len(result.embedding) == 768
    assert "category" in result.confidence_scores


@pytest.mark.asyncio
async def test_stub_stylist_composes_outfits_with_required_slots() -> None:
    gw = StubGateway()
    candidates = [
        {"id": f"i{i}", "slot": slot}
        for i, slot in enumerate(["top", "top", "bottom", "bottom", "shoes", "shoes", "accessory"])
    ]
    result = await gw.stylist_compose(
        candidates=candidates,
        destination="office",
        mood="confident",
        weather={"temp_c": 22, "condition": "clear"},
        notes=None,
        kid_mode=False,
    )
    assert result.model_id == "stub-stylist-v0"
    assert 1 <= len(result.outfits) <= 3
    for outfit in result.outfits:
        slots = {i["slot"] for i in outfit["items"]}
        assert "top" in slots and "bottom" in slots and "shoes" in slots
