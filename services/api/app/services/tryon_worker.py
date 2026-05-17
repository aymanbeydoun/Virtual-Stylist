"""Virtual try-on worker job.

Pulls the outfit's items + the owner's base photo from storage, calls the
gateway's try_on_outfit, writes the rendered JPEG back, and updates the
OutfitTryon row with the result key.

Runs as an Arq job because nano-banana takes 8-15s — too long to block an
HTTP request.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.storage import get_storage
from app.db import SessionLocal
from app.models.outfits import Outfit, OutfitSlot
from app.models.tryons import OutfitTryon, TryonStatus
from app.models.users import OwnerKind, StyleProfile
from app.services.model_gateway import TryonInput, get_model_gateway

logger = structlog.get_logger()


# Slot priority — only these contribute to the body composite. Shoes get a
# stitched inset by the mobile layer (most VTO models can't place shoes
# convincingly on a full-body shot). Accessories/jewelry are tiny and tend to
# confuse the editor, so skipped at this stage.
_TRYON_SLOTS = (
    OutfitSlot.dress,
    OutfitSlot.top,
    OutfitSlot.bottom,
    OutfitSlot.outerwear,
)


async def _lookup_body_shape(
    db: Any, owner_kind: OwnerKind, owner_id: uuid.UUID
) -> str | None:
    """Fetch the wearer's body_shape from their style profile.

    Family members + the user himself both have StyleProfile rows keyed by
    owner_kind + owner_id. Returns None if no profile or no shape set.
    """
    row = (
        await db.execute(
            select(StyleProfile).where(
                StyleProfile.owner_kind == owner_kind,
                StyleProfile.owner_id == owner_id,
            )
        )
    ).scalar_one_or_none()
    return row.body_shape if row else None


async def tryon_outfit(ctx: dict[str, Any], tryon_id: str) -> None:
    storage = get_storage()
    gateway = get_model_gateway()
    tryon_uuid = uuid.UUID(tryon_id)

    async with SessionLocal() as db:
        tryon = (
            await db.execute(select(OutfitTryon).where(OutfitTryon.id == tryon_uuid))
        ).scalar_one()
        if tryon.status == TryonStatus.ready:
            return

        outfit = (
            await db.execute(
                select(Outfit)
                .where(Outfit.id == tryon.outfit_id)
                .options(selectinload(Outfit.items))
            )
        ).scalar_one()

        # Load base photo bytes.
        try:
            person_bytes = await storage.read_bytes(tryon.base_photo_key)
        except FileNotFoundError:
            tryon.status = TryonStatus.failed
            tryon.error_message = "base photo missing"
            tryon.completed_at = datetime.now(UTC)
            await db.commit()
            return

        # FULL OUTFIT mode — render every renderable garment chained through
        # IDM-VTON. Slower than rendering one piece (~75-100s for a typical
        # 2-3 garment outfit) but the user sees themselves in the COMPLETE
        # look, not just a hero piece. Quality > speed per product call.
        from app.models.wardrobe import WardrobeItem

        item_ids = [oi.item_id for oi in outfit.items if oi.slot in _TRYON_SLOTS]
        items_q = await db.execute(
            select(WardrobeItem).where(WardrobeItem.id.in_(item_ids))
        )
        items_by_id = {it.id: it for it in items_q.scalars().all()}

        garment_inputs: list[TryonInput] = []
        for oi in outfit.items:
            if oi.slot not in _TRYON_SLOTS:
                continue
            item = items_by_id.get(oi.item_id)
            if not item:
                continue
            key = item.cutout_image_key or item.raw_image_key
            try:
                bytes_ = await storage.read_bytes(key)
            except FileNotFoundError:
                logger.warning("tryon.item_image_missing", item_id=str(item.id), key=key)
                continue
            colors = item.colors or []
            color_phrase = (
                f"{colors[0].name} " if colors and hasattr(colors[0], "name") else ""
            )
            desc = f"{color_phrase}{item.category or oi.slot.value}".strip()
            garment_inputs.append(
                TryonInput(image_bytes=bytes_, slot=oi.slot.value, description=desc)
            )

        if not garment_inputs:
            tryon.status = TryonStatus.failed
            tryon.error_message = "no garments to render"
            tryon.completed_at = datetime.now(UTC)
            await db.commit()
            return

        # Pull the wearer's body_shape so nano-banana can drape accordingly.
        # We look up the style profile for whoever owns the outfit (user OR
        # family member). Missing profile → None → gateway falls back to a
        # shape-agnostic prompt.
        body_shape = await _lookup_body_shape(db, outfit.owner_kind, outfit.owner_id)

        try:
            result = await gateway.try_on_outfit(
                person_image=person_bytes,
                garments=garment_inputs,
                body_shape=body_shape,
            )
        except Exception as exc:
            logger.warning(
                "tryon.failed",
                tryon_id=str(tryon.id),
                error_type=type(exc).__name__,
                error_msg=str(exc)[:200],
            )
            tryon.status = TryonStatus.failed
            tryon.error_message = f"{type(exc).__name__}: {str(exc)[:300]}"
            tryon.completed_at = datetime.now(UTC)
            await db.commit()
            return

        out_key = f"tryon/{outfit.owner_id}/{tryon.id}.jpg"
        await storage.write_bytes(out_key, result.image_bytes)

        tryon.rendered_image_key = out_key
        tryon.status = TryonStatus.ready
        tryon.model_id = result.model_id
        tryon.completed_at = datetime.now(UTC)
        await db.commit()
        logger.info("tryon.ready", tryon_id=str(tryon.id), key=out_key)
