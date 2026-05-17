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
    BasePhotoCommit,
    BasePhotoOut,
    BasePhotoUploadUrlRequest,
    BasePhotoUploadUrlResponse,
    TryonOut,
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
    owner_row, _, _ = await _resolve_owner_for_base_photo(
        db, user, body.owner_kind, body.owner_id
    )
    # owner_row is a User or FamilyMember — both have base_photo_key.
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


@router.post(
    "/outfits/{outfit_id}/tryon",
    response_model=TryonOut,
    status_code=status.HTTP_202_ACCEPTED,
)
async def request_tryon(
    outfit_id: Annotated[uuid.UUID, Path()],
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> OutfitTryon:
    """Kick off a virtual try-on render. Returns 202 with the tryon row;
    poll GET /outfits/{outfit_id}/tryon to check status.
    """
    outfit = (
        await db.execute(select(Outfit).where(Outfit.id == outfit_id))
    ).scalar_one_or_none()
    if not outfit:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no such outfit")

    # Authorise + locate the owner's base photo.
    if outfit.owner_kind == OwnerKind.user:
        if outfit.owner_id != user.id:
            raise HTTPException(status.HTTP_403_FORBIDDEN)
        base_photo_key = user.base_photo_key
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
        base_photo_key = member.base_photo_key

    if not base_photo_key:
        raise HTTPException(
            status.HTTP_412_PRECONDITION_FAILED,
            "upload a base photo first (POST /tryon/base-photo)",
        )

    tryon = OutfitTryon(
        outfit_id=outfit_id,
        base_photo_key=base_photo_key,
        status=TryonStatus.pending,
    )
    db.add(tryon)
    await db.commit()
    await db.refresh(tryon)

    settings = get_settings()
    if settings.ingest_inline:
        from app.services.tryon_worker import tryon_outfit as do_tryon

        await do_tryon({}, str(tryon.id))
        await db.refresh(tryon)
    else:
        try:
            redis = await create_pool(RedisSettings.from_dsn(settings.redis_url))
            await redis.enqueue_job("tryon_outfit", str(tryon.id))
            await redis.aclose()
        except Exception:
            from app.services.tryon_worker import tryon_outfit as do_tryon

            await do_tryon({}, str(tryon.id))
            await db.refresh(tryon)

    return tryon


@router.get("/outfits/{outfit_id}/tryon", response_model=TryonOut)
async def latest_tryon(
    outfit_id: Annotated[uuid.UUID, Path()],
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> OutfitTryon:
    """Return the most-recent tryon for this outfit (any status). 404 if none."""
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

    tryon = (
        await db.execute(
            select(OutfitTryon)
            .where(OutfitTryon.outfit_id == outfit_id)
            .order_by(OutfitTryon.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if not tryon:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no tryon yet")
    return tryon
