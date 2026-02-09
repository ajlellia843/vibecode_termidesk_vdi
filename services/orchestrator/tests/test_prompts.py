"""Tests for prompt assembly."""
import pytest

from orchestrator.clients.retrieval_client import RetrievalResultItem
from orchestrator.service.prompts import (
    build_full_prompt,
    build_rag_context,
    build_messages_context,
)


def test_build_rag_context_empty() -> None:
    assert "(Релевантных фрагментов" in build_rag_context([])


def test_build_rag_context_with_chunks() -> None:
    chunks = [
        RetrievalResultItem(chunk_id="1", text="FAQ: Termidesk — это VDI.", source="faq.md", score=0.9),
    ]
    out = build_rag_context(chunks)
    assert "faq.md" in out
    assert "Termidesk" in out


def test_build_messages_context_empty() -> None:
    assert build_messages_context([]) == ""


def test_build_messages_context() -> None:
    history = [("user", "Как подключиться?"), ("assistant", "Установите клиент...")]
    out = build_messages_context(history)
    assert "Пользователь" in out
    assert "Ассистент" in out
    assert "Как подключиться?" in out


def test_build_full_prompt_includes_system_and_user() -> None:
    chunks = [
        RetrievalResultItem(chunk_id="1", text="Контекст из базы.", source="faq.md", score=0.9),
    ]
    prompt = build_full_prompt("Что такое Termidesk?", chunks, [])
    assert "Ты — бот поддержки" in prompt or "Termidesk" in prompt
    assert "Контекст из базы" in prompt
    assert "Что такое Termidesk?" in prompt
    assert "Ответ:" in prompt
