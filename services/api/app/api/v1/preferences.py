"""User preference endpoints — saved style + future settings."""
import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser
from app.db import get_db
from app.models.family import FamilyMember
from app.models.users import OwnerKind, StyleProfile
from app.schemas.stylist import Style

router = APIRouter()


BodyShape = Literal[
    "rectangle",
    "hourglass",
    "pear",
    "apple",
    "inverted_triangle",
    "athletic",
]

# "mens" | "womens" — the two gendered category prefixes Claude tagging uses.
# "unspecified" is represented as None on the wire (cleared field).
Gender = Literal["mens", "womens"]


class StylePreferenceOut(BaseModel):
    preferred_style: Style | None
    body_shape: BodyShape | None = None
    gender: Gender | None = None
    owner_kind: OwnerKind
    owner_id: uuid.UUID


class StylePreferenceIn(BaseModel):
    preferred_style: Style | None  # null clears it
    owner_kind: OwnerKind = OwnerKind.user
    owner_id: uuid.UUID | None = None


class BodyShapeIn(BaseModel):
    body_shape: BodyShape | None
    owner_kind: OwnerKind = OwnerKind.user
    owner_id: uuid.UUID | None = None


class GenderIn(BaseModel):
    gender: Gender | None
    owner_kind: OwnerKind = OwnerKind.user
    owner_id: uuid.UUID | None = None


async def _resolve_owner_for_prefs(
    db: AsyncSession,
    user_id: uuid.UUID,
    owner_kind: OwnerKind,
    owner_id: uuid.UUID | None,
) -> tuple[OwnerKind, uuid.UUID]:
    if owner_kind == OwnerKind.user:
        return OwnerKind.user, user_id
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
    return OwnerKind.family_member, member.id


async def _profile(
    db: AsyncSession, owner_kind: OwnerKind, owner_id: uuid.UUID
) -> StyleProfile:
    """Get or create the StyleProfile for this owner."""
    profile = (
        await db.execute(
            select(StyleProfile).where(
                StyleProfile.owner_kind == owner_kind, StyleProfile.owner_id == owner_id
            )
        )
    ).scalar_one_or_none()
    if not profile:
        profile = StyleProfile(owner_kind=owner_kind, owner_id=owner_id)
        db.add(profile)
        await db.flush()
    return profile


@router.get("/style", response_model=StylePreferenceOut)
async def get_style_preference(
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    owner_kind: OwnerKind = OwnerKind.user,
    owner_id: uuid.UUID | None = None,
) -> StylePreferenceOut:
    resolved_kind, resolved_id = await _resolve_owner_for_prefs(
        db, user.id, owner_kind, owner_id
    )
    profile = await _profile(db, resolved_kind, resolved_id)
    return StylePreferenceOut(
        preferred_style=_coerce_style(profile.preferred_style),
        body_shape=_coerce_body_shape(profile.body_shape),
        gender=_coerce_gender(profile.gender),
        owner_kind=resolved_kind,
        owner_id=resolved_id,
    )


@router.put("/style", response_model=StylePreferenceOut)
async def set_style_preference(
    body: StylePreferenceIn,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> StylePreferenceOut:
    resolved_kind, resolved_id = await _resolve_owner_for_prefs(
        db, user.id, body.owner_kind, body.owner_id
    )
    profile = await _profile(db, resolved_kind, resolved_id)
    profile.preferred_style = body.preferred_style
    await db.commit()
    await db.refresh(profile)
    return StylePreferenceOut(
        preferred_style=_coerce_style(profile.preferred_style),
        body_shape=_coerce_body_shape(profile.body_shape),
        gender=_coerce_gender(profile.gender),
        owner_kind=resolved_kind,
        owner_id=resolved_id,
    )


@router.put("/body-shape", response_model=StylePreferenceOut)
async def set_body_shape(
    body: BodyShapeIn,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> StylePreferenceOut:
    resolved_kind, resolved_id = await _resolve_owner_for_prefs(
        db, user.id, body.owner_kind, body.owner_id
    )
    profile = await _profile(db, resolved_kind, resolved_id)
    profile.body_shape = body.body_shape
    await db.commit()
    await db.refresh(profile)
    return StylePreferenceOut(
        preferred_style=_coerce_style(profile.preferred_style),
        body_shape=_coerce_body_shape(profile.body_shape),
        gender=_coerce_gender(profile.gender),
        owner_kind=resolved_kind,
        owner_id=resolved_id,
    )


# StyleProfile.preferred_style is free-text in the DB, but the API typechecks
# against the closed Style literal. Coerce unknown values to None defensively
# so we never crash a client that's older than the DB.
_VALID_STYLES: set[str] = {
    "streetwear",
    "minimal",
    "classic",
    "preppy",
    "bohemian",
    "athleisure",
    "avant_garde",
    "smart_casual",
}


def _coerce_style(raw: str | None) -> Style | None:
    if raw and raw in _VALID_STYLES:
        return raw  # type: ignore[return-value]
    return None


_VALID_BODY_SHAPES: set[str] = {
    "rectangle", "hourglass", "pear", "apple", "inverted_triangle", "athletic",
}


def _coerce_body_shape(raw: str | None) -> BodyShape | None:
    if raw and raw in _VALID_BODY_SHAPES:
        return raw  # type: ignore[return-value]
    return None


_VALID_GENDERS: set[str] = {"mens", "womens"}


def _coerce_gender(raw: str | None) -> Gender | None:
    if raw and raw in _VALID_GENDERS:
        return raw  # type: ignore[return-value]
    return None


@router.put("/gender", response_model=StylePreferenceOut)
async def set_gender(
    body: GenderIn,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> StylePreferenceOut:
    """Set the wearer's gender preference.

    Drives the gender hard-filter on candidate selection — without it, a
    user with a mixed seeded closet ends up with cross-gender items in
    suggested outfits, which break try-on (Gemini biases the render to
    match the item gender, not the user's photo).
    """
    resolved_kind, resolved_id = await _resolve_owner_for_prefs(
        db, user.id, body.owner_kind, body.owner_id
    )
    profile = await _profile(db, resolved_kind, resolved_id)
    profile.gender = body.gender
    await db.commit()
    await db.refresh(profile)
    return StylePreferenceOut(
        preferred_style=_coerce_style(profile.preferred_style),
        body_shape=_coerce_body_shape(profile.body_shape),
        gender=_coerce_gender(profile.gender),
        owner_kind=resolved_kind,
        owner_id=resolved_id,
    )


# Literal is imported for typing-only use elsewhere; reference once to silence
# the unused-import warning without changing public API.
_ = Literal
