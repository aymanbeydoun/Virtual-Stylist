"""Seed a large, hand-curated demo wardrobe for the 'ayman' dev user.

Pre-tags every item (category, colors, formality, seasonality, pattern) so
no Claude or Replicate calls are needed — the seed is instant and free.
Items land in status='ready' immediately.

Usage:
    cd services/api
    uv run python scripts/seed_demo_closet.py
    # add --replace to wipe the user's closet first
    # add --bg-removal to queue Replicate bg-removal for each item (slower, ~$1)

Default user UUID is the hash of nickname 'ayman' (see apps/mobile/src/state/auth.ts).
Pass --user-id <uuid> to seed a different user.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import sys
import uuid
from pathlib import Path

import httpx
import structlog
from sqlalchemy import delete, select

from app.config import get_settings
from app.core.storage import get_storage
from app.db import SessionLocal
from app.models.users import OwnerKind, User, UserRole
from app.models.wardrobe import Pattern, WardrobeItem
from app.schemas.common import ColorTag, ConfidenceScores

logger = structlog.get_logger()

AYMAN_UUID = uuid.UUID("85864e68-d0b2-b091-8586-4e69b35e1551")

# Curated apparel catalogue. Each tuple is:
#   (slug, unsplash_photo_id, category, pattern, primary_colors, formality, seasonality)
#
# Categories follow the convention <gender>.<group>.<subcategory>:
#   gender: mens | womens | kids | accessories
#   group:  tops | bottoms | dresses | outerwear | shoes | accessories | jewelry
#
# Photo IDs come from public Unsplash. If a URL 404s the script logs + skips.
# To add items, append a tuple. To re-run cleanly use --replace.
CATALOGUE: list[tuple[str, str, str, str, list[tuple[str, str]], int, list[str]]] = [
    # ---- MENS TOPS ----
    ("mens-white-tee", "1521572163474-6864f9cf17ab", "mens.tops.t-shirt", "solid",
     [("white", "#F2F2F2")], 2, ["spring", "summer", "fall"]),
    ("mens-black-tee", "1583743814966-8936f5b7be1a", "mens.tops.t-shirt", "solid",
     [("black", "#1a1a1a")], 2, ["spring", "summer", "fall"]),
    ("mens-grey-hoodie", "1556821840-3a63f95609a7", "mens.tops.hoodie", "solid",
     [("heather grey", "#8a8a8a")], 2, ["fall", "winter", "spring"]),
    ("mens-oxford-blue", "1602810318383-e386cc2a3ccf", "mens.tops.shirt", "solid",
     [("oxford blue", "#7b9eb5")], 6, ["spring", "summer", "fall"]),
    ("mens-white-oxford", "1598033129183-c4f50c736f10", "mens.tops.shirt", "solid",
     [("white", "#FAFAFA")], 6, ["spring", "summer", "fall", "winter"]),
    ("mens-striped-sweater", "1591047139829-d91aecb6caea", "mens.tops.sweater", "stripe",
     [("navy", "#1a2840"), ("white", "#f5f5f5")], 4, ["fall", "winter"]),
    ("mens-flannel-shirt", "1604644401890-0bd678c83788", "mens.tops.shirt", "plaid",
     [("red", "#a83232"), ("black", "#1a1a1a")], 3, ["fall", "winter"]),
    ("mens-polo-navy", "1622445275576-721325763afe", "mens.tops.polo", "solid",
     [("navy", "#1a2840")], 5, ["spring", "summer"]),
    ("mens-knit-cream", "1620799140408-edc6dcb6d633", "mens.tops.sweater", "solid",
     [("cream", "#f0e6d2")], 5, ["fall", "winter"]),
    # ---- MENS BOTTOMS ----
    ("mens-blue-jeans", "1542272604-787c3835535d", "mens.bottoms.jeans", "solid",
     [("medium blue denim", "#5a7a9a")], 3, ["spring", "summer", "fall", "winter"]),
    ("mens-black-jeans", "1604176354204-9268737828e4", "mens.bottoms.jeans", "solid",
     [("black", "#1a1a1a")], 3, ["spring", "fall", "winter"]),
    ("mens-khaki-chinos", "1473966968600-fa801b869a1a", "mens.bottoms.chinos", "solid",
     [("khaki", "#b59f7b")], 5, ["spring", "summer", "fall"]),
    ("mens-grey-trousers", "1593030761757-71fae45fa0e7", "mens.bottoms.trousers", "solid",
     [("charcoal", "#4a4a52")], 7, ["spring", "fall", "winter"]),
    ("mens-shorts-navy", "1605518216938-7c31b7b14ad0", "mens.bottoms.shorts", "solid",
     [("navy", "#1a2840")], 2, ["summer"]),
    ("mens-joggers-grey", "1552902865-b72c031ac5ea", "mens.bottoms.joggers", "solid",
     [("grey", "#7a7a7a")], 1, ["fall", "winter", "spring"]),
    # ---- MENS OUTERWEAR ----
    ("mens-bomber-terra", "1591047139829-d91aecb6caea", "mens.outerwear.bomber-jacket", "solid",
     [("terracotta", "#b8694a")], 4, ["spring", "fall"]),
    ("mens-denim-jacket", "1591047139831-fbb1f2cc6d9a", "mens.outerwear.jacket", "solid",
     [("denim blue", "#5a7a9a")], 4, ["spring", "fall"]),
    ("mens-trench-camel", "1551803091-e20673f15770", "mens.outerwear.coat", "solid",
     [("camel", "#b89770")], 7, ["fall", "winter", "spring"]),
    ("mens-puffer-black", "1551488831-00ddcb6c6bd3", "mens.outerwear.jacket", "solid",
     [("black", "#1a1a1a")], 3, ["winter"]),
    ("mens-blazer-navy", "1594938298603-c8148c4dae35", "mens.outerwear.blazer", "solid",
     [("navy", "#1a2840")], 8, ["spring", "fall", "winter"]),
    # ---- MENS SHOES ----
    ("mens-white-sneakers", "1542291026-7eec264c27ff", "mens.shoes.sneaker", "solid",
     [("white", "#f5f2ef")], 3, ["spring", "summer", "fall"]),
    ("mens-red-sneakers", "1595950653106-6c9ebd614d3a", "mens.shoes.sneaker", "solid",
     [("crimson", "#c0201a")], 2, ["spring", "summer", "fall", "winter"]),
    ("mens-loafers-brown", "1605812860427-4024433a70fd", "mens.shoes.loafer", "solid",
     [("cognac brown", "#8a5a3a")], 7, ["spring", "fall", "winter"]),
    ("mens-chelsea-black", "1614252369475-531eba835eb1", "mens.shoes.chelsea-boot", "solid",
     [("black", "#1a1a1a")], 7, ["fall", "winter", "spring"]),
    ("mens-runners-grey", "1606107557195-0e29a4b5b4aa", "mens.shoes.sneaker", "solid",
     [("grey", "#a8a8a8")], 2, ["spring", "summer", "fall"]),
    # ---- WOMENS TOPS ----
    ("womens-white-tee", "1581655353564-df123a1eb820", "womens.tops.t-shirt", "solid",
     [("white", "#FAFAFA")], 2, ["spring", "summer", "fall"]),
    ("womens-silk-blouse", "1503342217505-b0a15ec3261c", "womens.tops.blouse", "solid",
     [("ivory", "#f0ebe1")], 6, ["spring", "summer", "fall"]),
    ("womens-cashmere-knit", "1576566588028-4147f3842f27", "womens.tops.sweater", "solid",
     [("oatmeal", "#d9c9b3")], 5, ["fall", "winter"]),
    ("womens-black-bodysuit", "1554568218-0f1715e72254", "womens.tops.bodysuit", "solid",
     [("black", "#1a1a1a")], 5, ["spring", "summer", "fall", "winter"]),
    ("womens-striped-tee", "1620799140188-3b2a02fd9a77", "womens.tops.t-shirt", "stripe",
     [("white", "#FAFAFA"), ("navy", "#1a2840")], 3, ["spring", "summer", "fall"]),
    ("womens-sweatshirt", "1499951360447-b19be8fe80f5", "womens.tops.sweatshirt", "solid",
     [("white", "#f5f5f5")], 3, ["fall", "winter", "spring"]),
    # ---- WOMENS BOTTOMS ----
    ("womens-skinny-jeans", "1541099649105-f69ad21f3246", "womens.bottoms.jeans", "solid",
     [("dark wash", "#2c3a52")], 3, ["spring", "fall", "winter"]),
    ("womens-mom-jeans", "1582418702059-97ebafb35d09", "womens.bottoms.jeans", "solid",
     [("light blue", "#7b9bb5")], 3, ["spring", "summer", "fall"]),
    ("womens-leather-leggings", "1594633312681-425c7b97ccd1", "womens.bottoms.leggings", "solid",
     [("black", "#1a1a1a")], 5, ["fall", "winter"]),
    ("womens-pleated-skirt", "1583496661160-fb5886a13d44", "womens.bottoms.skirt", "solid",
     [("camel", "#b89770")], 6, ["fall", "winter"]),
    ("womens-tailored-trousers", "1594633312681-425c7b97ccd1", "womens.bottoms.trousers", "solid",
     [("charcoal", "#4a4a52")], 7, ["spring", "fall", "winter"]),
    # ---- WOMENS DRESSES ----
    ("womens-midi-black", "1539109136881-3be0616acf4b", "womens.dresses.midi", "solid",
     [("black", "#1a1a1a")], 7, ["spring", "summer", "fall"]),
    ("womens-floral-summer", "1572804013309-59a88b7e92f1", "womens.dresses.midi", "floral",
     [("blush", "#e8c8c0"), ("sage", "#8aa080")], 4, ["spring", "summer"]),
    ("womens-slip-dress", "1490481651871-ab68de25d43d", "womens.dresses.slip", "solid",
     [("champagne", "#d8c4a0")], 8, ["spring", "summer", "fall"]),
    ("womens-knit-dress", "1571513722275-4b41940f54b8", "womens.dresses.knit", "solid",
     [("rust", "#a85a3a")], 5, ["fall", "winter"]),
    # ---- WOMENS OUTERWEAR ----
    ("womens-trench-beige", "1591047139756-eb04ae9deaa6", "womens.outerwear.trench", "solid",
     [("beige", "#c9b89a")], 7, ["spring", "fall"]),
    ("womens-leather-jacket", "1551028719-00167b16eac5", "womens.outerwear.jacket", "solid",
     [("black", "#1a1a1a")], 4, ["spring", "fall", "winter"]),
    ("womens-blazer-cream", "1591047139756-eb04ae9deaa6", "womens.outerwear.blazer", "solid",
     [("cream", "#f0e6d2")], 7, ["spring", "fall", "winter"]),
    ("womens-puffer-pink", "1604644401890-0bd678c83788", "womens.outerwear.jacket", "solid",
     [("dusty pink", "#d9a8a8")], 3, ["winter"]),
    # ---- WOMENS SHOES ----
    ("womens-white-sneakers", "1595950653106-6c9ebd614d3a", "womens.shoes.sneaker", "solid",
     [("white", "#f5f2ef")], 3, ["spring", "summer", "fall"]),
    ("womens-ankle-boots", "1605812860427-4024433a70fd", "womens.shoes.boot", "solid",
     [("black", "#1a1a1a")], 6, ["fall", "winter", "spring"]),
    ("womens-strappy-sandals", "1543163521-1bf539c55dd2", "womens.shoes.sandal", "solid",
     [("nude", "#d8b89a")], 6, ["spring", "summer"]),
    ("womens-stilettos-black", "1543163521-1bf539c55dd2", "womens.shoes.stiletto", "solid",
     [("black", "#1a1a1a")], 8, ["spring", "fall", "winter"]),
    ("womens-flat-loafer", "1614252235316-8c857d38b5f4", "womens.shoes.loafer", "solid",
     [("cognac brown", "#8a5a3a")], 6, ["spring", "fall", "winter"]),
    # ---- ACCESSORIES ----
    ("belt-black-leather", "1624222247344-550fb60583dc", "accessories.belts.leather", "solid",
     [("black", "#1a1a1a")], 5, ["spring", "summer", "fall", "winter"]),
    ("belt-brown-leather", "1624222247344-550fb60583dc", "accessories.belts.leather", "solid",
     [("cognac brown", "#8a5a3a")], 5, ["spring", "summer", "fall", "winter"]),
    ("hat-fedora", "1521369909029-2afed882baee", "accessories.hats.fedora", "solid",
     [("charcoal", "#4a4a52")], 6, ["fall", "winter", "spring"]),
    ("baseball-cap", "1521369909029-2afed882baee", "accessories.hats.cap", "solid",
     [("navy", "#1a2840")], 1, ["spring", "summer"]),
    ("sunglasses-aviator", "1577803645773-f96470509666", "accessories.eyewear.sunglasses", "solid",
     [("gold", "#c9a85a"), ("brown", "#5a3a2a")], 5, ["spring", "summer", "fall"]),
    ("watch-silver", "1524805444758-089113d48a6d", "accessories.jewelry.watch", "solid",
     [("silver", "#c0c0c0")], 6, ["spring", "summer", "fall", "winter"]),
    ("gold-chain", "1611652022419-a9419f74343d", "accessories.jewelry.necklace", "solid",
     [("gold", "#c9a85a")], 5, ["spring", "summer", "fall", "winter"]),
    ("crossbody-bag", "1591561954557-26941169b49e", "accessories.bags.crossbody", "solid",
     [("camel", "#b89770")], 5, ["spring", "summer", "fall"]),
    ("backpack-canvas", "1553062407-98eeb64c6a62", "accessories.bags.backpack", "solid",
     [("olive", "#5a6a3a")], 2, ["spring", "summer", "fall", "winter"]),
]


def _deterministic_id(slug: str) -> uuid.UUID:
    """A stable UUID per slug so re-runs upsert instead of duplicating."""
    h = hashlib.sha1(f"seed:{slug}".encode()).digest()
    return uuid.UUID(bytes=h[:16], version=4)


async def _fetch(client: httpx.AsyncClient, photo_id: str) -> bytes | None:
    url = f"https://images.unsplash.com/photo-{photo_id}?w=900&fm=jpg&q=85"
    try:
        r = await client.get(url, follow_redirects=True, timeout=30.0)
        if r.status_code != 200 or not r.headers.get("content-type", "").startswith("image/"):
            logger.warning("seed.skip", slug=photo_id, status=r.status_code)
            return None
        return r.content
    except Exception as exc:
        logger.warning("seed.skip", photo_id=photo_id, error=str(exc)[:120])
        return None


async def main(user_id: uuid.UUID, replace: bool, queue_bg_removal: bool) -> int:
    settings = get_settings()
    storage = get_storage()

    async with SessionLocal() as db:
        # Ensure the user row exists.
        existing_user = (
            await db.execute(select(User).where(User.id == user_id))
        ).scalar_one_or_none()
        if not existing_user:
            db.add(
                User(
                    id=user_id,
                    email=f"dev+{user_id}@virtual-stylist.local",
                    role=UserRole.guardian,
                    display_name="Seed User",
                )
            )
            await db.commit()
            logger.info("seed.created_user", user_id=str(user_id))

        if replace:
            res = await db.execute(
                delete(WardrobeItem).where(
                    WardrobeItem.owner_kind == OwnerKind.user,
                    WardrobeItem.owner_id == user_id,
                )
            )
            await db.commit()
            # Async result counts vary by driver; just log success.
            del res
            logger.info("seed.replace_wiped")

        async with httpx.AsyncClient() as http:
            inserted = 0
            skipped = 0
            for slug, photo_id, category, pattern, color_pairs, formality, seasonality in CATALOGUE:
                item_id = _deterministic_id(slug)
                # Idempotent: skip if this seed-id is already in the closet.
                existing = (
                    await db.execute(select(WardrobeItem).where(WardrobeItem.id == item_id))
                ).scalar_one_or_none()
                if existing:
                    skipped += 1
                    continue

                bytes_ = await _fetch(http, photo_id)
                if not bytes_:
                    continue

                raw_key = f"raw/{user_id}/{item_id}.jpg"
                cutout_key = f"cutout/{user_id}/{item_id}.jpg"
                await storage.write_bytes(raw_key, bytes_)
                # Use the same bytes as the cutout — composites will look a bit
                # busy until the optional bg-removal pass upgrades them.
                await storage.write_bytes(cutout_key, bytes_)

                item = WardrobeItem(
                    id=item_id,
                    owner_kind=OwnerKind.user,
                    owner_id=user_id,
                    raw_image_key=raw_key,
                    cutout_image_key=cutout_key,
                    thumbnail_key=cutout_key,
                    category=category,
                    colors=[ColorTag(name=n, hex=h, weight=1.0 / len(color_pairs))
                            for n, h in color_pairs],
                    pattern=Pattern(pattern),
                    formality=formality,
                    seasonality=list(seasonality),
                    embedding=[0.0] * 768,  # zero-vector; similarity degrades but works
                    confidence_scores=ConfidenceScores(
                        root={"category": 1.0, "pattern": 1.0, "color": 1.0}
                    ),
                    needs_review=False,
                    status="ready",
                )
                db.add(item)
                inserted += 1
                if inserted % 10 == 0:
                    await db.commit()
                    logger.info("seed.progress", inserted=inserted)

            await db.commit()
            logger.info("seed.done", inserted=inserted, skipped=skipped)

        if queue_bg_removal:
            from arq import create_pool
            from arq.connections import RedisSettings

            redis = await create_pool(RedisSettings.from_dsn(settings.redis_url))
            new_items = (
                await db.execute(
                    select(WardrobeItem.id).where(
                        WardrobeItem.owner_id == user_id,
                        WardrobeItem.embedding == [0.0] * 768,  # only the seeded ones
                    )
                )
            ).scalars().all()
            for iid in new_items:
                await redis.enqueue_job("ingest_item", str(iid))
            await redis.aclose()
            logger.info("seed.queued_bg_removal", count=len(new_items))

    return 0


def cli() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--user-id", type=str, default=str(AYMAN_UUID))
    parser.add_argument("--replace", action="store_true")
    parser.add_argument("--bg-removal", action="store_true",
                        help="Queue Replicate bg-removal in the background (slow, costs credits).")
    args = parser.parse_args()
    user_id = uuid.UUID(args.user_id)
    return asyncio.run(main(user_id, args.replace, args.bg_removal))


if __name__ == "__main__":
    # Ensure parent dir is on path so `app.*` imports resolve when invoked as
    # `uv run python scripts/seed_demo_closet.py`.
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    raise SystemExit(cli())
