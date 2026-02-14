"""Add documents.version and optional ivfflat index on chunks.embedding.

Revision ID: 002
Revises: 001
Create Date: 2025-01-01 00:00:01

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column("version", sa.Text(), nullable=False, server_default="6.1 (latest)"),
        schema="retrieval",
    )
    op.create_index(
        "ix_retrieval_documents_version",
        "documents",
        ["version"],
        schema="retrieval",
    )
    # Optional: ivfflat index on chunks.embedding; skip if unsupported
    try:
        op.execute(
            "CREATE INDEX ix_retrieval_chunks_embedding_ivfflat "
            "ON retrieval.chunks USING ivfflat (embedding vector_l2_ops) WITH (lists = 100)"
        )
    except Exception:
        # If pgvector does not support ivfflat or fails (e.g. empty table), skip
        pass


def downgrade() -> None:
    try:
        op.execute("DROP INDEX IF EXISTS retrieval.ix_retrieval_chunks_embedding_ivfflat")
    except Exception:
        pass
    op.drop_index("ix_retrieval_documents_version", table_name="documents", schema="retrieval")
    op.drop_column("documents", "version", schema="retrieval")
