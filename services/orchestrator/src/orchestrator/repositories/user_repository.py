"""User repository: get, upsert, set version."""
import json
import os
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
        # #region agent log
        _path = os.environ.get("DEBUG_LOG_PATH", ".cursor/debug.log")
        try:
            with open(_path, "a", encoding="utf-8") as _f:
                _f.write(json.dumps({"location": "user_repository.py", "message": "upsert call", "data": {"telegram_id": telegram_id, "termidesk_version": termidesk_version}, "hypothesisId": "H1", "timestamp": __import__("time").time() * 1000}, ensure_ascii=False) + "\n")
        except Exception:
            pass
        # #endregion
        set_dict = {"updated_at": func.now()}
        if termidesk_version is not None:
            set_dict["termidesk_version"] = termidesk_version
        stmt = insert(User).values(
            telegram_id=telegram_id,
            termidesk_version=termidesk_version,
        ).on_conflict_do_update(
            index_elements=["telegram_id"],
            set_=set_dict,
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