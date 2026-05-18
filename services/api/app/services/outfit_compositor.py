"""Server-side outfit flat-lay composition.

Lays out the item cutouts in a 2-column grid on a brand-coloured background and
writes the result back to storage as a PNG. This is what the mobile renders
in the outfit card — much more magazine-feel than a row of thumbnails.

Design choices:
- Slot order is deterministic so two outfits with the same items look the same:
  top/dress (TL), bottom (TR), outerwear (ML), shoes (MR), accessories (BL/BR).
- Output is 1080x1080 — square, retina-friendly for mobile cards, and big enough
  for share-sheet exports later.
- Background is a soft neutral (#F4F0EA, off-white linen-ish) that flatters
  most apparel colors. Theme tokens, not hardcoded — kept here because the
  compositor is the only consumer.
- Each item is resized to fit its slot while preserving aspect ratio, with a
  small drop shadow so cutouts feel 'placed' rather than pasted.
"""
from __future__ import annotations

import io
import uuid

import structlog
from PIL import Image, ImageDraw, ImageFilter
from sqlalchemy import select

from app.core.storage import get_storage
from app.db import SessionLocal
from app.models.outfits import Outfit, OutfitItem, OutfitSlot
from app.models.wardrobe import WardrobeItem

logger = structlog.get_logger()

CANVAS_SIZE = (1080, 1080)
BG_COLOR = (244, 240, 234, 255)  # #F4F0EA
SHADOW_COLOR = (0, 0, 0, 70)
SHADOW_OFFSET = (12, 14)
SHADOW_BLUR = 22

