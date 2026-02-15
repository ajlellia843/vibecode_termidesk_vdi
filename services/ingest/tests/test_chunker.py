"""Tests for ParagraphChunker: no mid-word cuts, list preservation, short chunk merging."""
import re

from ingest.chunking.paragraph_chunker import ParagraphChunker, _cut_at_sentence
from ingest.pipeline import merge_short_chunks


def test_no_mid_word_cut() -> None:
    """Chunks must not end in the middle of a word."""
    # Build a long text with no sentence-ending punctuation — forces word-boundary fallback
    words = ["слово"] * 300  # each 5 chars + space = ~1800 chars total
    long_text = " ".join(words)
    chunker = ParagraphChunker(chunk_size=200, overlap=0)
    chunks = chunker.chunk(long_text)
    assert len(chunks) > 1, "Should produce multiple chunks"
    for chunk in chunks:
        # Each chunk should end at a word boundary (no partial Cyrillic/Latin)
        stripped = chunk.rstrip()
        if stripped:
            assert not re.search(r"\w$", stripped) or stripped[-1].isalpha(), (
                f"Chunk should end at a word boundary, got: ...{stripped[-20:]}"
            )
            # The next character in the original (if any) should be a space or newline
            idx = long_text.find(stripped)
            if idx >= 0:
                end_pos = idx + len(stripped)
                if end_pos < len(long_text):
                    next_char = long_text[end_pos]
                    assert next_char in (" ", "\n", "\r"), (
                        f"Character after chunk end should be whitespace, got '{next_char}'"
                    )


def test_cut_at_sentence_prefers_word_boundary() -> None:
    """_cut_at_sentence should not split mid-word even without punctuation."""
    text = "aaaa bbbb cccc dddd eeee ffff"
    before, rest = _cut_at_sentence(text, 14)
    # max_len=14 falls in the middle of "dddd"; should cut at space before it
    assert not before.endswith("d") or before.endswith("dddd"), (
        f"Should not split mid-word: '{before}'"
    )
    assert " " not in before[-1:] or before[-1] != " ", "Should strip trailing space"


def test_numbered_list_stays_intact() -> None:
    """Numbered list items should not be split across chunks."""
    items = [f"{i}. Пункт номер {i} с длинным описанием действия" for i in range(1, 20)]
    text = "\n".join(items)
    chunker = ParagraphChunker(chunk_size=200, overlap=0)
    chunks = chunker.chunk(text)
    for chunk in chunks:
        # No chunk should end with a partial numbered item like "... или п"
        lines = chunk.strip().split("\n")
        for line in lines:
            line = line.strip()
            if not line:
                continue
            # If it starts with a number, the full item should be present
            if re.match(r"^\d+\.\s", line):
                assert len(line) > 5, f"List item seems truncated: '{line}'"


def test_cut_at_sentence_with_list_boundary() -> None:
    """_cut_at_sentence should prefer cutting before a list item."""
    text = "Введение в систему.\n1. Первый пункт\n2. Второй пункт\n3. Третий пункт"
    before, rest = _cut_at_sentence(text, 30)
    # Should cut at the sentence end or before a list item, not mid-item
    assert "Введение" in before
    assert not before.endswith("Пер")  # not mid-word


def test_short_chunks_merged() -> None:
    """Chunks shorter than 150 chars should be merged with neighbors."""
    chunks = ["Короткий чанк.", "Ещё один.", "Длинный текст " * 20]
    result = merge_short_chunks(chunks)
    # First two are short (<150), should be merged
    assert len(result) <= 2, f"Expected merging of short chunks, got {len(result)} chunks"
    # The merged chunk should contain both short texts
    assert "Короткий" in result[0]
    assert "Ещё один" in result[0]
