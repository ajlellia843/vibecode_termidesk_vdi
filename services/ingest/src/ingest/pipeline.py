"""Ingest pipeline: load files -> chunk -> embed -> write to DB."""
import sys
from pathlib import Path
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from ingest.chunking import SimpleChunker
from ingest.db.models import Chunk, Document
from ingest.loaders import PDFLoader, TextLoader
from shared.embedder import Embedder


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
    kb_default_version: str = "6.1 (latest)",
    embedder: Embedder | None = None,
) -> int:
    engine = create_async_engine(database_url, echo=False)
    session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    chunker = SimpleChunker(chunk_size=chunk_size, overlap=chunk_overlap)
    if embedder is None:
        embedder = Embedder()

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
                version=kb_default_version,
            )
            session.add(doc)
            await session.flush()

            chunks_text = chunker.chunk(content)
            embeddings = embedder.embed_texts(chunks_text) if chunks_text else []
            chunk_embeddings: list[tuple[uuid4, list[float] | None]] = []
            for i, chunk_text in enumerate(chunks_text):
                emb = embeddings[i] if i < len(embeddings) else None
                chunk = Chunk(
                    id=uuid4(),
                    document_id=doc.id,
                    text=chunk_text,
                    index_in_doc=i,
                    embedding=None,
                )
                session.add(chunk)
                chunk_embeddings.append((chunk.id, emb))
                total_chunks += 1
            await session.flush()
            # Write embedding via raw SQL (asyncpg does not serialize vector without register_vector)
            num_emb = 0
            for cid, emb in chunk_embeddings:
                if emb is not None:
                    emb_str = "[" + ",".join(str(x) for x in emb) + "]"
                    result = await session.execute(
                        text(
                            "UPDATE retrieval.chunks SET embedding = CAST(:emb AS vector) WHERE id = CAST(:id AS uuid)"
                        ),
                        {"emb": emb_str, "id": str(cid)},
                    )
                    num_emb += result.rowcount
            if num_emb > 0:
                print(f"[ingest] Updated {num_emb} chunk embeddings via SQL", file=sys.stderr)
        await session.commit()
    await engine.dispose()
    return total_chunks