# Slot placement strategy.
#
# The canvas is split into a 2-column grid. Different outfits have different
# slot mixes — a dress outfit doesn't need a bottom cell, an outfit without
# shoes shouldn't leave its cell empty, etc. The previous static GRID had
# accessory + bottom colliding at (1,0) and jewelry + shoes colliding at
# (1,1) when both were present. We now resolve cells dynamically based on
# which slots are actually in the outfit.
#
# Priority order — when two slots want the same cell, the higher-priority
# slot wins and the lower-priority one is dropped from the flat-lay (it's
# still part of the outfit, just doesn't appear in the picture).
_SLOT_PRIORITY: list[OutfitSlot] = [
    OutfitSlot.dress,
    OutfitSlot.top,
    OutfitSlot.bottom,
    OutfitSlot.outerwear,
    OutfitSlot.shoes,
    OutfitSlot.accessory,
    OutfitSlot.jewelry,
]
CELL_SIZE = (CANVAS_SIZE[0] // 2, CANVAS_SIZE[1] // 2)
INNER_PADDING = 40


def _resolve_layout(
    slots_present: set[OutfitSlot],
) -> dict[OutfitSlot, tuple[int, int, int, int]]:
    """Pick a non-overlapping cell for each slot present in the outfit.

    Returns {slot: (col, row, cspan, rspan)} for every slot that survives
    the collision resolution. Slots not in the map are skipped during
    rendering (this is what fixes the overlap bug).
    """
    layout: dict[OutfitSlot, tuple[int, int, int, int]] = {}
    occupied: set[tuple[int, int]] = set()

    def _claim(slot: OutfitSlot, box: tuple[int, int, int, int]) -> bool:
        col, row, cspan, rspan = box
        cells = {
            (c, r)
            for c in range(col, col + cspan)
            for r in range(row, row + rspan)
        }
        if cells & occupied:
            return False
        occupied.update(cells)
        layout[slot] = box
        return True

    # Dress, if present, claims the full left column (two stacked cells)
    # so the hero item dominates the composition.
    if OutfitSlot.dress in slots_present:
        _claim(OutfitSlot.dress, (0, 0, 1, 2))
    else:
        # No dress → top owns top-left, bottom owns top-right.
        if OutfitSlot.top in slots_present:
            _claim(OutfitSlot.top, (0, 0, 1, 1))
        if OutfitSlot.bottom in slots_present:
            _claim(OutfitSlot.bottom, (1, 0, 1, 1))

    # Bottom row: outerwear bottom-left, shoes bottom-right.
    if OutfitSlot.outerwear in slots_present:
        _claim(OutfitSlot.outerwear, (0, 1, 1, 1))
    if OutfitSlot.shoes in slots_present:
        _claim(OutfitSlot.shoes, (1, 1, 1, 1))

    # Accessories + jewelry fill any cells the primary slots didn't claim.
    # Priority order: top-right > bottom-right > bottom-left > top-left.
    fallback_cells = [(1, 0, 1, 1), (1, 1, 1, 1), (0, 1, 1, 1), (0, 0, 1, 1)]
    for slot in (OutfitSlot.accessory, OutfitSlot.jewelry):
        if slot not in slots_present:
            continue
        for box in fallback_cells:
            if _claim(slot, box):
                break

    return layout


def _place_cutout(
    canvas: Image.Image, cutout: Image.Image, cell_box: tuple[int, int, int, int]
) -> None:
    """Resize cutout to fit cell_box (x0, y0, x1, y1) preserving aspect, drop a soft shadow."""
    x0, y0, x1, y1 = cell_box
    cell_w = (x1 - x0) - 2 * INNER_PADDING
    cell_h = (y1 - y0) - 2 * INNER_PADDING

    cw, ch = cutout.size
    scale = min(cell_w / cw, cell_h / ch)
    new_size = (max(1, int(cw * scale)), max(1, int(ch * scale)))
    resized = cutout.resize(new_size, Image.Resampling.LANCZOS)

    # Center inside the cell.
    px = x0 + INNER_PADDING + (cell_w - new_size[0]) // 2
    py = y0 + INNER_PADDING + (cell_h - new_size[1]) // 2

    # Soft shadow: alpha-only silhouette, blurred + offset.
    alpha = resized.split()[-1] if resized.mode == "RGBA" else None
    if alpha:
        shadow = Image.new("RGBA", resized.size, SHADOW_COLOR)
        shadow.putalpha(alpha)
        shadow = shadow.filter(ImageFilter.GaussianBlur(radius=SHADOW_BLUR))
        canvas.alpha_composite(shadow, (px + SHADOW_OFFSET[0], py + SHADOW_OFFSET[1]))

    canvas.alpha_composite(resized.convert("RGBA"), (px, py))


def _grid_to_pixels(box: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    """Convert a (col, row, cspan, rspan) grid box to pixel coords."""
    col, row, cspan, rspan = box
    x0 = col * CELL_SIZE[0]
    y0 = row * CELL_SIZE[1]
    x1 = x0 + cspan * CELL_SIZE[0]
    y1 = y0 + rspan * CELL_SIZE[1]
    return x0, y0, x1, y1


async def _load_item_cutout(storage_key: str | None) -> Image.Image | None:
    if not storage_key:
        return None
    storage = get_storage()
    try:
        raw = await storage.read_bytes(storage_key)
    except FileNotFoundError:
        return None
    try:
        img = Image.open(io.BytesIO(raw))
        img.load()
        return img.convert("RGBA")
    except Exception as exc:
        logger.warning("compositor.bad_cutout", key=storage_key, error=str(exc)[:120])
        return None


async def compose_outfit_image(ctx: dict[str, object], outfit_id: str) -> None:
    """Build the flat-lay PNG for one outfit and persist its storage key."""
    outfit_uuid = uuid.UUID(outfit_id)
    storage = get_storage()

    async with SessionLocal() as db:
        outfit = (
            await db.execute(select(Outfit).where(Outfit.id == outfit_uuid))
        ).scalar_one_or_none()
        if not outfit or outfit.composite_image_key:
            return

        rows = (
            await db.execute(
                select(OutfitItem.slot, WardrobeItem.cutout_image_key, WardrobeItem.thumbnail_key)
                .join(WardrobeItem, WardrobeItem.id == OutfitItem.item_id)
                .where(OutfitItem.outfit_id == outfit_uuid)
            )
        ).all()
        if not rows:
            return

        canvas = Image.new("RGBA", CANVAS_SIZE, BG_COLOR)

        # Resolve the layout dynamically based on which slots are actually
        # present. This is the fix for the collision bug (accessory+bottom,
        # jewelry+shoes both targeting the same cell when the outfit had
        # all four). Slots that lose the collision are dropped from the
        # flat-lay — they're still part of the outfit data, just not in
        # the picture.
        slots_present = {row.slot for row in rows}
        layout = _resolve_layout(slots_present)

        # De-dup: if the same slot has multiple items (shouldn't happen but
        # belt-and-braces), keep the first one and skip the rest.
        rendered_slots: set[OutfitSlot] = set()
        for slot, cutout_key, thumb_key in rows:
            if slot not in layout:
                continue
            if slot in rendered_slots:
                continue
            key = cutout_key or thumb_key
            cutout = await _load_item_cutout(key)
            if not cutout:
                continue
            _place_cutout(canvas, cutout, _grid_to_pixels(layout[slot]))
            rendered_slots.add(slot)

        # Brand strip along the bottom for share/export later.
        draw = ImageDraw.Draw(canvas)
        draw.rectangle(
            (0, CANVAS_SIZE[1] - 6, CANVAS_SIZE[0], CANVAS_SIZE[1]),
            fill=(0, 0, 0, 220),
        )

        out_bytes = io.BytesIO()
        canvas.convert("RGB").save(out_bytes, format="JPEG", quality=88, optimize=True)
        composite_key = f"outfit-composite/{outfit.owner_id}/{outfit.id}.jpg"
        await storage.write_bytes(composite_key, out_bytes.getvalue())

        outfit.composite_image_key = composite_key
        await db.commit()
        logger.info("outfit.composed", outfit_id=str(outfit.id), key=composite_key)


