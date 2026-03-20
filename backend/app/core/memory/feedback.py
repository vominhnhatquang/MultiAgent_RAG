"""Feedback storage and statistics."""
import uuid

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.session import Feedback

logger = structlog.get_logger(__name__)


class FeedbackStore:
    """
    Store and query user feedback on messages.

    Feedback types:
        - thumbs_up: Positive rating
        - thumbs_down: Negative rating
        - comment: Optional text feedback
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def record(
        self,
        message_id: uuid.UUID,
        session_id: uuid.UUID,
        rating: str,
        comment: str | None = None,
    ) -> uuid.UUID:
        """
        Record feedback for a message.

        Args:
            message_id: Message UUID
            session_id: Session UUID
            rating: "thumbs_up" or "thumbs_down"
            comment: Optional feedback text

        Returns:
            Feedback record ID
        """
        feedback = Feedback(
            message_id=message_id,
            session_id=session_id,
            rating=rating,
            comment=comment,
        )
        self.db.add(feedback)
        await self.db.flush()

        logger.info(
            "feedback.recorded",
            message_id=str(message_id),
            rating=rating,
            has_comment=comment is not None,
        )
        return feedback.id

    async def get_stats(self) -> dict:
        """
        Get overall feedback statistics.

        Returns:
            Dict with upvotes, downvotes, total counts
        """
        result = await self.db.execute(
            select(
                func.count().filter(Feedback.rating == "thumbs_up").label("upvotes"),
                func.count().filter(Feedback.rating == "thumbs_down").label("downvotes"),
                func.count().label("total"),
            )
        )
        row = result.one()

        return {
            "upvotes": row.upvotes,
            "downvotes": row.downvotes,
            "total": row.total,
            "satisfaction_rate": round(row.upvotes / row.total, 2) if row.total > 0 else 0,
        }

    async def get_recent_negative(self, limit: int = 10) -> list[dict]:
        """
        Get recent negative feedback for review.

        Returns:
            List of feedback with associated message content
        """
        from app.db.models.session import Message

        result = await self.db.execute(
            select(Feedback, Message)
            .join(Message, Feedback.message_id == Message.id)
            .where(Feedback.rating == "thumbs_down")
            .order_by(Feedback.created_at.desc())
            .limit(limit)
        )
        rows = result.all()

        return [
            {
                "feedback_id": str(f.id),
                "message_id": str(f.message_id),
                "session_id": str(f.session_id),
                "comment": f.comment,
                "message_content": m.content[:500],  # Truncate long messages
                "created_at": f.created_at.isoformat(),
            }
            for f, m in rows
        ]
