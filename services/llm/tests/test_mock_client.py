"""Tests for mock LLM client."""
import pytest

from llm.client.mock_client import MockLLMClient


@pytest.mark.asyncio
async def test_mock_returns_fixed_phrase() -> None:
    client = MockLLMClient()
    text = await client.generate("Что такое Termidesk?", max_tokens=100)
    assert isinstance(text, str)
    assert len(text) > 0
    assert "mock" in text.lower() or "Termidesk" in text or "поддержк" in text
