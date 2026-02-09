"""Load .pdf files."""
from pathlib import Path

from ingest.loaders.base import BaseLoader


class PDFLoader(BaseLoader):
    @property
    def extensions(self) -> tuple[str, ...]:
        return (".pdf",)

    def load(self, path: Path) -> str:
        try:
            from pypdf import PdfReader
        except ImportError:
            return ""
        reader = PdfReader(str(path))
        parts = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                parts.append(text)
        return "\n\n".join(parts)
