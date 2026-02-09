"""Ingest pipeline: load files -> chunk -> embed (stub) -> write to DB."""
from pathlib import Path
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from ingest.chunking import SimpleChunker
from ingest.db.models import Chunk, Document
from ingest.embedding import StubEmbedder
from ingest.loaders import PDFLoader, TextLoader


def collect_files(knowledge_path: str) -> list[Path]:
    path = Path(knowledge_path)
    if not path.exists():
        return []
    exts = {".md", ".txt", ".pdf"}
    files = []
    for f in path.rglob("*"):
        if f.is_file() and f.suffix.lower() in exts:
            files.append(f)
    return files


def load_content(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        return PDFLoader().load(path)
    return TextLoader().load(path)


async def run_ingest(
    database_url: str,
    knowledge_path: str,
    chunk_size: int = 500,
    chunk_overlap: int = 50,
) -> int:
    engine = create_async_engine(database_url, echo=False)
    session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    chunker = SimpleChunker(chunk_size=chunk_size, overlap=chunk_overlap)
    embedder = StubEmbedder(dim=384)

    files = collect_files(knowledge_path)
    total_chunks = 0

    async with session_factory() as session:
        for path in files:
            try:
                content = load_content(path)
            except Exception:
                continue
            if not content.strip():
                continue
            source = path.name
            doc_path = str(path)
            doc = Document(
                id=uuid4(),
                source=source,
                path=doc_path,
                meta={"ingest_path": doc_path},
            )
            session.add(doc)
            await session.flush()

            chunks_text = chunker.chunk(content)
            for i, text in enumerate(chunks_text):
                embedder.embed(text)  # stub; real impl would store in Chunk.embedding
                chunk = Chunk(
                    id=uuid4(),
                    document_id=doc.id,
                    text=text,
                    index_in_doc=i,
                )
                session.add(chunk)
                total_chunks += 1
            await session.flush()
        await session.commit()
    await engine.dispose()
    return total_chunks
