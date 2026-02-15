"""Dialog service: retrieval + prompt assembly + LLM + persistence."""
import re
import time
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from orchestrator.api.schemas import ChatResult
from orchestrator.clients import LLMClient, RetrievalClient, RetrievalResultItem
from orchestrator.repositories.conversation_repository import ConversationRepository
from orchestrator.repositories.message_repository import MessageRepository
from orchestrator.repositories.user_repository import UserRepository
from orchestrator.service.context_utils import (
    extract_relevant_section,
    normalize_and_dedup,
)
from orchestrator.service.prompts import build_full_prompt
from orchestrator.service import rag_text

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
        rag_max_chunks: int = 3,
        rag_max_context_chars: int = 2500,
        rag_strict_mode: bool = False,
        rag_join_neighbors: bool = True,
        rag_dedup_lines: bool = True,
        rag_section_extraction: bool = True,
        rag_normalize_text: bool = True,
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
        self._rag_join_neighbors = rag_join_neighbors
        self._rag_dedup_lines = rag_dedup_lines
        self._rag_section_extraction = rag_section_extraction
        self._rag_normalize_text = rag_normalize_text

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
            rag_chunks: list[RetrievalResultItem] = await self._retrieval.search(
                user_message, top_k=self._retrieval_top_k, version=termidesk_version
            )

            top_score = max((c.score for c in rag_chunks), default=0.0)
            rag_info = {
                "retrieved_count": len(rag_chunks),
                "top_score": top_score,
                "threshold": self._rag_min_confidence,
            }

            # diagnostic: empty or below threshold -- do not call LLM
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

            # message looks like gibberish -- force diagnostic
            if _is_likely_gibberish(user_message):
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

            # --- Context assembly ---
            # 1. Sort by score DESC, dedup by chunk_id
            seen_ids: set[str] = set()
            unique_chunks: list[RetrievalResultItem] = []
            for c in sorted(rag_chunks, key=lambda c: -c.score):
                if c.chunk_id not in seen_ids:
                    seen_ids.add(c.chunk_id)
                    unique_chunks.append(c)

            # 2. Optionally merge neighbors
            if self._rag_join_neighbors:
                merged = _merge_adjacent_chunks(unique_chunks)
                merged.sort(key=lambda c: -c.score)
                if self._rag_normalize_text:
                    merged = [
                        RetrievalResultItem(
                            chunk_id=c.chunk_id,
                            text=rag_text.normalize_text(c.text),
                            source=c.source,
                            score=c.score,
                            document_title=c.document_title,
                            section_title=c.section_title,
                            position=c.position,
                        )
                        for c in merged
                    ]
            else:
                merged = unique_chunks

            # 3. Limit to max_chunks / max_context_chars
            context_chunks = _limit_rag_context(
                merged, self._rag_max_chunks, self._rag_max_context_chars,
            )

            # 4. Section extraction and/or normalization per chunk (rag_text) or legacy dedup (context_utils)
            if self._rag_section_extraction or self._rag_normalize_text:
                cleaned_chunks = []
                for c in context_chunks:
                    txt = c.text
                    if self._rag_section_extraction:
                        txt = rag_text.best_section(txt, user_message)
                    if self._rag_normalize_text:
                        txt = rag_text.normalize_text(txt)
                    cleaned_chunks.append(
                        RetrievalResultItem(
                            chunk_id=c.chunk_id,
                            text=txt,
                            source=c.source,
                            score=c.score,
                            document_title=c.document_title,
                            section_title=c.section_title,
                            position=c.position,
                        )
                    )
                context_chunks = cleaned_chunks
            elif self._rag_dedup_lines:
                cleaned_chunks = []
                for c in context_chunks:
                    cleaned = extract_relevant_section(c.text, user_message)
                    cleaned = normalize_and_dedup(cleaned)
                    cleaned_chunks.append(
                        RetrievalResultItem(
                            chunk_id=c.chunk_id,
                            text=cleaned,
                            source=c.source,
                            score=c.score,
                            document_title=c.document_title,
                            section_title=c.section_title,
                            position=c.position,
                        )
                    )
                context_chunks = cleaned_chunks

            prompt = build_full_prompt(
                user_message,
                context_chunks,
                history,
                version=termidesk_version,
                strict_mode=self._rag_strict_mode,
                max_context_chars=self._rag_max_context_chars,
            )

            t0 = time.perf_counter()
            reply_text = await self._llm.generate(prompt, max_tokens=512)
            llm_latency_ms = int((time.perf_counter() - t0) * 1000)
            rag_info["llm_latency_ms"] = llm_latency_ms

            await msg_repo.add(conv.id, "user", user_message)
            await msg_repo.add(conv.id, "assistant", reply_text)
            await session.commit()

            # Dedup sources by source name
            seen_sources: set[str] = set()
            sources: list[dict[str, str]] = []
            for c in context_chunks[:3]:
                if c.source not in seen_sources:
                    seen_sources.add(c.source)
                    sources.append(
                        {"chunk_id": c.chunk_id, "text": c.text[:200], "source": c.source}
                    )
            return ChatResult(
                reply=reply_text,
                sources=sources,
                conversation_id=conv.id,
                mode="answer",
                version=termidesk_version,
                rag=rag_info,
            )
