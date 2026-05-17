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
from app.models.users import OwnerKind, StyleProfile
from app.models.wardrobe import WardrobeItem
from app.schemas.common import WeatherSnapshot
from app.services.model_gateway import StylistResult, get_model_gateway
from app.services.weather import get_weather


async def _resolved_default_style(
    db: AsyncSession, owner_kind: OwnerKind, owner_id: uuid.UUID
) -> str | None:
    """Return the saved preferred_style for the owner, or None."""
    profile = (
        await db.execute(
            select(StyleProfile).where(
                StyleProfile.owner_kind == owner_kind,
                StyleProfile.owner_id == owner_id,
            )
        )
    ).scalar_one_or_none()
    return profile.preferred_style if profile else None


async def _resolved_body_shape(
    db: AsyncSession, owner_kind: OwnerKind, owner_id: uuid.UUID
) -> str | None:
    profile = (
        await db.execute(
            select(StyleProfile).where(
                StyleProfile.owner_kind == owner_kind,
                StyleProfile.owner_id == owner_id,
            )
        )
    ).scalar_one_or_none()
    return profile.body_shape if profile else None

_CATEGORY_TO_SLOT = {
    "tops": OutfitSlot.top,
    "bottoms": OutfitSlot.bottom,
    "dresses": OutfitSlot.dress,
    "outerwear": OutfitSlot.outerwear,
    "shoes": OutfitSlot.shoes,
    "accessories": OutfitSlot.accessory,
    "jewelry": OutfitSlot.jewelry,
}

# Per-body-shape stylist guidance — kept short so it doesn't blow the prompt
# budget but specific enough that Claude actually changes the recommendation.
# Reference: standard women's/men's fashion-school body-shape framework.
_BODY_SHAPE_GUIDANCE: dict[str, str] = {
    "rectangle": (
        "Wearer has a rectangle body shape (shoulders ≈ waist ≈ hips). Create curves "
        "with belted waists, peplum tops, structured shoulders. Avoid straight shift "
        "dresses and boxy outerwear."
    ),
    "hourglass": (
        "Wearer has an hourglass body shape (defined waist, balanced shoulders/hips). "
        "Lean into fitted waists, wrap dresses, high-rise bottoms. Avoid oversized "
        "silhouettes that hide the waist."
    ),
    "pear": (
        "Wearer has a pear body shape (hips wider than shoulders). Balance with "
        "structured shoulders, statement tops, A-line or straight-leg bottoms. Avoid "
        "skinny bottoms with simple tops, low-rise jeans, hip pockets."
    ),
    "apple": (
        "Wearer has an apple body shape (fuller middle, slimmer legs). V-necklines, "
        "vertical lines, empire waists, straight-leg or bootcut bottoms. Avoid "
        "high-waisted belted looks, clingy fabric at the midsection."
    ),
    "inverted_triangle": (
        "Wearer has an inverted triangle body shape (shoulders wider than hips). "
        "Soft shoulder lines, scoop/V necks, wide-leg or A-line bottoms. Avoid "
        "shoulder pads, boat necks, skinny bottoms with tight tops."
    ),
    "athletic": (
        "Wearer has an athletic body shape (defined muscles, less curve). Add visual "
        "softness with flowing fabrics, layered necklines, peplum or ruched waists. "
        "Avoid stiff boxy fits that flatten the silhouette."
    ),
}


_DESTINATION_FORMALITY = {
    "office": (5, 9),
    "formal_event": (8, 10),
    "wedding": (7, 10),  # guest attire — never under-dress
    "restaurant": (4, 8),  # nicer dining — UAE skews dressier
    "date": (4, 8),
    "religious": (5, 9),  # modest + formal-leaning by default
    "brunch": (3, 7),
    "mall": (2, 7),
    "casual": (1, 6),
    "school": (1, 5),
    "park": (1, 4),
    "playground": (0, 4),
    "beach": (0, 3),
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
        # Carry deep attributes through to the stylist prompt so it can apply
        # fabric / fit / neckline reasoning. Empty {} when nothing tagged.
        "attributes": item.attributes or {},
    }


