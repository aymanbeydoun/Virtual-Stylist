import uuid
from typing import Annotated

from arq import create_pool
from arq.connections import RedisSettings
from fastapi import APIRouter, Depends, HTTPException, Path, Request, Response, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.auth import CurrentUser
from app.core.rate_limit import limiter, user_or_ip
from app.core.storage import get_storage, new_object_key
from app.db import get_db
from app.models.family import FamilyMember
from app.models.users import OwnerKind
from app.models.wardrobe import ItemCorrection, WardrobeItem
from app.schemas.wardrobe import (
    ClosetInsights,
    ItemCorrectionIn,
    ScanItemsRequest,
    ScanItemsResponse,
    ScanRegion,
    StaleItem,
    UploadUrlRequest,
    UploadUrlResponse,
    WardrobeItemCreate,
    WardrobeItemOut,
    WardrobeItemsBulkCreate,
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
@limiter.limit(lambda: get_settings().upload_rate_limit, key_func=user_or_ip)
async def create_upload_url(
    request: Request,
    body: UploadUrlRequest,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UploadUrlResponse:
    request.state.user = user
    await _resolve_owner(db, user.id, body.owner_kind, body.owner_id)
    storage = get_storage()
    key = new_object_key(prefix=f"raw/{user.id}", content_type=body.content_type)
    url, expires = await storage.signed_upload_url(key, body.content_type)
    return UploadUrlResponse(upload_url=url, object_key=key, expires_at=expires)


@router.post("/items/scan", response_model=ScanItemsResponse)
@limiter.limit(lambda: get_settings().upload_rate_limit, key_func=user_or_ip)
async def scan_for_multiple_items(
    request: Request,
    body: ScanItemsRequest,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ScanItemsResponse:
    """Run SAM 2 over an uploaded photo and return per-garment previews.

    Designed for the "I have a photo of 3 things laid out, add them all"
    flow. Costs ~$0.04 per scan (Replicate SAM 2 auto-everything mode), so
    only triggered when the user explicitly opts in — never on the default
    single-item path.

    The previews are stored under `scan-preview/{user_id}/...` and have the
    background removed by the SAM 2 mask. The mobile shows the user a grid;
    whichever previews they confirm are then committed via the bulk-create
    endpoint below.
    """
    request.state.user = user
    _kind, owner_id, _ = await _resolve_owner(
        db, user.id, body.owner_kind, body.owner_id
    )

    storage = get_storage()
    try:
        raw = await storage.read_bytes(body.object_key)
    except FileNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "upload not found") from exc

    from app.services.model_gateway import get_model_gateway

    gateway = get_model_gateway()
    masks = await gateway.segment_garments(raw)
    if not masks:
        # SAM 2 found nothing actionable. Caller can fall back to single-
        # item create with the original upload.
        return ScanItemsResponse(regions=[])

    regions: list[ScanRegion] = []
    for i, mask in enumerate(masks):
        preview_key = f"scan-preview/{owner_id}/{uuid.uuid4()}.png"
        await storage.write_bytes(preview_key, mask.mask_bytes)
        regions.append(
            ScanRegion(
                preview_key=preview_key,
                bbox=list(mask.bounding_box),
                label=mask.label,
            )
        )
        del i  # avoid ruff B007
    return ScanItemsResponse(regions=regions)


@router.post(
    "/items/bulk",
    response_model=list[WardrobeItemOut],
    status_code=status.HTTP_201_CREATED,
)
async def create_items_from_scan(
    body: WardrobeItemsBulkCreate,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[WardrobeItem]:
    """Commit N WardrobeItems from a SAM-2 scan the user just approved.

    Each `object_keys[i]` should be a `preview_key` from a previous
    `/items/scan` response, OR a `raw/...` upload key. We don't distinguish —
    we just create a row per key and enqueue the standard ingest pipeline,
    which will run preflight + classifier + bg-removal + tagging.
    """
    owner_kind, owner_id, coppa = await _resolve_owner(
        db, user.id, body.owner_kind, body.owner_id
    )

    items: list[WardrobeItem] = []
    for key in body.object_keys:
        item = WardrobeItem(
            owner_kind=owner_kind,
            owner_id=owner_id,
            raw_image_key=key,
            coppa_protected=coppa,
            status="pending",
        )
        db.add(item)
        items.append(item)
    await db.commit()
    for it in items:
        await db.refresh(it)

    settings = get_settings()
    if settings.ingest_inline:
        from app.services.ingest_worker import ingest_item

        for it in items:
            await ingest_item({}, str(it.id))
        for it in items:
            await db.refresh(it)
    else:
        try:
            redis = await create_pool(RedisSettings.from_dsn(settings.redis_url))
            for it in items:
                await redis.enqueue_job("ingest_item", str(it.id))
            await redis.aclose()
        except Exception:
            from app.services.ingest_worker import ingest_item

            for it in items:
                await ingest_item({}, str(it.id))
            for it in items:
                await db.refresh(it)

    return items


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
    if settings.ingest_inline:
        from app.services.ingest_worker import ingest_item

        await ingest_item({}, str(item.id))
        await db.refresh(item)
    else:
        try:
            redis = await create_pool(RedisSettings.from_dsn(settings.redis_url))
            await redis.enqueue_job("ingest_item", str(item.id))
            await redis.aclose()
        except Exception:
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


@router.post("/items/{item_id}/retry", response_model=WardrobeItemOut)
async def retry_item(
    item_id: Annotated[uuid.UUID, Path()],
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> WardrobeItem:
    """Re-enqueue a failed item through the ingest pipeline."""
    item = await get_item(item_id, user, db)
    item.status = "pending"
    item.needs_review = False
    await db.commit()
    await db.refresh(item)

    settings = get_settings()
    if settings.ingest_inline:
        from app.services.ingest_worker import ingest_item

        await ingest_item({}, str(item.id))
        await db.refresh(item)
    else:
        try:
            redis = await create_pool(RedisSettings.from_dsn(settings.redis_url))
            await redis.enqueue_job("ingest_item", str(item.id))
            await redis.aclose()
        except Exception:
            from app.services.ingest_worker import ingest_item

            await ingest_item({}, str(item.id))
            await db.refresh(item)
    return item


@router.delete("/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_item(
    item_id: Annotated[uuid.UUID, Path()],
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    """Soft-delete an item. Storage cleanup happens in a follow-up sweeper."""
    from datetime import UTC, datetime

    item = await get_item(item_id, user, db)
    item.deleted_at = datetime.now(UTC)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/insights", response_model=ClosetInsights)
async def closet_insights(
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    owner_kind: OwnerKind = OwnerKind.user,
    owner_id: uuid.UUID | None = None,
) -> ClosetInsights:
    """Aggregate closet hygiene signals.

    Returns:
      - total / worn / never-worn item counts
      - top 10 'stale' items (60+ days since last worn, or since upload if
        never worn)
      - overcrowded categories (>5 items in a single top-level category)
      - underused categories (categories present but with zero worn events)

    Drives the "Closet hygiene" card on the mobile You screen + the future
    "haven't worn this in months — sell or donate?" nudge.
    """
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import func

    from app.models.outfits import Outfit, OutfitEvent, OutfitEventKind, OutfitItem

    resolved_kind, resolved_id, _ = await _resolve_owner(
        db, user.id, owner_kind, owner_id
    )

    # ----- per-item last-worn timestamps ---------------------------------
    # outfit_events(worn) → outfit_items → wardrobe_items.
    # MAX(occurred_at) per item gives "last time you wore it".
    last_worn_subq = (
        select(
            OutfitItem.item_id.label("item_id"),
            func.max(OutfitEvent.occurred_at).label("last_worn_at"),
        )
        .select_from(OutfitEvent)
        .join(Outfit, Outfit.id == OutfitEvent.outfit_id)
        .join(OutfitItem, OutfitItem.outfit_id == Outfit.id)
        .where(
            Outfit.owner_kind == resolved_kind,
            Outfit.owner_id == resolved_id,
            OutfitEvent.event_kind == OutfitEventKind.worn,
        )
        .group_by(OutfitItem.item_id)
        .subquery()
    )

    rows = (
        await db.execute(
            select(
                WardrobeItem.id,
                WardrobeItem.category,
                WardrobeItem.thumbnail_key,
                WardrobeItem.created_at,
                last_worn_subq.c.last_worn_at,
            )
            .outerjoin(
                last_worn_subq,
                last_worn_subq.c.item_id == WardrobeItem.id,
            )
            .where(
                WardrobeItem.owner_kind == resolved_kind,
                WardrobeItem.owner_id == resolved_id,
                WardrobeItem.deleted_at.is_(None),
                WardrobeItem.status == "ready",
            )
        )
    ).all()

    now = datetime.now(UTC)
    total = len(rows)
    worn = sum(1 for r in rows if r.last_worn_at is not None)
    never_worn = sum(
        1
        for r in rows
        if r.last_worn_at is None and (now - r.created_at) >= timedelta(days=14)
    )

    # Stale: anything 60+ days since last worn (or 60+ days in closet without
    # being worn). Largest gap first.
    stale: list[StaleItem] = []
    for r in rows:
        ref = r.last_worn_at or r.created_at
        days = (now - ref).days
        if days < 60:
            continue
        stale.append(
            StaleItem(
                item_id=r.id,
                category=r.category,
                thumbnail_key=r.thumbnail_key,
                last_worn_at=r.last_worn_at,
                days_unworn=days,
            )
        )
    stale.sort(key=lambda s: s.days_unworn, reverse=True)
    stale = stale[:10]

    # Overcrowded: top-level category (the part before the second dot, eg
    # "mens.tops" from "mens.tops.tshirt") with > 5 items.
    from collections import Counter

    def _top_level(cat: str | None) -> str | None:
        if not cat:
            return None
        parts = cat.split(".")
        return ".".join(parts[:2]) if len(parts) >= 2 else cat

    cat_counts: Counter[str] = Counter()
    cat_worn: Counter[str] = Counter()
    for r in rows:
        tl = _top_level(r.category)
        if not tl:
            continue
        cat_counts[tl] += 1
        if r.last_worn_at:
            cat_worn[tl] += 1

    OVERCROWD_THRESHOLD = 5
    overcrowded = [
        {"category": cat, "count": n, "threshold": OVERCROWD_THRESHOLD}
        for cat, n in cat_counts.most_common()
        if n > OVERCROWD_THRESHOLD
    ][:5]

    # Underused: categories with >= 2 items but zero worn events.
    underused = [
        {"category": cat, "count": n}
        for cat, n in cat_counts.most_common()
        if n >= 2 and cat_worn.get(cat, 0) == 0
    ][:5]

    return ClosetInsights(
        total_items=total,
        worn_items=worn,
        never_worn_items=never_worn,
        stale_items=stale,
        overcrowded_categories=overcrowded,
        underused_categories=underused,
    )


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
