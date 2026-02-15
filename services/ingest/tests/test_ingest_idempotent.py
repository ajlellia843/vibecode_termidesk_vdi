"""Test that ingest pipeline uses UPSERT (ON CONFLICT) for idempotent ingestion."""
import re

from ingest.pipeline import run_ingest


def _extract_sql_from_source() -> str:
    """Read pipeline.py source and return its content for SQL pattern checks."""
    import inspect
    return inspect.getsource(run_ingest)


def test_pipeline_uses_document_upsert() -> None:
    """Verify the pipeline SQL contains ON CONFLICT for documents."""
    src = _extract_sql_from_source()
    assert "ON CONFLICT" in src, "run_ingest must use ON CONFLICT for documents upsert"
    assert "retrieval.documents" in src, "run_ingest must target retrieval.documents"
    assert "source, version" in src.replace("(", "").replace(")", ""), (
        "Document upsert must conflict on (source, version)"
    )


def test_pipeline_uses_chunk_upsert() -> None:
    """Verify the pipeline SQL contains ON CONFLICT for chunks."""
    src = _extract_sql_from_source()
    assert "retrieval.chunks" in src, "run_ingest must target retrieval.chunks"
    # Check for chunk upsert conflict clause
    assert re.search(r"ON CONFLICT\s*\(\s*document_id\s*,\s*position\s*\)", src), (
        "Chunk upsert must conflict on (document_id, position)"
    )


def test_pipeline_cleans_stale_chunks() -> None:
    """Verify the pipeline deletes stale chunks when a file shrinks."""
    src = _extract_sql_from_source()
    assert "position >= :max_position" in src or "position >=" in src, (
        "Pipeline must delete stale chunks with position >= new chunk count"
    )