# Soft color-harmony scoring. Returns 0.0-1.0 where 1.0 means strong harmony.
# Used post-LLM to surface clashing outfits to the rationale rather than
# silently shipping them.
def _outfit_harmony_score(items_with_colors: list[list[dict[str, Any]]]) -> float:
    """Given a list of per-item color lists, return a coarse harmony score.

    Algorithm: convert each dominant color to HSL, count how many distinct
    *hue families* (60° buckets) appear. 1 family = monochrome (1.0).
    2 families with one being neutral = analogous (0.9). 2 saturated families
    that are ~180° apart = complementary (0.7). 3+ saturated families = clash
    (0.3). Calibrated to be permissive; only flag the obvious chaos.
    """
    import colorsys

    def _hue_family(hex_str: str) -> int | None:
        try:
            r, g, b = (int(hex_str[i : i + 2], 16) / 255 for i in (1, 3, 5))
        except (ValueError, IndexError):
            return None
        h, _light, sat = colorsys.rgb_to_hls(r, g, b)
        if sat < 0.15:  # neutral / greyscale
            return -1
        return int(h * 360) // 60  # 6 hue families

    families: set[int] = set()
    has_neutral = False
    for item_colors in items_with_colors:
        for c in item_colors[:1]:  # dominant only
            hex_val = str(c.get("hex", ""))
            fam = _hue_family(hex_val)
            if fam is None:
                continue
            if fam == -1:
                has_neutral = True
            else:
                families.add(fam)

    sat_count = len(families)
    if sat_count == 0:
        return 1.0  # all neutrals
    if sat_count == 1:
        return 1.0 if has_neutral else 0.95
    if sat_count == 2:
        # Complementary check: families 0/3, 1/4, 2/5 are roughly opposite.
        fams = sorted(families)
        complementary = (fams[1] - fams[0]) == 3
        return 0.9 if has_neutral else (0.75 if complementary else 0.6)
    # 3+ saturated families
    return 0.3


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
    mood: str | None,
    notes: str | None,
    kid_mode: bool,
    style: str | None = None,
    lat: float | None = None,
    lon: float | None = None,
) -> tuple[list[Outfit], WeatherSnapshot | None]:
    weather = await get_weather(lat, lon)
    items = await _select_candidates(
        db, owner_kind=owner_kind, owner_id=owner_id, destination=destination, weather=weather
    )
    if not items:
        return [], weather

    # Resolve style: per-request value wins; fall back to the user's saved
    # default in style_profiles so a streetwear-leaning user gets streetwear
    # by default without re-picking every time.
    resolved_style = style or await _resolved_default_style(db, owner_kind, owner_id)
    body_shape = await _resolved_body_shape(db, owner_kind, owner_id)

    candidates = [_serialize_candidate(i) for i in items]
    item_by_id = {str(i.id): i for i in items}

    # Build optional body-shape note for the stylist prompt.
    effective_notes = notes
    if body_shape:
        body_note = _BODY_SHAPE_GUIDANCE.get(body_shape, "")
        if body_note:
            effective_notes = (
                f"{notes}\n\n{body_note}" if notes else body_note
            )

    gateway = get_model_gateway()
    result: StylistResult = await gateway.stylist_compose(
        candidates=candidates,
        destination=destination,
        mood=mood,
        style=resolved_style,
        weather=weather,
        notes=effective_notes,
        kid_mode=kid_mode,
    )

    used_ids: set[str] = set()
    outfits_orm: list[Outfit] = []
    MAX_OUTFITS = 3

    for outfit_data in result.outfits:
        if len(outfits_orm) >= MAX_OUTFITS:
            break
        if _validate(outfit_data, weather):
            continue
        if any(i["item_id"] in used_ids for i in outfit_data["items"]):
            continue

        # Color harmony post-check. We only DOWN-rank — if every outfit is
        # below threshold we still ship them, because rejecting all of them
        # leaves the user with nothing.
        item_colors = [
            item_by_id[i["item_id"]].colors  # list of ColorTag models
            for i in outfit_data["items"]
            if i["item_id"] in item_by_id
        ]
        as_dicts = [[c.model_dump(mode="json") for c in colors] for colors in item_colors]
        harmony = _outfit_harmony_score(as_dicts)
        # Combine the LLM's confidence with our harmony signal. 0.7 weight on
        # LLM, 0.3 weight on harmony — lets the AI lead but penalises clashes.
        raw_conf = float(outfit_data.get("confidence") or 0.7)
        weighted_conf = 0.7 * raw_conf + 0.3 * harmony

        rationale = outfit_data.get("rationale")
        if harmony < 0.55 and rationale:
            rationale = (
                f"{rationale} (Note: this look mixes several saturated colors — "
                f"try one of the alternates for a calmer palette.)"
            )

        outfit = Outfit(
            owner_kind=owner_kind,
            owner_id=owner_id,
            source=OutfitSource.ai_generated,
            destination=destination,
            mood=mood,
            style=resolved_style,
            weather_snapshot=weather,
            rationale=rationale,
            confidence=weighted_conf,
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
