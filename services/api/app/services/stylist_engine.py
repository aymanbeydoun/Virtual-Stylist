from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.outfits import (
    Outfit,
    OutfitEvent,
    OutfitEventKind,
    OutfitItem,
    OutfitSlot,
    OutfitSource,
)
from app.models.users import OwnerKind
from app.models.wardrobe import WardrobeItem
from app.schemas.common import WeatherSnapshot
from app.services.model_gateway import StylistResult, get_model_gateway
from app.services.weather import get_weather

_CATEGORY_TO_SLOT = {
    "tops": OutfitSlot.top,
    "bottoms": OutfitSlot.bottom,
    "dresses": OutfitSlot.dress,
    "outerwear": OutfitSlot.outerwear,
    "shoes": OutfitSlot.shoes,
    "accessories": OutfitSlot.accessory,
    "jewelry": OutfitSlot.jewelry,
}

_DESTINATION_FORMALITY = {
    "office": (5, 9),
    "formal_event": (8, 10),
    "date": (4, 8),
    "brunch": (3, 7),
    "casual": (1, 6),
    "school": (1, 5),
    "playground": (0, 4),
    "gym": (0, 3),
    "travel": (2, 6),
}


def _slot_for(category: str | None) -> OutfitSlot | None:
    if not category:
        return None
    parts = category.split(".")
    for part in parts:
        if part in _CATEGORY_TO_SLOT:
            return _CATEGORY_TO_SLOT[part]
    return None


def _weather_ok(item: WardrobeItem, weather: WeatherSnapshot | None) -> bool:
    if not weather:
        return True
    if weather.temp_c >= 28 and "winter" in (item.seasonality or []):
        return False
    if weather.temp_c <= 5 and "summer" in (item.seasonality or []):
        return False
    return True


async def _select_candidates(
    db: AsyncSession,
    *,
    owner_kind: OwnerKind,
    owner_id: uuid.UUID,
    destination: str,
    weather: WeatherSnapshot | None,
    per_slot: int = 4,
) -> list[WardrobeItem]:
    formality_range = _DESTINATION_FORMALITY.get(destination, (0, 10))
    cutoff = datetime.now(UTC) - timedelta(days=3)

    # exclude items worn in the last 3 days
    recent_q = (
        select(OutfitItem.item_id)
        .join(Outfit, Outfit.id == OutfitItem.outfit_id)
        .join(OutfitEvent, OutfitEvent.outfit_id == Outfit.id)
        .where(
            and_(
                Outfit.owner_kind == owner_kind,
                Outfit.owner_id == owner_id,
                OutfitEvent.event_kind == OutfitEventKind.worn,
                OutfitEvent.occurred_at >= cutoff,
            )
        )
    )
    recent_ids = {r for r, in (await db.execute(recent_q)).all()}

    q = select(WardrobeItem).where(
        and_(
            WardrobeItem.owner_kind == owner_kind,
            WardrobeItem.owner_id == owner_id,
            WardrobeItem.deleted_at.is_(None),
            WardrobeItem.status == "ready",
        )
    )
    items = list((await db.execute(q)).scalars().all())

    buckets: dict[OutfitSlot, list[WardrobeItem]] = {}
    for item in items:
        if item.id in recent_ids:
            continue
        if item.formality is not None and not (
            formality_range[0] <= item.formality <= formality_range[1]
        ):
            continue
        if not _weather_ok(item, weather):
            continue
        slot = _slot_for(item.category)
        if slot is None:
            continue
        buckets.setdefault(slot, []).append(item)

    candidates: list[WardrobeItem] = []
    for slot_items in buckets.values():
        candidates.extend(slot_items[:per_slot])
    return candidates


def _serialize_candidate(item: WardrobeItem) -> dict[str, Any]:
    slot = _slot_for(item.category)
    return {
        "id": str(item.id),
        "slot": slot.value if slot else "accessory",
        "category": item.category,
        "colors": [c.model_dump(mode="json") for c in item.colors],
        "pattern": item.pattern.value if item.pattern else None,
        "formality": item.formality,
        "seasonality": item.seasonality,
    }


