"""Outfit refinement chat endpoint.

POST /outfits/{outfit_id}/refine — accepts a free-text user message, returns
the revised outfit + the assistant's reply.

GET  /outfits/{outfit_id}/conversation — returns the full chat history.
"""
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.auth import CurrentUser
from app.db import SessionLocal, get_db
from app.models.conversations import MessageRole, OutfitMessage
from app.models.family import FamilyMember
from app.models.outfits import Outfit, OutfitItem, OutfitSlot
from app.models.users import OwnerKind
from app.models.wardrobe import WardrobeItem
from app.schemas.refine import ConversationOut, MessageOut, RefineRequest, RefineResponse
from app.schemas.stylist import OutfitItemOut, OutfitOut
from app.schemas.wardrobe import WardrobeItemOut
from app.services.model_gateway import get_model_gateway
from app.services.stylist_engine import _serialize_candidate

router = APIRouter()


async def _check_outfit_access(
    db: AsyncSession, outfit_id: uuid.UUID, user_id: uuid.UUID
) -> Outfit:
    outfit = (
        await db.execute(
            select(Outfit).where(Outfit.id == outfit_id).options(selectinload(Outfit.items))
        )
    ).scalar_one_or_none()
    if not outfit:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no such outfit")
    if outfit.owner_kind == OwnerKind.user:
        if outfit.owner_id != user_id:
            raise HTTPException(status.HTTP_403_FORBIDDEN)
    else:
        member = (
            await db.execute(
                select(FamilyMember).where(
                    FamilyMember.id == outfit.owner_id, FamilyMember.guardian_id == user_id
                )
            )
        ).scalar_one_or_none()
        if not member:
            raise HTTPException(status.HTTP_403_FORBIDDEN)
    return outfit


def _outfit_to_response(outfit: Outfit, items_by_id: dict[uuid.UUID, WardrobeItem]) -> OutfitOut:
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


