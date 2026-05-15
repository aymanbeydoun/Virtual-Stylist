import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser
from app.db import get_db
from app.models.family import FamilyMember, FamilyMemberKind, KidConsent
from app.models.users import UserRole
from app.schemas.family import FamilyMemberCreate, FamilyMemberOut

router = APIRouter()


@router.get("/members", response_model=list[FamilyMemberOut])
async def list_members(
    user: CurrentUser, db: Annotated[AsyncSession, Depends(get_db)]
) -> list[FamilyMember]:
    rows = (
        await db.execute(
            select(FamilyMember).where(
                FamilyMember.guardian_id == user.id, FamilyMember.deleted_at.is_(None)
            )
        )
    ).scalars().all()
    return list(rows)


@router.post("/members", response_model=FamilyMemberOut, status_code=status.HTTP_201_CREATED)
async def create_member(
    body: FamilyMemberCreate,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> FamilyMember:
    if body.kind == FamilyMemberKind.kid and not body.consent_method:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "consent_method is required for kid sub-profiles"
        )

    if user.role != UserRole.guardian:
        user.role = UserRole.guardian  # promote on first family-member creation

    member = FamilyMember(
        guardian_id=user.id,
        display_name=body.display_name,
        kind=body.kind,
        birth_year=body.birth_year,
        kid_mode=body.kid_mode,
    )
    db.add(member)
    await db.flush()

    if body.kind == FamilyMemberKind.kid and body.consent_method:
        db.add(
            KidConsent(
                family_member_id=member.id,
                guardian_id=user.id,
                consent_method=body.consent_method,
                granted_at=datetime.now(UTC),
            )
        )

    await db.commit()
    await db.refresh(member)
    return member


@router.delete("/members/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_member(
    member_id: uuid.UUID,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    member = (
        await db.execute(
            select(FamilyMember).where(
                FamilyMember.id == member_id, FamilyMember.guardian_id == user.id
            )
        )
    ).scalar_one_or_none()
    if not member:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    member.deleted_at = datetime.now(UTC)
    await db.commit()
