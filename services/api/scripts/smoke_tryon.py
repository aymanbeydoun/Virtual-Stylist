"""End-to-end smoke test for the virtual try-on pipeline.

Pulls the user's actual base photo + one ready item from the DB, runs them
through the ProductionGateway's `try_on_outfit`, writes the result to disk.

Whoever's testing should then **open the output and confirm it's actually
them** — not a generic generated person. That visual check is the only
acceptance gate that catches identity drift.

Backend selected by env:
  - MODAL_TRYON_ENDPOINT set in .env → FitDiT on Modal (~$0.005/garment)
  - else → IDM-VTON on Replicate (~$0.06/garment)

Run with:
  cd services/api && uv run scripts/smoke_tryon.py [email]
  # email defaults to dev+ayman@virtual-stylist.local
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from sqlalchemy import select

from app.core.storage import get_storage
from app.db import SessionLocal
from app.models.users import User
from app.models.wardrobe import WardrobeItem
from app.services.model_gateway import TryonInput, get_model_gateway


async def main() -> int:
    email = sys.argv[1] if len(sys.argv) > 1 else "dev+ayman@virtual-stylist.local"

    async with SessionLocal() as db:
        user = (
            await db.execute(select(User).where(User.email == email))
        ).scalar_one_or_none()
        if not user:
            print(f"ERROR: no user with email {email!r}", file=sys.stderr)
            return 1
        if not user.base_photo_key:
            print(f"ERROR: user {email!r} has no base photo", file=sys.stderr)
            return 1

        # Pick the first ready upper-body item for a fast smoke test.
        item = (
            await db.execute(
                select(WardrobeItem).where(
                    WardrobeItem.owner_id == user.id,
                    WardrobeItem.status == "ready",
                    WardrobeItem.deleted_at.is_(None),
                    WardrobeItem.category.like("%.tops.%"),
                )
                .limit(1)
            )
        ).scalar_one_or_none()
        if not item:
            print(
                f"ERROR: user {email!r} has no ready top to try on",
                file=sys.stderr,
            )
            return 1

    storage = get_storage()
    person_bytes = await storage.read_bytes(user.base_photo_key)
    garment_bytes = await storage.read_bytes(
        item.cutout_image_key or item.raw_image_key
    )
    desc = (item.category or "").replace(".", " ")
    if item.colors:
        desc = f"{item.colors[0].name} {desc}"

    print(f"Person photo: {user.base_photo_key} ({len(person_bytes):,} bytes)")
    print(f"Garment: {item.category} ({len(garment_bytes):,} bytes) — {desc!r}")
    print("Calling IDM-VTON (this takes 15-25s)…")

    gateway = get_model_gateway()
    result = await gateway.try_on_outfit(
        person_image=person_bytes,
        garments=[
            TryonInput(image_bytes=garment_bytes, slot="top", description=desc),
        ],
    )

    out_dir = Path("smoke_tryon_output")
    out_dir.mkdir(exist_ok=True)
    person_path = out_dir / "input_person.jpg"
    person_path.write_bytes(person_bytes)
    garment_path = out_dir / "input_garment.png"
    garment_path.write_bytes(garment_bytes)
    result_path = out_dir / "result.jpg"
    result_path.write_bytes(result.image_bytes)

    from app.config import get_settings
    s = get_settings()
    backend = "modal-fitdit" if s.modal_tryon_endpoint else "replicate-idm-vton"
    print(f"\nDone. backend={backend} model_id={result.model_id}")
    print(f"  Input person : {person_path}")
    print(f"  Input garment: {garment_path}")
    print(f"  Try-on result: {result_path}")
    print("\nOpen the three files side-by-side and verify the result is the")
    print("SAME PERSON as the input, now wearing the garment.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
