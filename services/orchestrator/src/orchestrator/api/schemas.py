"""API request/response schemas."""
from typing import Literal
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
    mode: Literal["answer", "diagnostic", "need_version"] | None = None
    version: str | None = None
    rag: dict | None = None


class ChatResult:
    """Internal result from DialogService.reply(); maps to ChatResponse."""

    def __init__(
        self,
        reply: str,
        sources: list[dict],
        conversation_id: UUID,
        mode: Literal["answer", "diagnostic", "need_version"],
        version: str | None = None,
        rag: dict | None = None,
    ) -> None:
        self.reply = reply
        self.sources = sources
        self.conversation_id = conversation_id
        self.mode = mode
        self.version = version
        self.rag = rag


class UserUpsertRequest(BaseModel):
    telegram_id: str = Field(..., min_length=1)


class UserVersionRequest(BaseModel):
    version: str = Field(..., min_length=1)


class UserResponse(BaseModel):
    termidesk_version: str | None = None
