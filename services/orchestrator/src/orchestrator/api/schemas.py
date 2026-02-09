"""API request/response schemas."""
from uuid import UUID

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    user_id: str = Field(..., min_length=1)
    message: str = Field(..., min_length=1)
    conversation_id: UUID | None = None


class ChatResponse(BaseModel):
    reply: str
    sources: list[dict[str, str]] = Field(default_factory=list)
    conversation_id: UUID | None = None
