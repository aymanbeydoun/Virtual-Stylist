"""Seed a dev guardian + family + a starter closet so the app shows real data.

Requires a running Postgres (use infra/dev/docker-compose.yaml). The schema
uses ARRAY / JSONB / pgvector columns that don't compile on SQLite.

Usage:
    uv run alembic upgrade head
    uv run python -m scripts.seed [--reset]

Idempotent: re-running upserts the guardian/kid by stable IDs and only inserts
wardrobe items if the closet is empty.
"""
from __future__ import annotations

import argparse
import asyncio
import io
import sys
import uuid

from PIL import Image
from sqlalchemy import select

from app.core.storage import get_storage, new_object_key
from app.db import SessionLocal, engine
from app.models import Base, FamilyMember, KidConsent, User, WardrobeItem
from app.models.family import ConsentMethod, FamilyMemberKind
from app.models.users import OwnerKind, UserRole
from app.models.wardrobe import Pattern
from app.schemas.common import ColorTag, ConfidenceScores

GUARDIAN_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
KID_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")


ADULT_CLOSET = [
    ("womens.tops.blouse", Pattern.stripe, "navy", "#1c2541", 6, ["spring", "fall"]),
    ("womens.tops.blouse", Pattern.solid, "cream", "#f5e1c8", 5, ["spring", "summer"]),
    ("womens.bottoms.jeans", Pattern.solid, "indigo", "#1f3a68", 4, ["spring", "fall", "winter"]),
    ("womens.bottoms.skirt", Pattern.solid, "black", "#0c0c0c", 6, ["fall", "winter"]),
    ("womens.dresses.midi", Pattern.floral, "pink", "#f8a5b1", 7, ["spring", "summer"]),
    ("womens.outerwear.blazer", Pattern.solid, "camel", "#b78a5a", 7, ["spring", "fall"]),
    ("womens.shoes.sneaker", Pattern.solid, "white", "#f4f4f5", 3, ["spring", "summer", "fall"]),
    ("womens.shoes.stiletto", Pattern.solid, "black", "#0c0c0c", 8, ["fall", "winter"]),
    (
        "accessories.belts.leather",
        Pattern.solid,
        "black",
        "#0c0c0c",
        6,
        ["spring", "fall", "winter"],
    ),
    (
        "accessories.jewelry.necklace",
        Pattern.solid,
        "gold",
        "#d4af37",
        6,
        ["spring", "summer", "fall", "winter"],
    ),
]

KID_CLOSET = [
    ("kids.tops.graphic_tee", Pattern.graphic, "blue", "#3b82f6", 1, ["spring", "summer"]),
    ("kids.tops.graphic_tee", Pattern.graphic, "red", "#ef4444", 1, ["spring", "summer"]),
    ("kids.tops.sweater", Pattern.solid, "yellow", "#facc15", 2, ["fall", "winter"]),
    ("kids.bottoms.shorts", Pattern.solid, "navy", "#1e3a8a", 1, ["spring", "summer"]),
    ("kids.bottoms.jeans", Pattern.solid, "indigo", "#1f3a68", 2, ["spring", "fall", "winter"]),
    ("kids.shoes.sneaker", Pattern.solid, "white", "#f4f4f5", 1, ["spring", "summer", "fall"]),
    ("kids.outerwear.jacket", Pattern.solid, "green", "#16a34a", 2, ["fall", "winter"]),
    ("accessories.hats.cap", Pattern.solid, "red", "#ef4444", 1, ["spring", "summer"]),
]


def _solid_image(hex_color: str) -> bytes:
    rgb = tuple(int(hex_color.lstrip("#")[i : i + 2], 16) for i in (0, 2, 4))
    buf = io.BytesIO()
    Image.new("RGB", (256, 256), color=rgb).save(buf, "JPEG", quality=80)
    return buf.getvalue()


async def _ensure_tables() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def seed() -> None:
    storage = get_storage()
    async with SessionLocal() as db:
        guardian = (
            await db.execute(select(User).where(User.id == GUARDIAN_ID))
        ).scalar_one_or_none()
        if not guardian:
            guardian = User(
                id=GUARDIAN_ID,
                email="seed-guardian@virtual-stylist.local",
                role=UserRole.guardian,
                display_name="Seed Guardian",
            )
            db.add(guardian)
            await db.flush()

        kid = (
            await db.execute(select(FamilyMember).where(FamilyMember.id == KID_ID))
        ).scalar_one_or_none()
        if not kid:
            kid = FamilyMember(
                id=KID_ID,
                guardian_id=guardian.id,
                display_name="Ava",
                kind=FamilyMemberKind.kid,
                birth_year=2017,
                kid_mode=True,
            )
            db.add(kid)
            db.add(
                KidConsent(
                    family_member_id=kid.id,
                    guardian_id=guardian.id,
                    consent_method=ConsentMethod.card_check,
                )
            )
            await db.flush()

        async def add_closet(
            owner_kind: OwnerKind,
            owner_id: uuid.UUID,
            closet: list[tuple[str, "Pattern", str, str, int, list[str]]],
        ) -> int:
            existing = (
                await db.execute(
                    select(WardrobeItem).where(
                        WardrobeItem.owner_kind == owner_kind,
                        WardrobeItem.owner_id == owner_id,
                    )
                )
            ).scalars().all()
            if existing:
                return 0
            for category, pattern, color_name, hex_color, formality, seasons in closet:
                image_bytes = _solid_image(hex_color)
                key = new_object_key(prefix=f"raw/{owner_id}", content_type="image/jpeg")
                await storage.write_bytes(key, image_bytes)
                db.add(
                    WardrobeItem(
                        owner_kind=owner_kind,
                        owner_id=owner_id,
                        raw_image_key=key,
                        cutout_image_key=key,
                        thumbnail_key=key,
                        category=category,
                        pattern=pattern,
                        colors=[ColorTag(name=color_name, hex=hex_color, weight=1.0)],
                        formality=formality,
                        seasonality=seasons,
                        coppa_protected=owner_kind == OwnerKind.family_member,
                        status="ready",
                        confidence_scores=ConfidenceScores(
                            root={"category": 1.0, "pattern": 1.0, "color": 1.0}
                        ),
                    )
                )
            return len(closet)

        adult_count = await add_closet(OwnerKind.user, guardian.id, ADULT_CLOSET)
        kid_count = await add_closet(OwnerKind.family_member, kid.id, KID_CLOSET)
        await db.commit()

    print(
        f"Seeded: guardian={GUARDIAN_ID} (+{adult_count} items), "
        f"kid={KID_ID} (+{kid_count} items)."
    )
    print(f"In the mobile dev sign-in, enter: {GUARDIAN_ID}")


async def reset() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true", help="Drop + recreate all tables first")
    args = parser.parse_args()

    if args.reset:
        asyncio.run(reset())
    asyncio.run(_ensure_tables())
    asyncio.run(seed())
    return 0


if __name__ == "__main__":
    sys.exit(main())
