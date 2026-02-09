"""Orchestrator API routes."""
from uuid import UUID

from fastapi import APIRouter, Request

from orchestrator.api.schemas import ChatRequest, ChatResponse

router = APIRouter(prefix="/api/v1", tags=["orchestrator"])


@router.post("/chat", response_model=ChatResponse)
async def chat(body: ChatRequest, request: Request) -> ChatResponse:
    service = request.app.state.dialog_service
    reply, sources, conversation_id = await service.reply(
        user_id=body.user_id,
        telegram_chat_id=body.user_id,
        user_message=body.message,
        conversation_id=body.conversation_id,
    )
    return ChatResponse(reply=reply, sources=sources, conversation_id=conversation_id)
