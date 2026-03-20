"""Session manager: CRUD operations for chat sessions and messages."""
import uuid
from dataclasses import dataclass
from datetime import datetime

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.session import Message, Session

logger = structlog.get_logger(__name__)


@dataclass
class SessionData:
    """Session with its messages."""

    id: uuid.UUID
    title: str | None
    mode: str
    tier: str
    message_count: int
    created_at: datetime
    updated_at: datetime
    messages: list[dict]


@dataclass
class SessionSummary:
    """Session summary for listing."""

    id: uuid.UUID
    title: str | None
    mode: str
    tier: str
    message_count: int
    created_at: datetime
    updated_at: datetime


class SessionManager:
    """
    Manage chat sessions and messages.

    Operations:
        - create_session(mode) → session_id
        - get_session(session_id) → SessionData
        - add_message(session_id, role, content, metadata) → message_id
        - list_sessions(page, per_page) → list[SessionSummary]
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_session(
        self,
        mode: str = "strict",
        title: str | None = None,
    ) -> uuid.UUID:
        """
        Create a new chat session.

        Args:
            mode: "strict" or "general"
            title: Optional title (often first message text)

        Returns:
            New session ID
        """
        session = Session(
            mode=mode,
            title=title,
            tier="hot",  # New sessions start hot
        )
        self.db.add(session)
        await self.db.flush()

        logger.info("session.created", session_id=str(session.id), mode=mode)
        return session.id

    async def get_session(self, session_id: uuid.UUID) -> SessionData | None:
        """
        Get session with all messages.

        Args:
            session_id: Session UUID

        Returns:
            SessionData or None if not found
        """
        result = await self.db.execute(
            select(Session).where(Session.id == session_id)
        )
        session = result.scalars().first()

        if not session:
            return None

        # Load messages
        msg_result = await self.db.execute(
            select(Message)
            .where(Message.session_id == session_id)
            .order_by(Message.created_at)
        )
        messages = msg_result.scalars().all()

        return SessionData(
            id=session.id,
            title=session.title,
            mode=session.mode,
            tier=session.tier,
            message_count=session.message_count,
            created_at=session.created_at,
            updated_at=session.updated_at,
            messages=[
                {
                    "id": str(m.id),
                    "role": m.role,
                    "content": m.content,
                    "sources": m.sources,
                    "model_used": m.model_used,
                    "created_at": m.created_at.isoformat(),
                }
                for m in messages
            ],
        )

    async def add_message(
        self,
        session_id: uuid.UUID,
        role: str,
        content: str,
        sources: list | None = None,
        model_used: str | None = None,
    ) -> uuid.UUID:
        """
        Add a message to a session.

        Args:
            session_id: Session UUID
            role: "user", "assistant", or "system"
            content: Message content
            sources: Optional sources for assistant messages
            model_used: Optional model identifier

        Returns:
            New message ID
        """
        message = Message(
            session_id=session_id,
            role=role,
            content=content,
            sources=sources,
            model_used=model_used,
        )
        self.db.add(message)
        await self.db.flush()

        logger.debug(
            "message.added",
            session_id=str(session_id),
            role=role,
            message_id=str(message.id),
        )
        return message.id

    async def get_history(
        self,
        session_id: uuid.UUID,
        limit: int | None = None,
    ) -> list[dict]:
        """
        Get message history for a session.

        Args:
            session_id: Session UUID
            limit: Optional limit on messages (most recent)

        Returns:
            List of messages [{role, content}]
        """
        query = (
            select(Message)
            .where(Message.session_id == session_id)
            .order_by(Message.created_at.desc())
        )

        if limit:
            query = query.limit(limit)

        result = await self.db.execute(query)
        messages = list(reversed(result.scalars().all()))  # Reverse to chronological

        return [{"role": m.role, "content": m.content} for m in messages]

    async def list_sessions(
        self,
        page: int = 1,
        per_page: int = 20,
        tier: str | None = None,
    ) -> tuple[list[SessionSummary], int]:
        """
        List sessions with pagination.

        Args:
            page: Page number (1-indexed)
            per_page: Items per page
            tier: Optional filter by tier

        Returns:
            Tuple of (sessions, total_count)
        """
        query = select(Session)
        if tier:
            query = query.where(Session.tier == tier)
        query = query.order_by(Session.updated_at.desc())

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar_one()

        # Get page
        query = query.offset((page - 1) * per_page).limit(per_page)
        result = await self.db.execute(query)
        sessions = result.scalars().all()

        summaries = [
            SessionSummary(
                id=s.id,
                title=s.title,
                mode=s.mode,
                tier=s.tier,
                message_count=s.message_count,
                created_at=s.created_at,
                updated_at=s.updated_at,
            )
            for s in sessions
        ]

        return summaries, total

    async def update_title(self, session_id: uuid.UUID, title: str) -> None:
        """Update session title."""
        result = await self.db.execute(
            select(Session).where(Session.id == session_id)
        )
        session = result.scalars().first()
        if session:
            session.title = title[:255]
            await self.db.flush()

    async def update_tier(self, session_id: uuid.UUID, tier: str) -> None:
        """Update session tier (hot/warm/cold)."""
        result = await self.db.execute(
            select(Session).where(Session.id == session_id)
        )
        session = result.scalars().first()
        if session:
            session.tier = tier
            await self.db.flush()
            logger.debug("session.tier_updated", session_id=str(session_id), tier=tier)
