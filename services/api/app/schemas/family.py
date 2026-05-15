import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.family import ConsentMethod, FamilyMemberKind


class FamilyMemberCreate(BaseModel):
    display_name: str = Field(min_length=1, max_length=60)
    kind: FamilyMemberKind = FamilyMemberKind.kid
    birth_year: int | None = Field(default=None, ge=1900, le=2100)
    kid_mode: bool = True
    consent_method: ConsentMethod | None = None


class FamilyMemberOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    display_name: str
    kind: FamilyMemberKind
    birth_year: int | None
    kid_mode: bool
    created_at: datetime
