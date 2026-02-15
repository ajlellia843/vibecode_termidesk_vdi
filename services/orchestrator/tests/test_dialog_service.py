"""Unit tests for DialogService: threshold, diagnostic, answer modes."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from orchestrator.clients.retrieval_client import RetrievalResultItem
from orchestrator.service.dialog_service import DialogService


@pytest.fixture
def mock_session_factory() -> MagicMock:
    session = MagicMock()
    session.commit = AsyncMock()
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=session)
    cm.__aexit__ = AsyncMock(return_value=None)
    factory = MagicMock()
    factory.return_value = cm
    return factory


@pytest.fixture
def mock_user_with_version() -> MagicMock:
    user = MagicMock()
    user.termidesk_version = "6.1 (latest)"
    return user


@pytest.fixture
def mock_conv() -> MagicMock:
    conv = MagicMock()
    conv.id = uuid4()
    return conv


@pytest.mark.asyncio
async def test_retrieval_empty_returns_diagnostic_does_not_call_llm(
    mock_session_factory: MagicMock,
    mock_user_with_version: MagicMock,
    mock_conv: MagicMock,
) -> None:
    mock_retrieval = MagicMock()
    mock_retrieval.search = AsyncMock(return_value=[])
    mock_llm = MagicMock()
    mock_llm.generate = AsyncMock(return_value="LLM reply")

    with (
        patch("orchestrator.service.dialog_service.UserRepository") as UR,
        patch("orchestrator.service.dialog_service.ConversationRepository") as CR,
        patch("orchestrator.service.dialog_service.MessageRepository") as MR,
    ):
        UR.return_value.get_by_telegram_id = AsyncMock(return_value=mock_user_with_version)
        CR.return_value.get_by_id = AsyncMock(return_value=None)
        CR.return_value.get_or_create = AsyncMock(return_value=mock_conv)
        MR.return_value.add = AsyncMock()
        MR.return_value.get_recent = AsyncMock(return_value=[])

        service = DialogService(
            session_factory=mock_session_factory,
            retrieval_client=mock_retrieval,
            llm_client=mock_llm,
            retrieval_top_k=5,
            max_history_messages=10,
            rag_min_confidence=0.30,
            diagnostic_questions_max=2,
        )
        result = await service.reply(
            user_id="123",
            telegram_chat_id="123",
            user_message="random question xyz",
            conversation_id=None,
        )

    mock_llm.generate.assert_not_called()
    assert result.mode == "diagnostic"
    assert "ошибк" in result.reply.lower() or "логи" in result.reply.lower() or "шаге" in result.reply.lower()
    assert result.sources == []
    assert result.rag is not None
    assert result.rag["retrieved_count"] == 0


@pytest.mark.asyncio
async def test_retrieval_below_threshold_returns_diagnostic_does_not_call_llm(
    mock_session_factory: MagicMock,
    mock_user_with_version: MagicMock,
    mock_conv: MagicMock,
) -> None:
    low_score_chunks = [
        RetrievalResultItem(chunk_id="1", text="Some text.", source="a.md", score=0.1),
        RetrievalResultItem(chunk_id="2", text="Other.", source="b.md", score=0.2),
    ]
    mock_retrieval = MagicMock()
    mock_retrieval.search = AsyncMock(return_value=low_score_chunks)
    mock_llm = MagicMock()
    mock_llm.generate = AsyncMock(return_value="LLM reply")

    with (
        patch("orchestrator.service.dialog_service.UserRepository") as UR,
        patch("orchestrator.service.dialog_service.ConversationRepository") as CR,
        patch("orchestrator.service.dialog_service.MessageRepository") as MR,
    ):
        UR.return_value.get_by_telegram_id = AsyncMock(return_value=mock_user_with_version)
        CR.return_value.get_by_id = AsyncMock(return_value=None)
        CR.return_value.get_or_create = AsyncMock(return_value=mock_conv)
        MR.return_value.add = AsyncMock()
        MR.return_value.get_recent = AsyncMock(return_value=[])

        service = DialogService(
            session_factory=mock_session_factory,
            retrieval_client=mock_retrieval,
            llm_client=mock_llm,
            retrieval_top_k=5,
            max_history_messages=10,
            rag_min_confidence=0.30,
            diagnostic_questions_max=2,
        )
        result = await service.reply(
            user_id="123",
            telegram_chat_id="123",
            user_message="question",
            conversation_id=None,
        )

    mock_llm.generate.assert_not_called()
    assert result.mode == "diagnostic"
    assert result.rag is not None
    assert result.rag["top_score"] == 0.2
    assert result.rag["top_score"] < 0.30


@pytest.mark.asyncio
async def test_retrieval_above_threshold_calls_llm_returns_answer(
    mock_session_factory: MagicMock,
    mock_user_with_version: MagicMock,
    mock_conv: MagicMock,
) -> None:
    high_score_chunks = [
        RetrievalResultItem(chunk_id="1", text="Termidesk is VDI.", source="faq.md", score=0.9),
    ]
    mock_retrieval = MagicMock()
    mock_retrieval.search = AsyncMock(return_value=high_score_chunks)
    mock_llm = MagicMock()
    mock_llm.generate = AsyncMock(return_value="Termidesk — это платформа VDI.")

    with (
        patch("orchestrator.service.dialog_service.UserRepository") as UR,
        patch("orchestrator.service.dialog_service.ConversationRepository") as CR,
        patch("orchestrator.service.dialog_service.MessageRepository") as MR,
    ):
        UR.return_value.get_by_telegram_id = AsyncMock(return_value=mock_user_with_version)
        CR.return_value.get_by_id = AsyncMock(return_value=None)
        CR.return_value.get_or_create = AsyncMock(return_value=mock_conv)
        MR.return_value.add = AsyncMock()
        MR.return_value.get_recent = AsyncMock(return_value=[])

        service = DialogService(
            session_factory=mock_session_factory,
            retrieval_client=mock_retrieval,
            llm_client=mock_llm,
            retrieval_top_k=5,
            max_history_messages=10,
            rag_min_confidence=0.30,
            diagnostic_questions_max=2,
        )
        result = await service.reply(
            user_id="123",
            telegram_chat_id="123",
            user_message="Что такое Termidesk?",
            conversation_id=None,
        )

    mock_llm.generate.assert_called_once()
    assert result.mode == "answer"
    # Sources/version are in structured fields, NOT appended to reply text
    assert "Источники:" not in result.reply
    assert "Версия:" not in result.reply
    assert result.version == "6.1 (latest)"
    assert len(result.sources) >= 1
    assert result.sources[0]["source"] == "faq.md"
    assert result.rag is not None
    assert result.rag["top_score"] >= 0.30
