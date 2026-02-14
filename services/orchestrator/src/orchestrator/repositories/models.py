"""SQLAlchemy models for orchestrator schema."""
from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Conversation(Base):
    __tablename__ = "conversations"
    __table_args__ = {"schema": "orchestrator"}

    id: Mapped[uuid4] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    telegram_chat_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    messages: Mapped[list["Message"]] = relationship("Message", back_populates="conversation")


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = {"schema": "orchestrator"}

    id: Mapped[uuid4] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    conversation_id: Mapped[uuid4] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orchestrator.conversations.id"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(32), nullable=False)  # user | assistant | system
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    conversation: Mapped["Conversation"] = relationship("Conversation", back_populates="messages")


class User(Base):
    __tablename__ = "users"
    __table_args__ = {"schema": "orchestrator"}

    id: Mapped[uuid4] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    telegram_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    termidesk_version: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
