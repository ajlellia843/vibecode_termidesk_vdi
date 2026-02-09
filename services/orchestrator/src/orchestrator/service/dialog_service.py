"""Dialog service: retrieval + prompt assembly + LLM + persistence."""
import json
import os
import time
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from orchestrator.clients import LLMClient, RetrievalClient, RetrievalResultItem
# #region agent log
def _dlog(msg: str, data: dict, hypothesis_id: str) -> None:
    p = os.environ.get("DEBUG_LOG_PATH", ".cursor/debug.log")
    try:
        with open(p, "a", encoding="utf-8") as f:
            f.write(json.dumps({"hypothesisId": hypothesis_id, "location": "dialog_service.py", "message": msg, "data": data, "timestamp": int(time.time() * 1000)}, ensure_ascii=False) + "\n")
    except Exception:
        pass
# #endregion
from orchestrator.repositories.conversation_repository import ConversationRepository
from orchestrator.repositories.message_repository import MessageRepository
from orchestrator.service.prompts import build_full_prompt


class DialogService:
    def __init__(
        self,
        session_factory: type[AsyncSession],
        retrieval_client: RetrievalClient,
        llm_client: LLMClient,
        retrieval_top_k: int = 5,
        max_history_messages: int = 10,
    ) -> None:
        self._session_factory = session_factory
        self._retrieval = retrieval_client
        self._llm = llm_client
        self._retrieval_top_k = retrieval_top_k
        self._max_history = max_history_messages

    async def reply(
        self,
        user_id: str,
        telegram_chat_id: str,
        user_message: str,
        conversation_id: UUID | None = None,
    ) -> tuple[str, list[dict[str, str]], UUID]:
        """
        Process user message and return (reply_text, sources, conversation_id).
        sources: list of {"chunk_id", "text", "source"} for references.
        """
        async with self._session_factory() as session:
            conv_repo = ConversationRepository(session)
            msg_repo = MessageRepository(session)

            if conversation_id:
                conv = await conv_repo.get_by_id(conversation_id)
                if conv is None:
                    conv = await conv_repo.get_or_create(user_id, telegram_chat_id)
            else:
                conv = await conv_repo.get_or_create(user_id, telegram_chat_id)

            history_msgs = await msg_repo.get_recent(
                conv.id, limit=self._max_history
            )
            history = [
                (m.role, m.content) for m in history_msgs
                if m.role in ("user", "assistant")
            ]

            # #region agent log
            _dlog("before retrieval.search", {"user_message": user_message[:50]}, "H2")
            # #endregion
            rag_chunks: list[RetrievalResultItem] = await self._retrieval.search(
                user_message, top_k=self._retrieval_top_k
            )
            # #region agent log
            _dlog("after retrieval.search", {"rag_len": len(rag_chunks)}, "H2")
            # #endregion
            prompt = build_full_prompt(user_message, rag_chunks, history)

            # #region agent log
            _dlog("before llm.generate", {"prompt_len": len(prompt)}, "H2")
            # #endregion
            reply_text = await self._llm.generate(prompt, max_tokens=512)
            # #region agent log
            _dlog("after llm.generate", {"reply_len": len(reply_text)}, "H2")
            # #endregion

            await msg_repo.add(conv.id, "user", user_message)
            await msg_repo.add(conv.id, "assistant", reply_text)
            await session.commit()

            sources = [
                {"chunk_id": c.chunk_id, "text": c.text[:200], "source": c.source}
                for c in rag_chunks
            ]
            return reply_text, sources, conv.id
