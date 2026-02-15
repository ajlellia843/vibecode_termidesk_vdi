"""Dialog service: retrieval + prompt assembly + LLM + persistence."""
import json
import os
import re
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


def _merge_adjacent_chunks(chunks: list[RetrievalResultItem]) -> list[RetrievalResultItem]:
    """Merge consecutive chunks from same document (same document_title/source, consecutive position)."""
    if not chunks:
        return []
    key = lambda c: (c.document_title or c.source or "", c.position)
    sorted_chunks = sorted(chunks, key=key)
    merged: list[RetrievalResultItem] = []
    current_doc = None
    current_pos = -2
    current_text: list[str] = []
    current_item: RetrievalResultItem | None = None
    for c in sorted_chunks:
        doc_key = c.document_title or c.source or ""
        if doc_key == current_doc and c.position == current_pos + 1 and current_item:
            current_text.append(c.text)
            current_pos = c.position
        else:
            if current_item:
                merged.append(
                    RetrievalResultItem(
                        chunk_id=current_item.chunk_id,
                        text="\n\n".join(current_text),
                        source=current_item.source,
                        score=current_item.score,
                        document_title=current_item.document_title,
                        section_title=current_item.section_title,
                        position=current_item.position,
                    )
                )
            current_doc = doc_key
            current_pos = c.position
            current_text = [c.text]
            current_item = c
    if current_item:
        merged.append(
            RetrievalResultItem(
                chunk_id=current_item.chunk_id,
                text="\n\n".join(current_text),
                source=current_item.source,
                score=current_item.score,
                document_title=current_item.document_title,
                section_title=current_item.section_title,
                position=current_item.position,
            )
        )
    return merged


def _limit_rag_context(
    chunks: list[RetrievalResultItem],
    max_chunks: int,
    max_chars: int,
) -> list[RetrievalResultItem]:
    """Take up to max_chunks, total length <= max_chars (by score order)."""
    out: list[RetrievalResultItem] = []
    total = 0
    for c in chunks:
        if len(out) >= max_chunks or total + len(c.text) > max_chars:
            break
        out.append(c)
        total += len(c.text) + 2
    return out


def _is_likely_gibberish(message: str) -> bool:
    """Single token or no Cyrillic with very few words often means off-topic/gibberish for RU support."""
    words = re.findall(r"\w+", message.strip())
    if len(words) < 2:
        return True
    has_cyrillic = any(any("\u0400" <= c <= "\u04ff" for c in w) for w in words)
    if not has_cyrillic and len(words) < 3:
        return True
    return False


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
        rag_max_chunks: int = 5,
        rag_max_context_chars: int = 3000,
        rag_strict_mode: bool = False,
    ) -> None:
        self._session_factory = session_factory
        self._retrieval = retrieval_client
        self._llm = llm_client
        self._retrieval_top_k = retrieval_top_k
        self._max_history_messages = max_history_messages
        self._rag_min_confidence = rag_min_confidence
        self._diagnostic_questions_max = diagnostic_questions_max
        self._rag_max_chunks = rag_max_chunks
        self._rag_max_context_chars = rag_max_context_chars
        self._rag_strict_mode = rag_strict_mode

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

            # message looks like gibberish (single token / no Cyrillic) — force diagnostic to avoid RAG noise
            if _is_likely_gibberish(user_message):
                # #region agent log
                _dlog("gibberish override", {"user_message_preview": user_message[:40], "top_score": top_score}, "H1")
                # #endregion
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

            # Limit and merge chunks for context
            merged = _merge_adjacent_chunks(rag_chunks)
            merged.sort(key=lambda c: -c.score)
            context_chunks = _limit_rag_context(
                merged,
                self._rag_max_chunks,
                self._rag_max_context_chars,
            )
            prompt = build_full_prompt(
                user_message,
                context_chunks,
                history,
                version=termidesk_version,
                strict_mode=self._rag_strict_mode,
            )
            # #region agent log
            _dlog("before llm.generate", {"prompt_len": len(prompt)}, "H2")
            # #endregion
            import time as _time
            t0 = _time.perf_counter()
            reply_text = await self._llm.generate(prompt, max_tokens=512)
            llm_latency_ms = int((_time.perf_counter() - t0) * 1000)
            # #region agent log
            _dlog("after llm.generate", {"reply_len": len(reply_text)}, "H2")
            # #endregion
            rag_info["llm_latency_ms"] = llm_latency_ms

            sources_top3 = [
                {"source": c.source, "chunk_id": c.chunk_id, "score": c.score}
                for c in context_chunks[:3]
            ]
            sources_line = ", ".join(s.get("source", "?") for s in sources_top3)
            reply_text = f"{reply_text}\n\nИсточники: {sources_line}\nВерсия: {termidesk_version}"

            await msg_repo.add(conv.id, "user", user_message)
            await msg_repo.add(conv.id, "assistant", reply_text)
            await session.commit()

            sources = [
                {"chunk_id": c.chunk_id, "text": c.text[:200], "source": c.source}
                for c in context_chunks[:3]
            ]
            return ChatResult(
                reply=reply_text,
                sources=sources,
                conversation_id=conv.id,
                mode="answer",
                version=termidesk_version,
                rag=rag_info,
            )
