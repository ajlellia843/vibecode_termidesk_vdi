"""Add section_title, document_title, position, token_count to retrieval.chunks.

Revision ID: 003
Revises: 002
Create Date: 2025-01-01 00:00:02

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "chunks",
        sa.Column("section_title", sa.Text(), nullable=True),
        schema="retrieval",
    )
    op.add_column(
        "chunks",
        sa.Column("document_title", sa.String(512), nullable=True),
        schema="retrieval",
    )
    op.add_column(
        "chunks",
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        schema="retrieval",
    )
    op.add_column(
        "chunks",
        sa.Column("token_count", sa.Integer(), nullable=False, server_default="0"),
        schema="retrieval",
    )


def downgrade() -> None:
    op.drop_column("chunks", "token_count", schema="retrieval")
    op.drop_column("chunks", "position", schema="retrieval")
    op.drop_column("chunks", "document_title", schema="retrieval")
    op.drop_column("chunks", "section_title", schema="retrieval")
