"""Base-photo upload + virtual try-on endpoints."""
import uuid
from typing import Annotated

from arq import create_pool
from arq.connections import RedisSettings
from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.auth import CurrentUser
from app.core.storage import get_storage, new_object_key
from app.db import get_db
from app.models.family import FamilyMember
from app.models.outfits import Outfit
from app.models.tryons import OutfitTryon, TryonStatus
from app.models.users import OwnerKind, User
from app.schemas.tryon import (
    ANGLES,
    BasePhotoCommit,
    BasePhotoOut,
    BasePhotoSetOut,
    BasePhotoUploadUrlRequest,
    BasePhotoUploadUrlResponse,
    TryonOut,
    TryonSetOut,
)

router = APIRouter()


async def _resolve_owner_for_base_photo(
    db: AsyncSession,
    user: User,
    owner_kind: OwnerKind,
    owner_id: uuid.UUID | None,
) -> tuple[User | FamilyMember, OwnerKind, uuid.UUID]:
    """Return the row the base photo should attach to (User or FamilyMember).

    Family members must be the requesting user's. The returned row already has
    base_photo_key as a mutable column on it.
    """
    if owner_kind == OwnerKind.user:
        return user, OwnerKind.user, user.id
    if not owner_id:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "owner_id required for family_member owner"
        )
    member = (
        await db.execute(
            select(FamilyMember).where(
                FamilyMember.id == owner_id, FamilyMember.guardian_id == user.id
            )
        )
    ).scalar_one_or_none()
    if not member:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "not your family member")
    return member, OwnerKind.family_member, member.id


@router.post("/base-photo/upload-url", response_model=BasePhotoUploadUrlResponse)
async def create_base_photo_upload_url(
    body: BasePhotoUploadUrlRequest,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> BasePhotoUploadUrlResponse:
    _, _, owner_id = await _resolve_owner_for_base_photo(db, user, body.owner_kind, body.owner_id)
    storage = get_storage()
    key = new_object_key(prefix=f"base-photo/{owner_id}", content_type=body.content_type)
    url, expires = await storage.signed_upload_url(key, body.content_type)
    return BasePhotoUploadUrlResponse(upload_url=url, object_key=key, expires_at=expires)


@router.post("/base-photo", response_model=BasePhotoOut)
async def commit_base_photo(
    body: BasePhotoCommit,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> BasePhotoOut:
    """Commit a base photo. Supports both single-angle (legacy) and per-angle.

    When `angle` is set (must be one of `ANGLES`), the photo is filed in
    `base_photo_keys[angle]`. When the angle is "front" (or `angle` is None
    for back-compat with the old mobile build), `base_photo_key` is ALSO
    mirrored so any code path that reads the legacy column still works.
    """
    if body.angle is not None and body.angle not in ANGLES:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"angle must be one of {list(ANGLES)}",
        )

    owner_row, _, _ = await _resolve_owner_for_base_photo(
        db, user, body.owner_kind, body.owner_id
    )
    angle = body.angle or "front"
    # SQLAlchemy needs a fresh dict to detect the JSONB mutation.
    keys = dict(owner_row.base_photo_keys or {})
    keys[angle] = body.object_key
    owner_row.base_photo_keys = keys
    if angle == "front":
        owner_row.base_photo_key = body.object_key
    await db.commit()
    return BasePhotoOut(base_photo_key=body.object_key)


@router.get("/base-photo", response_model=BasePhotoOut)
async def get_base_photo(
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    owner_kind: OwnerKind = OwnerKind.user,
    owner_id: uuid.UUID | None = None,
) -> BasePhotoOut:
    owner_row, _, _ = await _resolve_owner_for_base_photo(db, user, owner_kind, owner_id)
    return BasePhotoOut(base_photo_key=owner_row.base_photo_key)


@router.get("/base-photos", response_model=BasePhotoSetOut)
async def get_base_photo_set(
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    owner_kind: OwnerKind = OwnerKind.user,
    owner_id: uuid.UUID | None = None,
) -> BasePhotoSetOut:
    """Return every uploaded angle for the owner."""
    owner_row, _, _ = await _resolve_owner_for_base_photo(db, user, owner_kind, owner_id)
    return BasePhotoSetOut(base_photo_keys=owner_row.base_photo_keys or {})


@router.post(
    "/outfits/{outfit_id}/tryon",
    response_model=TryonSetOut,
    status_code=status.HTTP_202_ACCEPTED,
)
async def request_tryon(
    outfit_id: Annotated[uuid.UUID, Path()],
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    all_angles: bool = False,
) -> TryonSetOut:
    """Kick off virtual try-on render(s).

    By default renders the FRONT angle only (or whichever single angle the
    user has uploaded). A full-outfit IDM-VTON render is ~60-90s for one
    angle — fanning out to 4 angles ballooned to 4-12 minutes in production
    and stacked behind Replicate's serialized semaphore, so the queue
    backed up beyond the user's patience.

    Pass `?all_angles=true` to render every uploaded angle. The mobile
    exposes this as a "Render all 4 angles" CTA shown once the front is
    ready — opt-in, not default.

    Returns 202 with the set of pending tryon rows.
    """
    outfit = (
        await db.execute(select(Outfit).where(Outfit.id == outfit_id))
    ).scalar_one_or_none()
    if not outfit:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no such outfit")

    # Authorise + locate the owner's full base-photo set.
    if outfit.owner_kind == OwnerKind.user:
        if outfit.owner_id != user.id:
            raise HTTPException(status.HTTP_403_FORBIDDEN)
        base_photo_keys = dict(user.base_photo_keys or {})
        legacy_key = user.base_photo_key
    else:
        member = (
            await db.execute(
                select(FamilyMember).where(
                    FamilyMember.id == outfit.owner_id,
                    FamilyMember.guardian_id == user.id,
                )
            )
        ).scalar_one_or_none()
        if not member:
            raise HTTPException(status.HTTP_403_FORBIDDEN)
        base_photo_keys = dict(member.base_photo_keys or {})
        legacy_key = member.base_photo_key

    # Mirror the legacy single-photo column into the dict if it isn't there
    # yet (covers users created before the multiangle migration backfill).
    if legacy_key and "front" not in base_photo_keys:
        base_photo_keys["front"] = legacy_key

    if not base_photo_keys:
        raise HTTPException(
            status.HTTP_412_PRECONDITION_FAILED,
            "upload a base photo first (POST /tryon/base-photo)",
        )

    # By default: render ONE angle (front, or the first available). Multi-
    # angle is opt-in via ?all_angles=true.
    if all_angles:
        target_angles = [a for a in ANGLES if a in base_photo_keys]
    else:
        # Prefer front; else whatever single angle the user uploaded.
        if "front" in base_photo_keys:
            target_angles = ["front"]
        else:
            first = next(iter(base_photo_keys.keys()))
            target_angles = [first]

    tryons: list[OutfitTryon] = []
    for angle in target_angles:
        key = base_photo_keys[angle]
        t = OutfitTryon(
            outfit_id=outfit_id,
            base_photo_key=key,
            angle=angle,
            status=TryonStatus.pending,
        )
        db.add(t)
        tryons.append(t)
    await db.commit()
    for t in tryons:
        await db.refresh(t)

    # Enqueue renders. Each one runs as its own Arq job → they run in parallel
    # on the worker pool. Inline fallback for tests/single-process dev.
    settings = get_settings()
    if settings.ingest_inline:
        from app.services.tryon_worker import tryon_outfit as do_tryon

        for t in tryons:
            await do_tryon({}, str(t.id))
        for t in tryons:
            await db.refresh(t)
    else:
        try:
            redis = await create_pool(RedisSettings.from_dsn(settings.redis_url))
            for t in tryons:
                await redis.enqueue_job("tryon_outfit", str(t.id))
            await redis.aclose()
        except Exception:
            from app.services.tryon_worker import tryon_outfit as do_tryon

            for t in tryons:
                await do_tryon({}, str(t.id))
            for t in tryons:
                await db.refresh(t)

    return TryonSetOut(renders=[TryonOut.model_validate(t) for t in tryons])


async def _authorise_outfit_access(
    db: AsyncSession, outfit_id: uuid.UUID, user: User
) -> Outfit:
    outfit = (
        await db.execute(select(Outfit).where(Outfit.id == outfit_id))
    ).scalar_one_or_none()
    if not outfit:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no such outfit")
    if outfit.owner_kind == OwnerKind.user and outfit.owner_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN)
    if outfit.owner_kind == OwnerKind.family_member:
        member = (
            await db.execute(
                select(FamilyMember).where(
                    FamilyMember.id == outfit.owner_id,
                    FamilyMember.guardian_id == user.id,
                )
            )
        ).scalar_one_or_none()
        if not member:
            raise HTTPException(status.HTTP_403_FORBIDDEN)
    return outfit


