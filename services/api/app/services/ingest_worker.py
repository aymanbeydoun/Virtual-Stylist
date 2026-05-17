from __future__ import annotations

import io
import uuid
from typing import Any, ClassVar

import pillow_heif
import structlog
from arq.connections import RedisSettings
from PIL import Image
from sqlalchemy import select

from app.config import get_settings
from app.core.storage import get_storage
from app.db import SessionLocal
from app.models.wardrobe import Pattern, WardrobeItem
from app.services.model_gateway import get_model_gateway
from app.services.outfit_compositor import compose_outfit_image
from app.services.tryon_worker import tryon_outfit

# Register HEIF/HEIC decoder so Pillow can open iPhone Camera default exports.
pillow_heif.register_heif_opener()


def _normalise_to_jpeg(raw: bytes) -> bytes:
    """Decode any Pillow-supported image and re-encode as JPEG.

    iPhones save photos as HEIC by default. Replicate's models and Claude Vision
    refuse anything that isn't JPEG/PNG/GIF/WebP — even when the file has a
    .jpg extension. Decoding via Pillow + re-encoding as JPEG is a safe pass:
    real JPEGs round-trip identically (to within transcoding noise), HEIC gets
    converted, and corrupt bytes raise here instead of mysteriously failing
    300 lines downstream.
    """
    img: Image.Image = Image.open(io.BytesIO(raw))
    if img.mode in ("RGBA", "P", "LA"):
        # JPEG can't carry alpha; composite onto white so transparent regions
        # show as white rather than going black.
        background = Image.new("RGB", img.size, (255, 255, 255))
        background.paste(img, mask=img.split()[-1] if img.mode != "P" else None)
        img = background
    elif img.mode != "RGB":
        img = img.convert("RGB")
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=90, optimize=True)
    return out.getvalue()

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

        # Normalise HEIC / oddball formats to JPEG before anything else touches
        # them. iPhone Camera defaults to HEIC; Replicate + Claude can't decode.
        try:
            raw = _normalise_to_jpeg(raw)
            # Persist the normalised JPEG so subsequent re-runs + the mobile
            # preview both work without re-converting.
            await storage.write_bytes(item.raw_image_key, raw)
        except Exception as exc:
            logger.warning(
                "item.normalise_failed",
                item_id=str(item.id),
                error_type=type(exc).__name__,
                error_msg=str(exc)[:200],
            )
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
        item.attributes = tags.attributes
        item.needs_review = tags.confidence_scores.min_confidence < 0.7
        item.status = "ready"

        await db.commit()
        logger.info("item.ingested", item_id=str(item.id), category=item.category)


async def _on_startup(ctx: dict[str, Any]) -> None:
    logger.info("worker.startup", functions=[f.__name__ for f in WorkerSettings.functions])


async def _on_shutdown(ctx: dict[str, Any]) -> None:
    logger.info("worker.shutdown")


async def _stalled_sweeper(ctx: dict[str, Any]) -> None:
    """Periodic safety net: any row stuck `pending` for >10 minutes is moved
    to `failed`. Without this, a worker that crashed mid-job leaves the item
    in pending forever and the mobile UI polls indefinitely.
    """
    from datetime import UTC, datetime, timedelta

    from app.models.tryons import OutfitTryon, TryonStatus

    cutoff = datetime.now(UTC) - timedelta(minutes=10)
    async with SessionLocal() as db:
        items = (
            await db.execute(
                select(WardrobeItem).where(
                    WardrobeItem.status == "pending",
                    WardrobeItem.created_at < cutoff,
                )
            )
        ).scalars().all()
        for it in items:
            it.status = "failed"
            logger.warning("sweeper.item_stalled", item_id=str(it.id))
        tryons = (
            await db.execute(
                select(OutfitTryon).where(
                    OutfitTryon.status == TryonStatus.pending,
                    OutfitTryon.created_at < cutoff,
                )
            )
        ).scalars().all()
        for t in tryons:
            t.status = TryonStatus.failed
            t.error_message = "render timed out (worker crash recovery)"
            logger.warning("sweeper.tryon_stalled", tryon_id=str(t.id))
        if items or tryons:
            await db.commit()


class WorkerSettings:
    functions: ClassVar[list[Any]] = [ingest_item, compose_outfit_image, tryon_outfit]
    # Stalled-row sweeper runs every 2 minutes — its job is to mop up after the
    # worker itself (or Redis) hiccups and leaves a row stuck in pending.
    cron_jobs: ClassVar[list[Any]] = []  # populated below
    # Longer connect-timeout absorbs flaky Docker-bridge Redis reconnects on macOS.
    # Each Claude/Replicate call can take 30-60s — Arq's default 300s job timeout is fine.
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    # Resilient connection: retry on transient drops so a 1-2s Docker network
    # blip doesn't kill the worker.
    redis_settings.conn_retries = 5
    redis_settings.conn_retry_delay = 2
    job_timeout = 300  # seconds, per job (premium bg-removal can be 60s+)
    max_tries = 3
    keep_result = 300
    on_startup = _on_startup
    on_shutdown = _on_shutdown
    # Health pings every 60s — Arq logs `j_complete / j_failed / queued` lines
    # we can scrape if anything degrades.
    health_check_interval = 60


# Register the periodic sweeper after WorkerSettings is defined so it can
# reference the class attributes.
try:
    from arq.cron import cron

    # Every 2 minutes (sweep stalled rows). Building the set explicitly keeps
    # the line under ruff's 100-char limit.
    _EVERY_2_MIN = set(range(0, 60, 2))
    WorkerSettings.cron_jobs = [cron(_stalled_sweeper, minute=_EVERY_2_MIN)]
except ImportError:
    # arq.cron not available in older arq — workers will run without the sweeper.
    logger.warning("worker.cron_unavailable")
