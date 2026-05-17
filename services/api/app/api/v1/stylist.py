import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.auth import CurrentUser
from app.core.rate_limit import limiter, user_or_ip
from app.db import get_db
from app.models.family import FamilyMember, FamilyMemberKind
from app.models.outfits import Outfit, OutfitEvent, OutfitEventKind
from app.models.users import OwnerKind
from app.models.wardrobe import WardrobeItem
from app.schemas.stylist import (
    GenerateOutfitRequest,
    GenerateOutfitResponse,
    OutfitItemOut,
    OutfitOut,
)
from app.schemas.wardrobe import WardrobeItemOut
from app.services.stylist_engine import generate_outfits

router = APIRouter()


async def _resolve_owner_and_kid_mode(
    db: AsyncSession,
    user_id: uuid.UUID,
    owner_kind: OwnerKind,
    owner_id: uuid.UUID | None,
) -> tuple[OwnerKind, uuid.UUID, bool]:
    if owner_kind == OwnerKind.user:
        return OwnerKind.user, user_id, False
    if not owner_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "owner_id required")
    member = (
        await db.execute(
            select(FamilyMember).where(
                FamilyMember.id == owner_id, FamilyMember.guardian_id == user_id
            )
        )
    ).scalar_one_or_none()
    if not member:
        raise HTTPException(status.HTTP_403_FORBIDDEN)
    return OwnerKind.family_member, member.id, member.kind == FamilyMemberKind.kid


def _outfit_to_response(outfit: Outfit, items_by_id: dict[uuid.UUID, object]) -> OutfitOut:
    return OutfitOut(
        id=outfit.id,
        destination=outfit.destination,
        mood=outfit.mood,
        style=outfit.style,
        rationale=outfit.rationale,
        confidence=outfit.confidence,
        composite_image_key=outfit.composite_image_key,
        created_at=outfit.created_at,
        items=[
            OutfitItemOut(
                slot=oi.slot.value,
                item=WardrobeItemOut.model_validate(items_by_id[oi.item_id]),
            )
            for oi in outfit.items
            if oi.item_id in items_by_id
        ],
    )


@router.post("/generate", response_model=GenerateOutfitResponse)
@limiter.limit(lambda: get_settings().stylist_rate_limit, key_func=user_or_ip)
async def generate(
    request: Request,
    body: GenerateOutfitRequest,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> GenerateOutfitResponse:
    request.state.user = user
    owner_kind, owner_id, kid_mode = await _resolve_owner_and_kid_mode(
        db, user.id, body.owner_kind, body.owner_id
    )
    outfits, weather = await generate_outfits(
        db,
        owner_kind=owner_kind,
        owner_id=owner_id,
        destination=body.destination,
        mood=body.mood,
        style=body.style,
        notes=body.notes,
        kid_mode=kid_mode,
    )

    item_ids = {oi.item_id for o in outfits for oi in o.items}
    items_map: dict[uuid.UUID, object] = {}
    if item_ids:
        rows = (
            await db.execute(select(WardrobeItem).where(WardrobeItem.id.in_(item_ids)))
        ).scalars().all()
        items_map = {r.id: r for r in rows}

    return GenerateOutfitResponse(
        outfits=[_outfit_to_response(o, items_map) for o in outfits], weather=weather
    )


@router.get("/outfits/{outfit_id}", response_model=OutfitOut)
async def get_outfit(
    outfit_id: uuid.UUID,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> OutfitOut:
    from sqlalchemy.orm import selectinload

    outfit = (
        await db.execute(
            select(Outfit).where(Outfit.id == outfit_id).options(selectinload(Outfit.items))
        )
    ).scalar_one_or_none()
    if not outfit:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    if outfit.owner_kind == OwnerKind.user and outfit.owner_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN)
    if outfit.owner_kind == OwnerKind.family_member:
        member = (
            await db.execute(
                select(FamilyMember).where(
                    FamilyMember.id == outfit.owner_id, FamilyMember.guardian_id == user.id
                )
            )
        ).scalar_one_or_none()
        if not member:
            raise HTTPException(status.HTTP_403_FORBIDDEN)
    item_ids = {oi.item_id for oi in outfit.items}
    items_map: dict[uuid.UUID, object] = {}
    if item_ids:
        rows = (
            await db.execute(select(WardrobeItem).where(WardrobeItem.id.in_(item_ids)))
        ).scalars().all()
        items_map = {r.id: r for r in rows}
    return _outfit_to_response(outfit, items_map)


@router.post("/outfits/{outfit_id}/events", status_code=status.HTTP_201_CREATED)
async def record_event(
    outfit_id: uuid.UUID,
    kind: OutfitEventKind,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, str]:
    outfit = (
        await db.execute(select(Outfit).where(Outfit.id == outfit_id))
    ).scalar_one_or_none()
    if not outfit:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    if outfit.owner_kind == OwnerKind.user and outfit.owner_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN)

    if kind == OutfitEventKind.saved:
        outfit.accepted = True
    event = OutfitEvent(outfit_id=outfit_id, event_kind=kind)
    db.add(event)
    await db.commit()
    return {"status": "recorded"}
