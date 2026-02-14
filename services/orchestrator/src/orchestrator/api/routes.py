"""Orchestrator API routes."""
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request

from orchestrator.api.schemas import (
    ChatRequest,
    ChatResponse,
    UserResponse,
    UserUpsertRequest,
    UserVersionRequest,
)
from orchestrator.repositories import UserRepository

TERMIDESK_VERSIONS = (
    "6.1 (latest)",
    "6.0.2",
    "6.0.1",
    "6.0",
    "5.1.2",
    "5.1.1",
    "5.1",
)

router = APIRouter(prefix="/api/v1", tags=["orchestrator"])


@router.post("/chat", response_model=ChatResponse)
async def chat(body: ChatRequest, request: Request) -> ChatResponse:
    service = request.app.state.dialog_service
    result = await service.reply(
        user_id=body.user_id,
        telegram_chat_id=body.user_id,
        user_message=body.message,
        conversation_id=body.conversation_id,
    )
    return ChatResponse(
        reply=result.reply,
        sources=result.sources,
        conversation_id=result.conversation_id,
        mode=result.mode,
        version=result.version,
        rag=result.rag,
    )


@router.post("/users/upsert", response_model=UserResponse)
async def users_upsert(body: UserUpsertRequest, request: Request) -> UserResponse:
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        repo = UserRepository(session)
        user = await repo.upsert(body.telegram_id)
        await session.commit()
    return UserResponse(termidesk_version=user.termidesk_version)


@router.post("/users/{telegram_id}/version", response_model=UserResponse)
async def users_set_version(
    telegram_id: str, body: UserVersionRequest, request: Request
) -> UserResponse:
    if body.version not in TERMIDESK_VERSIONS:
        raise HTTPException(status_code=400, detail="Invalid version")
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        repo = UserRepository(session)
        user = await repo.get_by_telegram_id(telegram_id)
        if user is None:
            user = await repo.upsert(telegram_id, termidesk_version=body.version)
        else:
            await repo.set_version(telegram_id, body.version)
        await session.commit()
        user = await repo.get_by_telegram_id(telegram_id)
    return UserResponse(termidesk_version=user.termidesk_version if user else None)


@router.get("/users/{telegram_id}", response_model=UserResponse)
async def users_get(telegram_id: str, request: Request) -> UserResponse:
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        repo = UserRepository(session)
        user = await repo.get_by_telegram_id(telegram_id)
    return UserResponse(termidesk_version=user.termidesk_version if user else None)
