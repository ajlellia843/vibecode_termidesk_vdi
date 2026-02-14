"""Dialog service: retrieval + prompt assembly + LLM + persistence."""
import json
import os
import time
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from orchestrator.api.schemas import ChatResult
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
from orchestrator.repositories.user_repository import UserRepository
from orchestrator.service.prompts import build_full_prompt

NEED_VERSION_REPLY = (
    "Чтобы получать ответы по документации, выберите версию Termidesk (кнопка «Версия» или /version)."
)

DIAGNOSTIC_QUESTIONS = [
    "Какой текст ошибки или код ошибки вы видите?",
    "На каком шаге возникает проблема? (подключение / логин / запуск ВМ / тонкий клиент)",
    "Это происходит на клиенте или на сервере Termidesk?",
]

DIAGNOSTIC_COLLECT = (
    "Пожалуйста, подготовьте: версию Termidesk, ОС клиента или тонкого клиента, "
    "логи и журналы (см. документацию по сбору логов для вашей версии)."
)


def _build_diagnostic_reply(questions_max: int) -> str:
    parts = [
        "По вашему запросу в базе знаний не найдено достаточно релевантной информации. Чтобы уточнить ситуацию:",
        "",
    ]
    for q in DIAGNOSTIC_QUESTIONS[:questions_max]:
        parts.append(f"• {q}")
    parts.extend(["", DIAGNOSTIC_COLLECT])
    return "\n".join(parts)


class DialogService:
    def __init__(
        self,
        session_factory: type[AsyncSession],
        retrieval_client: RetrievalClient,
        llm_client: LLMClient,
        retrieval_top_k: int = 5,
        max_history_messages: int = 10,
        rag_min_confidence: float = 0.30,
        diagnostic_questions_max: int = 2,
    ) -> None:
        self._session_factory = session_factory
        self._retrieval = retrieval_client
        self._llm = llm_client
        self._retrieval_top_k = retrieval_top_k
        self._max_history_messages = max_history_messages
        self._rag_min_confidence = rag_min_confidence
        self._diagnostic_questions_max = diagnostic_questions_max

    async def reply(
        self,
        user_id: str,
        telegram_chat_id: str,
        user_message: str,
        conversation_id: UUID | None = None,
    ) -> ChatResult:
        """
        Process user message and return ChatResult (reply, sources, conversation_id, mode, version, rag).
        """
        async with self._session_factory() as session:
            conv_repo = ConversationRepository(session)
            msg_repo = MessageRepository(session)
            user_repo = UserRepository(session)

            user = await user_repo.get_by_telegram_id(user_id)
            termidesk_version: str | None = user.termidesk_version if user else None

            if conversation_id:
                conv = await conv_repo.get_by_id(conversation_id)
                if conv is None:
                    conv = await conv_repo.get_or_create(user_id, telegram_chat_id)
            else:
                conv = await conv_repo.get_or_create(user_id, telegram_chat_id)

            history_msgs = await msg_repo.get_recent(
                conv.id, limit=self._max_history_messages
            )
            history = [
                (m.role, m.content) for m in history_msgs
                if m.role in ("user", "assistant")
            ]

            # need_version: user has not selected version
            if termidesk_version is None:
                reply_text = NEED_VERSION_REPLY
                await msg_repo.add(conv.id, "user", user_message)
                await msg_repo.add(conv.id, "assistant", reply_text)
                await session.commit()
                return ChatResult(
                    reply=reply_text,
                    sources=[],
                    conversation_id=conv.id,
                    mode="need_version",
                    version=None,
                    rag=None,
                )

            # retrieval with version
            # #region agent log
            _dlog("before retrieval.search", {"user_message": user_message[:50], "version": termidesk_version}, "H2")
            # #endregion
            rag_chunks: list[RetrievalResultItem] = await self._retrieval.search(
                user_message, top_k=self._retrieval_top_k, version=termidesk_version
            )
            # #region agent log
            _dlog("after retrieval.search", {"rag_len": len(rag_chunks)}, "H2")
            # #endregion

            top_score = max((c.score for c in rag_chunks), default=0.0)
            rag_info = {
                "retrieved_count": len(rag_chunks),
                "top_score": top_score,
                "threshold": self._rag_min_confidence,
            }
            # #region agent log
            _dlog("threshold check", {"top_score": top_score, "threshold": self._rag_min_confidence, "branch": "diagnostic" if (not rag_chunks or top_score < self._rag_min_confidence) else "answer", "scores": [round(c.score, 4) for c in rag_chunks[:5]]}, "H1")
            # #endregion

            # diagnostic: empty or below threshold — do not call LLM
            if not rag_chunks or top_score < self._rag_min_confidence:
                reply_text = _build_diagnostic_reply(self._diagnostic_questions_max)
                await msg_repo.add(conv.id, "user", user_message)
                await msg_repo.add(conv.id, "assistant", reply_text)
                await session.commit()
                return ChatResult(
                    reply=reply_text,
                    sources=[],
                    conversation_id=conv.id,
                    mode="diagnostic",
                    version=termidesk_version,
                    rag=rag_info,
                )

            # answer: build prompt, call LLM, append sources and version to reply
            prompt = build_full_prompt(
                user_message, rag_chunks, history, version=termidesk_version
            )
            # #region agent log
            _dlog("before llm.generate", {"prompt_len": len(prompt)}, "H2")
            # #endregion
            reply_text = await self._llm.generate(prompt, max_tokens=512)
            # #region agent log
            _dlog("after llm.generate", {"reply_len": len(reply_text)}, "H2")
            # #endregion

            sources_top3 = [
                {
                    "source": c.source,
                    "chunk_id": c.chunk_id,
                    "score": c.score,
                }
                for c in rag_chunks[:3]
            ]
            sources_line = ", ".join(s.get("source", "?") for s in sources_top3)
            reply_text = f"{reply_text}\n\nИсточники: {sources_line}\nВерсия: {termidesk_version}"

            await msg_repo.add(conv.id, "user", user_message)
            await msg_repo.add(conv.id, "assistant", reply_text)
            await session.commit()

            sources = [
                {"chunk_id": c.chunk_id, "text": c.text[:200], "source": c.source}
                for c in rag_chunks[:3]
            ]
            return ChatResult(
                reply=reply_text,
                sources=sources,
                conversation_id=conv.id,
                mode="answer",
                version=termidesk_version,
                rag=rag_info,
            )
