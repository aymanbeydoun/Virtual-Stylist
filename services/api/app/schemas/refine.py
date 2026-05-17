"""Schemas for the outfit-refinement chat endpoint."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.conversations import MessageRole
from app.schemas.stylist import OutfitOut


class RefineRequest(BaseModel):
    message: str = Field(min_length=1, max_length=500)


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    role: MessageRole
    content: str
    created_at: datetime


class RefineResponse(BaseModel):
    outfit: OutfitOut
    message: MessageOut  # the assistant's reply that just got created


class ConversationOut(BaseModel):
    messages: list[MessageOut]
