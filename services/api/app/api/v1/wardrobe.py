import uuid
from typing import Annotated

from arq import create_pool
from arq.connections import RedisSettings
from fastapi import APIRouter, Depends, HTTPException, Path, Response, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.auth import CurrentUser
from app.core.storage import get_storage, new_object_key
from app.db import get_db
from app.models.family import FamilyMember
from app.models.users import OwnerKind
from app.models.wardrobe import ItemCorrection, WardrobeItem
from app.schemas.wardrobe import (
    ItemCorrectionIn,
    UploadUrlRequest,
    UploadUrlResponse,
    WardrobeItemCreate,
    WardrobeItemOut,
)

router = APIRouter()


async def _resolve_owner(
    db: AsyncSession,
    user_id: uuid.UUID,
    owner_kind: OwnerKind,
    owner_id: uuid.UUID | None,
) -> tuple[OwnerKind, uuid.UUID, bool]:
    if owner_kind == OwnerKind.user:
        return OwnerKind.user, user_id, False
    if not owner_id:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "owner_id required for family_member owner"
        )
    member = (
        await db.execute(
            select(FamilyMember).where(
                FamilyMember.id == owner_id, FamilyMember.guardian_id == user_id
            )
        )
    ).scalar_one_or_none()
    if not member:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "not your family member")
    return OwnerKind.family_member, member.id, member.kind.value == "kid"


@router.post("/upload-url", response_model=UploadUrlResponse)
async def create_upload_url(
    body: UploadUrlRequest,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UploadUrlResponse:
    await _resolve_owner(db, user.id, body.owner_kind, body.owner_id)
    storage = get_storage()
    key = new_object_key(prefix=f"raw/{user.id}", content_type=body.content_type)
    url, expires = await storage.signed_upload_url(key, body.content_type)
    return UploadUrlResponse(upload_url=url, object_key=key, expires_at=expires)


@router.post("/items", response_model=WardrobeItemOut, status_code=status.HTTP_201_CREATED)
async def create_item(
    body: WardrobeItemCreate,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> WardrobeItem:
    owner_kind, owner_id, coppa = await _resolve_owner(db, user.id, body.owner_kind, body.owner_id)
    item = WardrobeItem(
        owner_kind=owner_kind,
        owner_id=owner_id,
        raw_image_key=body.object_key,
        coppa_protected=coppa,
        status="pending",
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)

    settings = get_settings()
    try:
        redis = await create_pool(RedisSettings.from_dsn(settings.redis_url))
        await redis.enqueue_job("ingest_item", str(item.id))
        await redis.close()
    except Exception:
        # In dev without redis: run inline so the loop still works.
        from app.services.ingest_worker import ingest_item

        await ingest_item({}, str(item.id))
        await db.refresh(item)

    return item


@router.get("/items", response_model=list[WardrobeItemOut])
async def list_items(
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    owner_kind: OwnerKind = OwnerKind.user,
    owner_id: uuid.UUID | None = None,
    category: str | None = None,
) -> list[WardrobeItem]:
    resolved_kind, resolved_id, _ = await _resolve_owner(db, user.id, owner_kind, owner_id)
    q = select(WardrobeItem).where(
        WardrobeItem.owner_kind == resolved_kind,
        WardrobeItem.owner_id == resolved_id,
        WardrobeItem.deleted_at.is_(None),
    )
    if category:
        q = q.where(WardrobeItem.category.like(f"{category}%"))
    q = q.order_by(WardrobeItem.created_at.desc())
    return list((await db.execute(q)).scalars().all())


@router.get("/items/{item_id}", response_model=WardrobeItemOut)
async def get_item(
    item_id: Annotated[uuid.UUID, Path()],
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> WardrobeItem:
    item = (
        await db.execute(select(WardrobeItem).where(WardrobeItem.id == item_id))
    ).scalar_one_or_none()
    if not item:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    if item.owner_kind == OwnerKind.user and item.owner_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN)
    if item.owner_kind == OwnerKind.family_member:
        member = (
            await db.execute(
                select(FamilyMember).where(
                    FamilyMember.id == item.owner_id, FamilyMember.guardian_id == user.id
                )
            )
        ).scalar_one_or_none()
        if not member:
            raise HTTPException(status.HTTP_403_FORBIDDEN)
    return item


@router.post("/items/{item_id}/corrections", status_code=status.HTTP_204_NO_CONTENT)
async def correct_item(
    item_id: uuid.UUID,
    body: ItemCorrectionIn,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    item = await get_item(item_id, user, db)
    old = getattr(item, body.field, None)
    correction = ItemCorrection(
        item_id=item.id, field=body.field, old_value=str(old), new_value=body.new_value
    )
    db.add(correction)
    if hasattr(item, body.field):
        setattr(item, body.field, body.new_value)
    item.needs_review = False
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put("/_local_upload/{key:path}", include_in_schema=False)
async def _local_upload(key: str, file: UploadFile) -> dict[str, str]:
    settings = get_settings()
    if settings.storage_backend != "local":
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    data = await file.read()
    await get_storage().write_bytes(key, data)
    return {"key": key}


@router.get("/_local_read/{key:path}", include_in_schema=False)
async def _local_read(key: str) -> Response:
    settings = get_settings()
    if settings.storage_backend != "local":
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    data = await get_storage().read_bytes(key)
    return Response(content=data, media_type="application/octet-stream")
