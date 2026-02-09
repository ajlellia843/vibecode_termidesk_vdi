"""Conversation repository."""
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from orchestrator.repositories.models import Conversation


class ConversationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_or_create(self, user_id: str, telegram_chat_id: str) -> Conversation:
        q = select(Conversation).where(
            Conversation.telegram_chat_id == telegram_chat_id
        ).order_by(Conversation.created_at.desc()).limit(1)
        result = await self._session.execute(q)
        conv = result.scalar_one_or_none()
        if conv is not None:
            return conv
        conv = Conversation(user_id=user_id, telegram_chat_id=telegram_chat_id)
        self._session.add(conv)
        await self._session.flush()
        return conv

    async def get_by_id(self, conversation_id: UUID) -> Conversation | None:
        result = await self._session.execute(
            select(Conversation).where(Conversation.id == conversation_id)
        )
        return result.scalar_one_or_none()
