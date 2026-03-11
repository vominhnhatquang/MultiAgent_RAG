import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.postgres import Base


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    mode: Mapped[str] = mapped_column(String(10), nullable=False, default="strict")
    tier: Mapped[str] = mapped_column(String(10), nullable=False, default="hot")
    message_count: Mapped[int] = mapped_column(Integer, default=0)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    messages: Mapped[list["Message"]] = relationship(
        "Message", back_populates="session", cascade="all, delete-orphan",
        order_by="Message.created_at"
    )

    __table_args__ = (
        CheckConstraint("mode IN ('strict', 'general')", name="chk_sessions_mode"),
        CheckConstraint("tier IN ('hot', 'warm', 'cold')", name="chk_sessions_tier"),
        Index("idx_sessions_updated_at", "updated_at"),
        Index("idx_sessions_tier", "tier"),
    )


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(10), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    sources: Mapped[list | None] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), nullable=True
    )
    model_used: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    session: Mapped["Session"] = relationship("Session", back_populates="messages")
    feedback: Mapped["Feedback | None"] = relationship(
        "Feedback", back_populates="message", uselist=False, cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint("role IN ('user', 'assistant', 'system')", name="chk_messages_role"),
        Index("idx_messages_session_id", "session_id"),
        Index("idx_messages_created_at", "session_id", "created_at"),
    )


class Feedback(Base):
    __tablename__ = "feedback"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    message_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("messages.id", ondelete="CASCADE"), nullable=False
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False
    )
    rating: Mapped[str] = mapped_column(String(10), nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    message: Mapped["Message"] = relationship("Message", back_populates="feedback")

    __table_args__ = (
        CheckConstraint("rating IN ('thumbs_up', 'thumbs_down')", name="chk_feedback_rating"),
        UniqueConstraint("message_id", name="uq_feedback_message"),
        Index("idx_feedback_session_id", "session_id"),
        Index("idx_feedback_rating", "rating"),
    )
