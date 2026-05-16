"""Closet-Gap analysis endpoints."""
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser
from app.db import get_db
from app.models.family import FamilyMember
from app.models.gaps import GapFinding, GapStatus
from app.models.users import OwnerKind
from app.schemas.gaps import GapAnalyseRequest, GapFindingOut
from app.services.gap_analysis import analyse_wardrobe, dismiss

router = APIRouter()


async def _resolve_owner(
    db: AsyncSession,
    user_id: uuid.UUID,
    owner_kind: OwnerKind,
    owner_id: uuid.UUID | None,
) -> tuple[OwnerKind, uuid.UUID, str]:
    """Resolve owner + label. Mirrors wardrobe._resolve_owner but also returns a label."""
    if owner_kind == OwnerKind.user:
        return OwnerKind.user, user_id, "You"
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
    return OwnerKind.family_member, member.id, member.display_name


@router.post("/analyse", response_model=list[GapFindingOut])
async def run_analysis(
    body: GapAnalyseRequest,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[GapFinding]:
    owner_kind, owner_id, label = await _resolve_owner(
        db, user.id, body.owner_kind, body.owner_id
    )
    findings = await analyse_wardrobe(
        db, owner_kind=owner_kind, owner_id=owner_id, owner_label=label
    )
    return findings


@router.get("", response_model=list[GapFindingOut])
async def list_gaps(
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    owner_kind: OwnerKind = OwnerKind.user,
    owner_id: uuid.UUID | None = None,
    include_dismissed: bool = False,
) -> list[GapFinding]:
    resolved_kind, resolved_id, _ = await _resolve_owner(db, user.id, owner_kind, owner_id)
    q = select(GapFinding).where(
        GapFinding.owner_kind == resolved_kind,
        GapFinding.owner_id == resolved_id,
    )
    if not include_dismissed:
        q = q.where(GapFinding.status == GapStatus.open)
    q = q.order_by(GapFinding.severity, GapFinding.created_at.desc())
    return list((await db.execute(q)).scalars().all())


@router.post("/{gap_id}/dismiss", status_code=status.HTTP_204_NO_CONTENT)
async def dismiss_gap(
    gap_id: Annotated[uuid.UUID, Path()],
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    owner_kind: OwnerKind = OwnerKind.user,
    owner_id: uuid.UUID | None = None,
) -> Response:
    resolved_kind, resolved_id, _ = await _resolve_owner(db, user.id, owner_kind, owner_id)
    ok = await dismiss(db, gap_id=gap_id, owner_kind=resolved_kind, owner_id=resolved_id)
    if not ok:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no open gap with that id")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
