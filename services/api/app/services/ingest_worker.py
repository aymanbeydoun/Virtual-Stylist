from __future__ import annotations

import uuid
from typing import Any, ClassVar

import structlog
from arq.connections import RedisSettings
from sqlalchemy import select

from app.config import get_settings
from app.core.storage import get_storage
from app.db import SessionLocal
from app.models.wardrobe import Pattern, WardrobeItem
from app.services.model_gateway import get_model_gateway

logger = structlog.get_logger()


async def ingest_item(ctx: dict[str, Any], item_id: str) -> None:
    """Run the full CV pipeline for one wardrobe item."""
    storage = get_storage()
    gateway = get_model_gateway()
    item_uuid = uuid.UUID(item_id)

    async with SessionLocal() as db:
        item = (
            await db.execute(select(WardrobeItem).where(WardrobeItem.id == item_uuid))
        ).scalar_one()
        if item.status == "ready":
            return

        try:
            raw = await storage.read_bytes(item.raw_image_key)
        except FileNotFoundError:
            item.status = "failed"
            await db.commit()
            return

        cutout = await gateway.remove_background(raw)
        cutout_key = item.raw_image_key.replace("raw/", "cutout/")
        await storage.write_bytes(cutout_key, cutout)

        tags = await gateway.tag_item(cutout)

        item.cutout_image_key = cutout_key
        item.thumbnail_key = cutout_key  # downscale in a follow-up worker pass
        item.category = tags.category
        item.pattern = Pattern(tags.pattern)
        item.colors = tags.colors
        item.formality = tags.formality
        item.seasonality = tags.seasonality
        item.embedding = tags.embedding
        item.confidence_scores = tags.confidence_scores
        item.needs_review = min(tags.confidence_scores.values()) < 0.7
        item.status = "ready"

        await db.commit()
        logger.info("item.ingested", item_id=str(item.id), category=item.category)


class WorkerSettings:
    functions: ClassVar[list[Any]] = [ingest_item]
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
