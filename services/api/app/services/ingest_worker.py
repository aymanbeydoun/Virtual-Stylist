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
from app.services.outfit_compositor import compose_outfit_image

logger = structlog.get_logger()


def _is_transient(exc: Exception) -> bool:
    """Heuristic: anything we'd recover from on retry (rate limits, 5xx, network blips)."""
    import httpx

    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code == 429 or exc.response.status_code >= 500
    if isinstance(exc, httpx.RequestError | TimeoutError | ConnectionError):
        return True
    # Replicate's "no more credits" gets wrapped as RuntimeError by our gateway — permanent.
    return False


async def ingest_item(ctx: dict[str, Any], item_id: str) -> None:
    """Run the full CV pipeline for one wardrobe item.

    Failure model:
      - FileNotFoundError on the source bytes → permanent failure (the upload was never
        committed). Mark status='failed', return cleanly.
      - Transient gateway errors (429, 5xx, network) → re-raise so Arq retries with
        backoff. Don't burn the item.
      - Permanent gateway errors (invalid image, malformed JSON, 4xx) → mark failed.
        Re-trying these wastes credits and clogs the queue.
    """
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

        try:
            cutout = await gateway.remove_background(raw)
            cutout_key = item.raw_image_key.replace("raw/", "cutout/")
            await storage.write_bytes(cutout_key, cutout)

            tags = await gateway.tag_item(cutout)
        except Exception as exc:
            if _is_transient(exc):
                logger.info(
                    "item.ingest_retry",
                    item_id=str(item.id),
                    error_type=type(exc).__name__,
                )
                # Don't touch the DB — let Arq retry with backoff.
                raise
            logger.warning(
                "item.ingest_failed",
                item_id=str(item.id),
                error_type=type(exc).__name__,
                error_msg=str(exc)[:200],
            )
            item.status = "failed"
            await db.commit()
            return

        item.cutout_image_key = cutout_key
        item.thumbnail_key = cutout_key
        item.category = tags.category
        item.pattern = Pattern(tags.pattern)
        item.colors = tags.colors
        item.formality = tags.formality
        item.seasonality = tags.seasonality
        item.embedding = tags.embedding
        item.confidence_scores = tags.confidence_scores
        item.needs_review = tags.confidence_scores.min_confidence < 0.7
        item.status = "ready"

        await db.commit()
        logger.info("item.ingested", item_id=str(item.id), category=item.category)


class WorkerSettings:
    functions: ClassVar[list[Any]] = [ingest_item, compose_outfit_image]
    # Longer connect-timeout absorbs flaky Docker-bridge Redis reconnects on macOS.
    # Each Claude/Replicate call can take 30-60s — Arq's default 300s job timeout is fine.
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    job_timeout = 180  # seconds, per job
    max_tries = 3
    keep_result = 300