@router.get("/outfits/{outfit_id}/conversation", response_model=ConversationOut)
async def get_conversation(
    outfit_id: Annotated[uuid.UUID, Path()],
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ConversationOut:
    await _check_outfit_access(db, outfit_id, user.id)
    rows = (
        await db.execute(
            select(OutfitMessage)
            .where(OutfitMessage.outfit_id == outfit_id)
            .order_by(OutfitMessage.created_at.asc())
        )
    ).scalars().all()
    return ConversationOut(
        messages=[MessageOut.model_validate(m) for m in rows]
    )


@router.post("/outfits/{outfit_id}/refine", response_model=RefineResponse)
async def refine_outfit(
    outfit_id: Annotated[uuid.UUID, Path()],
    body: RefineRequest,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> RefineResponse:
    outfit = await _check_outfit_access(db, outfit_id, user.id)

    # Load the user's full closet so the AI can pick replacements/additions.
    closet_q = select(WardrobeItem).where(
        WardrobeItem.owner_kind == outfit.owner_kind,
        WardrobeItem.owner_id == outfit.owner_id,
        WardrobeItem.status == "ready",
        WardrobeItem.deleted_at.is_(None),
    )
    closet = list((await db.execute(closet_q)).scalars().all())
    candidates = [_serialize_candidate(it) for it in closet]
    items_by_id = {it.id: it for it in closet}

    # Snapshot the current outfit items as the "current" view.
    current_items = [
        {"item_id": str(oi.item_id), "slot": oi.slot.value} for oi in outfit.items
    ]

    # Chat history for this outfit.
    history_rows = (
        await db.execute(
            select(OutfitMessage)
            .where(OutfitMessage.outfit_id == outfit_id)
            .order_by(OutfitMessage.created_at.asc())
        )
    ).scalars().all()
    history = [{"role": h.role.value, "content": h.content} for h in history_rows]

    # Persist the user turn before calling the LLM so we don't lose it on
    # transient failures.
    user_msg = OutfitMessage(
        outfit_id=outfit_id, role=MessageRole.user, content=body.message
    )
    db.add(user_msg)
    await db.flush()

    # Call the gateway.
    gateway = get_model_gateway()
    # Determine kid_mode by checking the owner type — adults get the full
    # adult model, family-member kids get Haiku.
    kid_mode = False
    if outfit.owner_kind == OwnerKind.family_member:
        member = (
            await db.execute(
                select(FamilyMember).where(FamilyMember.id == outfit.owner_id)
            )
        ).scalar_one_or_none()
        kid_mode = bool(member and member.kind.value == "kid" and member.kid_mode)

    result = await gateway.refine_outfit(
        current_items=current_items,
        candidates=candidates,
        history=history,
        user_message=body.message,
        destination=outfit.destination,
        mood=outfit.mood,
        style=outfit.style,
        kid_mode=kid_mode,
    )

    # Validate every returned item_id is in the closet — never trust the LLM
    # to invent IDs.
    valid_ids = {str(it.id) for it in closet}
    revised_items: list[OutfitItem] = []
    used: set[str] = set()
    for entry in result.items:
        iid = str(entry.get("item_id", ""))
        slot = str(entry.get("slot", ""))
        if iid in valid_ids and iid not in used and slot:
            try:
                revised_items.append(
                    OutfitItem(item_id=uuid.UUID(iid), slot=OutfitSlot(slot))
                )
                used.add(iid)
            except (ValueError, KeyError):
                continue

    items_actually_changed = False
    if revised_items:
        old_ids = {oi.item_id for oi in outfit.items}
        new_ids = {oi.item_id for oi in revised_items}
        items_actually_changed = old_ids != new_ids

        # Replace items atomically: delete old joins, add new.
        for oi in list(outfit.items):
            outfit.items.remove(oi)
        for oi in revised_items:
            outfit.items.append(oi)

        outfit.rationale = result.rationale or outfit.rationale
        if result.style:
            outfit.style = result.style

        if items_actually_changed:
            # The flat-lay PNG is now stale. Mark null + enqueue a recompose so
            # the mobile picks up the new image on its next refetch.
            outfit.composite_image_key = None

    # Persist the assistant reply.
    assistant_msg = OutfitMessage(
        outfit_id=outfit_id,
        role=MessageRole.assistant,
        content=result.message,
    )
    db.add(assistant_msg)

    await db.commit()
    await db.refresh(outfit, attribute_names=["items"])
    await db.refresh(assistant_msg)

    # Post-commit side effects: re-render the composite + drop any cached
    # tryons so the user is prompted to re-render once the items changed.
    if items_actually_changed:
        await _enqueue_after_refine(outfit_id)

    return RefineResponse(
        outfit=_outfit_to_response(outfit, items_by_id),
        message=MessageOut.model_validate(assistant_msg),
    )


async def _enqueue_after_refine(outfit_id: uuid.UUID) -> None:
    """Re-render the composite + mark existing tryons stale.

    The composite reads from each item's cutout — same flow as the initial
    generation. The previous tryon used the old item set, so we delete the
    rendered_image_key but keep the row (history). The mobile shows a fresh
    'Try on me' CTA on next view.
    """
    from app.config import get_settings
    from app.models.tryons import OutfitTryon, TryonStatus
    from app.services.outfit_compositor import compose_outfit_image

    settings = get_settings()
    # Mark existing ready tryons stale so the mobile re-renders.
    async with SessionLocal() as db2:
        rows = (
            await db2.execute(
                select(OutfitTryon).where(
                    OutfitTryon.outfit_id == outfit_id,
                    OutfitTryon.status == TryonStatus.ready,
                )
            )
        ).scalars().all()
        for t in rows:
            t.rendered_image_key = None
            t.status = TryonStatus.failed
            t.error_message = "stale: outfit changed via refinement"
        await db2.commit()

    if settings.ingest_inline:
        await compose_outfit_image({}, str(outfit_id))
        return
    try:
        from arq import create_pool
        from arq.connections import RedisSettings

        redis = await create_pool(RedisSettings.from_dsn(settings.redis_url))
        await redis.enqueue_job("compose_outfit_image", str(outfit_id))
        await redis.aclose()
    except Exception:
        await compose_outfit_image({}, str(outfit_id))
