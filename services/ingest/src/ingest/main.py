"""Ingest CLI - run pipeline to load knowledge into DB."""
import asyncio
import sys

from ingest.config import IngestSettings
from ingest.pipeline import run_ingest


def main() -> None:
    settings = IngestSettings()
    n = asyncio.run(
        run_ingest(
            database_url=settings.database_url,
            knowledge_path=settings.knowledge_path,
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
            kb_default_version=settings.kb_default_version,
            embedder_backend=settings.embedder_backend,
            embedder_model_name=settings.embedder_model_name,
            embedding_dim=settings.embedding_dim,
        )
    )
    print(f"Ingested {n} chunks", file=sys.stderr)
    sys.exit(0)


if __name__ == "__main__":
    main()
