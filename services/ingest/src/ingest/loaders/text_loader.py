"""Load .md and .txt files."""
from pathlib import Path

from ingest.loaders.base import BaseLoader


class TextLoader(BaseLoader):
    @property
    def extensions(self) -> tuple[str, ...]:
        return (".md", ".txt")

    def load(self, path: Path) -> str:
        return path.read_text(encoding="utf-8", errors="replace")
