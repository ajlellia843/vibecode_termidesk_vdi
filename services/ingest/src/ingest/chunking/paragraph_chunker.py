"""Paragraph- and sentence-aware chunker: split by paragraphs, respect sentence boundaries."""
import re
from ingest.chunking.base import BaseChunker


_SENTENCE_END = re.compile(r"(?<=[.!?])\s+|\n+")


def _split_paragraphs(text: str) -> list[str]:
    return [p.strip() for p in text.split("\n\n") if p.strip()]


def _split_sentences(text: str) -> list[str]:
    """Split text into sentences (by . ! ? followed by space or newline)."""
    if not text.strip():
        return []
    parts = re.split(r"([.!?]\s+)", text)
    sentences = []
    buf = ""
    for i, p in enumerate(parts):
        buf += p
        if re.search(r"[.!?]\s*$", p):
            sentences.append(buf.strip())
            buf = ""
    if buf.strip():
        sentences.append(buf.strip())
    return [s for s in sentences if s]


def _cut_at_sentence(text: str, max_len: int) -> tuple[str, str]:
    """Split at last sentence boundary before max_len. Returns (before, rest)."""
    if len(text) <= max_len:
        return text, ""
    search_region = text[: max_len + 50]
    last = -1
    for m in re.finditer(r"[.!?]\s+", search_region):
        last = m.end()
    if last <= 0:
        last = max(search_region.rfind(". "), search_region.rfind("! "), search_region.rfind("? "))
        if last >= 0:
            last += 2
    if last <= 0:
        last = search_region.rfind("\n")
        if last >= 0:
            last += 1
    if last <= 0:
        last = max_len
    return text[:last].strip(), text[last:].lstrip()


class ParagraphChunker(BaseChunker):
    """Chunk by paragraphs; respect sentence boundaries; optional overlap."""

    def __init__(self, chunk_size: int = 900, overlap: int = 180) -> None:
        self._chunk_size = max(chunk_size, 100)
        self._overlap = min(max(0, overlap), self._chunk_size // 2)

    def chunk(self, text: str) -> list[str]:
        if not text or not text.strip():
            return []
        text = text.strip()
        paragraphs = _split_paragraphs(text)
        if not paragraphs:
            return []
        chunks: list[str] = []
        buf: list[str] = []
        length = 0
        for p in paragraphs:
            add_len = len(p) + (2 if buf else 0)
            if length + add_len <= self._chunk_size:
                buf.append(p)
                length += add_len
                continue
            if buf:
                chunks.append("\n\n".join(buf))
            if len(p) <= self._chunk_size:
                if self._overlap and buf:
                    overlap_text = "\n\n".join(buf)
                    start = max(0, len(overlap_text) - self._overlap)
                    tail = overlap_text[start:].lstrip()
                    buf = [tail, p] if tail else [p]
                    length = len(tail) + len(p) + 4 if tail else len(p) + 2
                else:
                    buf = [p]
                    length = len(p) + 2
                continue
            for sent in _split_sentences(p):
                add_len = len(sent) + (1 if buf else 0)
                if length + add_len <= self._chunk_size:
                    buf.append(sent)
                    length += add_len
                    continue
                if buf:
                    chunks.append(" ".join(buf))
                if len(sent) <= self._chunk_size:
                    buf = [sent]
                    length = len(sent) + 1
                else:
                    before, rest = _cut_at_sentence(sent, self._chunk_size)
                    chunks.append(before)
                    buf = [rest] if rest else []
                    length = len(rest) + 1 if rest else 0
        if buf:
            chunks.append("\n\n".join(buf) if "\n\n" in " ".join(buf) else " ".join(buf))
        return [c for c in chunks if c.strip()]
