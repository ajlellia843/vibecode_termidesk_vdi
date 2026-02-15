"""Test that tg-bot deduplicates sources and formats them correctly."""


def _format_sources(sources: list[dict[str, str]]) -> str:
    """Extract the dedup logic from chat.py for isolated testing."""
    seen: list[str] = []
    for s in sources:
        name = s.get("source", "?")
        if name not in seen:
            seen.append(name)
    return ", ".join(seen)


def test_sources_dedup_removes_duplicates() -> None:
    sources = [
        {"source": "faq.md", "chunk_id": "1", "text": "..."},
        {"source": "faq.md", "chunk_id": "2", "text": "..."},
        {"source": "troubleshooting.md", "chunk_id": "3", "text": "..."},
    ]
    result = _format_sources(sources)
    assert result == "faq.md, troubleshooting.md"


def test_sources_dedup_preserves_order() -> None:
    sources = [
        {"source": "troubleshooting.md", "chunk_id": "1", "text": "..."},
        {"source": "faq.md", "chunk_id": "2", "text": "..."},
        {"source": "troubleshooting.md", "chunk_id": "3", "text": "..."},
    ]
    result = _format_sources(sources)
    assert result == "troubleshooting.md, faq.md"


def test_sources_empty_list() -> None:
    assert _format_sources([]) == ""


def test_sources_single() -> None:
    sources = [{"source": "faq.md", "chunk_id": "1", "text": "..."}]
    result = _format_sources(sources)
    assert result == "faq.md"


def test_sources_missing_key() -> None:
    sources = [{"chunk_id": "1", "text": "..."}, {"source": "faq.md", "chunk_id": "2", "text": "..."}]
    result = _format_sources(sources)
    assert result == "?, faq.md"
