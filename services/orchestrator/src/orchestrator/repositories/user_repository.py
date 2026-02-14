"""User repository: get, upsert, set version."""
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import func

from orchestrator.repositories.models import User


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_telegram_id(self, telegram_id: str) -> User | None:
        result = await self._session.execute(select(User).where(User.telegram_id == telegram_id))
        return result.scalar_one_or_none()

    async def upsert(self, telegram_id: str, termidesk_version: str | None = None) -> User:
        stmt = insert(User).values(
            telegram_id=telegram_id,
            termidesk_version=termidesk_version,
        ).on_conflict_do_update(
            index_elements=["telegram_id"],
            set_={"termidesk_version": termidesk_version, "updated_at": func.now()},
        )
        await self._session.execute(stmt)
        await self._session.flush()
        user = await self.get_by_telegram_id(telegram_id)
        assert user is not None
        return user

    async def set_version(self, telegram_id: str, version: str) -> User | None:
        user = await self.get_by_telegram_id(telegram_id)
        if user is None:
            return None
        user.termidesk_version = version
        await self._session.flush()
        return user