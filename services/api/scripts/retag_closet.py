"""Re-run real Claude Vision tagging over every item in a user's closet.

The original seed_100_closet.py used hardcoded pre-tags — that gave items
like a red maxi dress tagged as "womens.bottoms.trousers" because the
script blindly assigned the next category in its list to whatever Pexels
photo loaded. The cure is to run the actual ingest pipeline:

  preflight → clothing classifier (Haiku) → bg-removal (Replicate)
  → Claude Vision tagging → CLIP embedding → optional premium upgrade

Each item costs ~$0.013 and takes ~10-20s in the worker. 100 items =
~$1.30 and 15-30 min wall-time (Replicate semaphore serializes).

Usage:
  cd services/api && uv run python scripts/retag_closet.py
"""
from __future__ import annotations

import argparse
import asyncio
import sys
import uuid
from pathlib import Path

from arq import create_pool
from arq.connections import RedisSettings
from sqlalchemy import select, update

from app.config import get_settings
from app.db import SessionLocal
from app.models.wardrobe import WardrobeItem

AYMAN_UUID = uuid.UUID("85864e68-d0b2-b091-8586-4e69b35e1551")


async def main(user_id: uuid.UUID) -> int:
    settings = get_settings()
    async with SessionLocal() as db:
        items = (
            await db.execute(
                select(WardrobeItem).where(
                    WardrobeItem.owner_id == user_id,
                    WardrobeItem.deleted_at.is_(None),
                )
            )
        ).scalars().all()
        if not items:
            print("No items found for user.")
            return 1

        # Reset every item to pending + clear all derived tags.
        # raw_image_key stays — the photo on disk is the source of truth and
        # the ingest pipeline will derive everything else from it.
        await db.execute(
            update(WardrobeItem)
            .where(
                WardrobeItem.owner_id == user_id,
                WardrobeItem.deleted_at.is_(None),
            )
            .values(
                status="pending",
                category=None,
                colors=[],
                pattern=None,
                formality=None,
                seasonality=[],
                attributes={},
                cutout_image_key=None,
                thumbnail_key=None,
                failure_reason=None,
                needs_review=False,
                quality_tier="standard",
            )
        )
        await db.commit()
        print(f"Reset {len(items)} items to pending.")

    # Enqueue ingest jobs.
    redis = await create_pool(RedisSettings.from_dsn(settings.redis_url))
    try:
        for it in items:
            await redis.enqueue_job("ingest_item", str(it.id))
    finally:
        await redis.aclose()
    print(f"Enqueued {len(items)} ingest jobs.")
    print("")
    print("Monitor:")
    print("  tail -f /tmp/arq-worker.log")
    print("Each item takes ~10-20s. 100 items ≈ 15-30 min total.")
    return 0


def cli() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--user-id", type=str, default=str(AYMAN_UUID))
    args = parser.parse_args()
    return asyncio.run(main(uuid.UUID(args.user_id)))


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    raise SystemExit(cli())
