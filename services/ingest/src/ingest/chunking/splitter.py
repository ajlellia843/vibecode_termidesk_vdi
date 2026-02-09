"""Split text into overlapping chunks."""
from ingest.chunking.base import BaseChunker


class SimpleChunker(BaseChunker):
    def __init__(self, chunk_size: int = 500, overlap: int = 50) -> None:
        self._chunk_size = chunk_size
        self._overlap = overlap

    def chunk(self, text: str) -> list[str]:
        if not text or not text.strip():
            return []
        text = text.strip()
        chunks = []
        start = 0
        while start < len(text):
            end = start + self._chunk_size
            chunk = text[start:end]
            if chunk.strip():
                chunks.append(chunk.strip())
            start = end - self._overlap
            if start >= len(text):
                break
        return chunks