def _validate(outfit: dict[str, Any], weather: WeatherSnapshot | None) -> str | None:
    slots = [i["slot"] for i in outfit["items"]]
    has_top_or_dress = "top" in slots or "dress" in slots
    has_bottom_or_dress = "bottom" in slots or "dress" in slots
    if not (has_top_or_dress and has_bottom_or_dress):
        return "outfit must include a top + bottom or a dress"
    if "shoes" not in slots:
        return "outfit must include shoes"
    if len(slots) != len(set(zip(slots, slots, strict=True))):
        # crude duplicate-slot check (allow one accessory + one jewelry)
        non_accessory = [s for s in slots if s not in ("accessory", "jewelry")]
        if len(non_accessory) != len(set(non_accessory)):
            return "outfit has duplicate slot"
    return None


async def generate_outfits(
    db: AsyncSession,
    *,
    owner_kind: OwnerKind,
    owner_id: uuid.UUID,
    destination: str,
    mood: str,
    notes: str | None,
    kid_mode: bool,
    lat: float | None = None,
    lon: float | None = None,
) -> tuple[list[Outfit], WeatherSnapshot | None]:
    weather = await get_weather(lat, lon)
    items = await _select_candidates(
        db, owner_kind=owner_kind, owner_id=owner_id, destination=destination, weather=weather
    )
    if not items:
        return [], weather

    candidates = [_serialize_candidate(i) for i in items]
    item_by_id = {str(i.id): i for i in items}

    gateway = get_model_gateway()
    result: StylistResult = await gateway.stylist_compose(
        candidates=candidates,
        destination=destination,
        mood=mood,
        weather=weather,
        notes=notes,
        kid_mode=kid_mode,
    )

    used_ids: set[str] = set()
    outfits_orm: list[Outfit] = []
    for outfit_data in result.outfits:
        if _validate(outfit_data, weather):
            continue
        if any(i["item_id"] in used_ids for i in outfit_data["items"]):
            continue
        outfit = Outfit(
            owner_kind=owner_kind,
            owner_id=owner_id,
            source=OutfitSource.ai_generated,
            destination=destination,
            mood=mood,
            weather_snapshot=weather,
            rationale=outfit_data.get("rationale"),
            confidence=outfit_data.get("confidence"),
            model_id=result.model_id,
        )
        for entry in outfit_data["items"]:
            item_id = entry["item_id"]
            if item_id not in item_by_id:
                continue
            used_ids.add(item_id)
            outfit.items.append(
                OutfitItem(item_id=uuid.UUID(item_id), slot=OutfitSlot(entry["slot"]))
            )
        db.add(outfit)
        outfits_orm.append(outfit)

    await db.commit()
    for o in outfits_orm:
        await db.refresh(o, attribute_names=["items"])

    if outfits_orm:
        await _enqueue_composition(outfits_orm)

    return outfits_orm, weather


async def _enqueue_composition(outfits: list[Outfit]) -> None:
    """Schedule each outfit for flat-lay composition.

    Falls back to an inline render when Redis isn't available (eg. tests, single-
    process dev). Inline keeps the API responsive only if the composition is
    fast; for 3 outfits at 1080x1080 it's ~100ms — acceptable in dev.
    """
    from app.config import get_settings
    from app.services.outfit_compositor import compose_outfit_image

    settings = get_settings()
    if settings.ingest_inline:
        for o in outfits:
            await compose_outfit_image({}, str(o.id))
        return
    try:
        from arq import create_pool
        from arq.connections import RedisSettings

        redis = await create_pool(RedisSettings.from_dsn(settings.redis_url))
        for o in outfits:
            await redis.enqueue_job("compose_outfit_image", str(o.id))
        await redis.aclose()
    except Exception:
        for o in outfits:
            await compose_outfit_image({}, str(o.id))
