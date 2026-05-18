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
from app.services.preflight import preflight_check
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


# Fabrics/transparency values where the standard bg-remover routinely loses
# detail. Re-checked against Claude's tagging taxonomy in `_TAGGING_SYSTEM`.
_DELICATE_FABRICS = {"silk", "linen", "lace", "fur", "mesh", "cashmere"}
_DELICATE_TRANSPARENCY = {"semi_sheer", "sheer"}
# When Claude isn't sure what the item even is, the cutout is also likely
# imperfect — kick to premium so the user at least gets a clean edge.
_LOW_CONFIDENCE = 0.7


def _should_upgrade_to_premium(tags: object) -> bool:
    """Decide whether this item warrants the premium bg-removal tier.

    Pure function over the tagging result so it's easy to test and to tune.
    Triggers when ANY of:
      - fabric is one of silk/linen/lace/fur/mesh/cashmere (hair-like edges)
      - transparency is semi_sheer or sheer (alpha matting helps a lot)
      - category-or-pattern confidence is below 0.7 (cutout likely messy too)
      - embellishments include lace or fringe (fine, detached detail)
    """
    attrs = getattr(tags, "attributes", None) or {}
    fabric = str(attrs.get("fabric", "")).lower()
    transparency = str(attrs.get("transparency", "")).lower()
    embellishments_raw = attrs.get("embellishments") or []
    embellishments = (
        {str(e).lower() for e in embellishments_raw}
        if isinstance(embellishments_raw, list)
        else set()
    )
    confidence = getattr(tags, "confidence_scores", None)
    min_conf = getattr(confidence, "min_confidence", 1.0) if confidence else 1.0

    return (
        fabric in _DELICATE_FABRICS
        or transparency in _DELICATE_TRANSPARENCY
        or min_conf < _LOW_CONFIDENCE
        or bool(embellishments & {"lace", "fringe"})
    )


def _premium_reason(tags: object) -> str:
    """Short human-readable reason for the structured log."""
    attrs = getattr(tags, "attributes", None) or {}
    fabric = str(attrs.get("fabric", "")).lower()
    transparency = str(attrs.get("transparency", "")).lower()
    if fabric in _DELICATE_FABRICS:
        return f"delicate_fabric:{fabric}"
    if transparency in _DELICATE_TRANSPARENCY:
        return f"transparency:{transparency}"
    embellishments_raw = attrs.get("embellishments") or []
    if isinstance(embellishments_raw, list):
        for e in embellishments_raw:
            if str(e).lower() in {"lace", "fringe"}:
                return f"embellishment:{str(e).lower()}"
    return "low_confidence"


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
            item.failure_reason = "Couldn't decode the photo. Try a different file."
            await db.commit()
            return

        # Preflight: cheap on-server check that catches obvious blur / tiny
        # images before we spend Claude + Replicate credits on them.
        pf = preflight_check(raw)
        if not pf.ok:
            item.status = "failed"
            item.failure_reason = pf.reason
            await db.commit()
            logger.info("item.preflight_rejected", item_id=str(item.id), reason=pf.reason)
            return

        # Zero-shot clothing-vs-not gate. Catches cat photos / landscapes /
        # screenshots BEFORE we burn the bg-removal + tagging credits. ~$0.0003
        # Haiku call, sub-second. Fails open on classifier error.
        try:
            clf = await gateway.classify_clothing(raw)
        except Exception as exc:
            if _is_transient(exc):
                logger.info(
                    "item.classifier_retry",
                    item_id=str(item.id),
                    error_type=type(exc).__name__,
                )
                raise
            logger.warning(
                "item.classifier_failed_open",
                item_id=str(item.id),
                error_type=type(exc).__name__,
            )
            clf = None
        if clf is not None and not clf.is_clothing:
            item.status = "failed"
            item.failure_reason = clf.reason or (
                "This doesn't look like a clothing item."
            )
            await db.commit()
            logger.info(
                "item.classifier_rejected",
                item_id=str(item.id),
                detected_label=clf.detected_label,
                confidence=clf.confidence,
            )
            return

        try:
            cutout = await gateway.remove_background(
                raw, quality_tier=item.quality_tier or "standard"
            )
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
            # Surface a useful reason to the mobile. We don't echo the full
            # provider error (often technical) — just enough for the user to
            # know to retake.
            err_msg = str(exc).lower()
            if "could not process image" in err_msg or "invalid_request" in err_msg:
                item.failure_reason = (
                    "The AI couldn't analyse this image. Try a clearer photo."
                )
            elif "payment" in err_msg or "402" in err_msg:
                item.failure_reason = (
                    "Tagging service is over budget. Try again in a moment."
                )
            else:
                item.failure_reason = "Couldn't tag this photo. Tap to retry or delete."
            await db.commit()
            return

        # ----- Auto premium-tier upgrade -----------------------------------
        # The standard bg-remover (851-labs) is fast + cheap but struggles on
        # hair, lace, mesh, fringe, and sheer/translucent fabrics. Once Claude
        # has tagged the item, we know whether it falls into one of those
        # buckets — if so, re-run the cutout with the premium model and
        # replace the saved cutout. Costs ~$0.02 extra, only on the ~15% of
        # items that actually benefit.
        needs_premium = (
            (item.quality_tier or "standard") == "standard"
            and _should_upgrade_to_premium(tags)
        )
        if needs_premium:
            try:
                logger.info(
                    "item.premium_upgrade",
                    item_id=str(item.id),
                    reason=_premium_reason(tags),
                )
                premium_cutout = await gateway.remove_background(
                    raw, quality_tier="premium"
                )
                # Only overwrite if the premium model actually produced
                # something different from the raw (gateway returns the
                # raw on failure).
                if premium_cutout != raw:
                    await storage.write_bytes(cutout_key, premium_cutout)
                    item.quality_tier = "premium"
            except Exception as exc:
                # Non-fatal — keep the standard cutout we already saved.
                logger.warning(
                    "item.premium_upgrade_failed",
                    item_id=str(item.id),
                    error_type=type(exc).__name__,
                )

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
