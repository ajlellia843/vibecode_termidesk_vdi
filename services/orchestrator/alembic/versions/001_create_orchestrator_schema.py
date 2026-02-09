"""Create orchestrator schema and tables.

Revision ID: 001
Revises:
Create Date: 2025-01-01 00:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS orchestrator")
    op.create_table(
        "conversations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", sa.String(255), nullable=False),
        sa.Column("telegram_chat_id", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        schema="orchestrator",
    )
    op.create_index(
        "ix_orchestrator_conversations_user_id",
        "conversations",
        ["user_id"],
        schema="orchestrator",
    )
    op.create_index(
        "ix_orchestrator_conversations_telegram_chat_id",
        "conversations",
        ["telegram_chat_id"],
        schema="orchestrator",
    )
    op.create_table(
        "messages",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("conversation_id", UUID(as_uuid=True), sa.ForeignKey("orchestrator.conversations.id"), nullable=False),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        schema="orchestrator",
    )


def downgrade() -> None:
    op.drop_table("messages", schema="orchestrator")
    op.drop_table("conversations", schema="orchestrator")
    op.execute("DROP SCHEMA IF EXISTS orchestrator")