@router.get("/outfits/{outfit_id}/tryon", response_model=TryonOut)
async def latest_tryon(
    outfit_id: Annotated[uuid.UUID, Path()],
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> OutfitTryon:
    """Back-compat: returns the most-recent single tryon row.

    New clients should use GET /outfits/{outfit_id}/tryons (plural) to get
    all per-angle renders. This endpoint preferentially returns the "front"
    render if one exists, falling back to whatever came last.
    """
    await _authorise_outfit_access(db, outfit_id, user)

    # Group by tryon-batch (created_at within ~60s of each other belongs to
    # the same request). Easiest: pick the latest render set, then pick the
    # front view inside it.
    latest_batch = (
        await db.execute(
            select(OutfitTryon)
            .where(OutfitTryon.outfit_id == outfit_id)
            .order_by(OutfitTryon.created_at.desc())
            .limit(4)
        )
    ).scalars().all()
    if not latest_batch:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no tryon yet")
    for t in latest_batch:
        if t.angle == "front":
            return t
    return latest_batch[0]


@router.get("/outfits/{outfit_id}/tryons", response_model=TryonSetOut)
async def latest_tryon_set(
    outfit_id: Annotated[uuid.UUID, Path()],
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TryonSetOut:
    """Return the most-recent set of tryon renders (one per angle).

    Used by the multi-angle carousel on the outfit detail screen.
    """
    await _authorise_outfit_access(db, outfit_id, user)

    # Pull the most recent batch — up to 4 renders sharing roughly the same
    # created_at. We grab the latest 4 rows (the per-angle fan-out caps at 4)
    # and group by the batch identifier: their created_at clustering.
    rows = (
        await db.execute(
            select(OutfitTryon)
            .where(OutfitTryon.outfit_id == outfit_id)
            .order_by(OutfitTryon.created_at.desc())
            .limit(4)
        )
    ).scalars().all()
    if not rows:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no tryon yet")

    # Sort to playback order so the mobile receives them already sequenced.
    angle_index = {a: i for i, a in enumerate(ANGLES)}
    sorted_rows = sorted(
        rows,
        key=lambda t: angle_index.get(t.angle or "", 99),
    )
    return TryonSetOut(renders=[TryonOut.model_validate(t) for t in sorted_rows])
