"""Three-tier memory: Hot (Redis) → Warm (PG) → Cold (Disk+Zstd)."""
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import structlog
import zstandard as zstd
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.session import Message, Session
from app.db.redis import get_redis

logger = structlog.get_logger(__name__)

# Cold storage directory
COLD_STORAGE_DIR = Path("data/cold_storage")


@dataclass
class MemoryTierConfig:
    """Configuration for memory tiers."""

    hot_ttl_minutes: int = 30  # Redis TTL
    warm_retention_days: int = 7  # Keep in PG before archiving to cold
    cold_compression_level: int = 3  # Zstd compression level (1-22)


class MemoryTiers:
    """
    Three-tier memory management.

    Tier Lifecycle:
        New message → save to Hot (Redis) + Warm (PG) simultaneously
        Hot has TTL (30 min by default)
        Warm keeps 7 days before archiving to Cold

    Read path:
        1. Check Hot (Redis) → hit → return immediately
        2. Miss → check Warm (PG) → promote last 3 turns to Hot → return
        3. Miss → check Cold (Disk) → decompress → promote to Warm + Hot → return
    """

    def __init__(self, config: MemoryTierConfig | None = None) -> None:
        self.config = config or MemoryTierConfig()
        self._hot_prefix = "session:hot:"
        self._compressor = zstd.ZstdCompressor(level=self.config.cold_compression_level)
        self._decompressor = zstd.ZstdDecompressor()

        # Ensure cold storage directory exists
        COLD_STORAGE_DIR.mkdir(parents=True, exist_ok=True)

    def _hot_key(self, session_id: uuid.UUID) -> str:
        """Redis key for session."""
        return f"{self._hot_prefix}{session_id}"

    def _cold_path(self, session_id: uuid.UUID) -> Path:
        """Disk path for cold storage."""
        return COLD_STORAGE_DIR / f"{session_id}.zst"

    async def save_to_hot(
        self,
        session_id: uuid.UUID,
        messages: list[dict],
    ) -> None:
        """
        Save messages to hot tier (Redis).

        Args:
            session_id: Session UUID
            messages: List of message dicts
        """
        redis = get_redis()
        key = self._hot_key(session_id)
        ttl = self.config.hot_ttl_minutes * 60  # Convert to seconds

        try:
            await redis.setex(key, ttl, json.dumps(messages))
            logger.debug("memory.hot_save", session_id=str(session_id), count=len(messages))
        except Exception as e:
            logger.warning("memory.hot_save_failed", error=str(e))

    async def get_from_hot(self, session_id: uuid.UUID) -> list[dict] | None:
        """
        Get messages from hot tier (Redis).

        Returns:
            Messages if found, None if miss
        """
        redis = get_redis()
        key = self._hot_key(session_id)

        try:
            data = await redis.get(key)
            if data:
                messages = json.loads(data)
                logger.debug("memory.hot_hit", session_id=str(session_id))
                return messages
        except Exception as e:
            logger.warning("memory.hot_get_failed", error=str(e))

        logger.debug("memory.hot_miss", session_id=str(session_id))
        return None

    async def promote_to_hot(
        self,
        session_id: uuid.UUID,
        messages: list[dict],
        limit: int = 6,
    ) -> None:
        """
        Promote messages from warm/cold to hot tier.

        Args:
            session_id: Session UUID
            messages: All messages from warm tier
            limit: Number of recent messages to cache (default: 3 turns = 6 messages)
        """
        recent = messages[-limit:] if len(messages) > limit else messages
        await self.save_to_hot(session_id, recent)
        logger.debug(
            "memory.promoted_to_hot",
            session_id=str(session_id),
            promoted=len(recent),
        )

    async def refresh_hot_ttl(self, session_id: uuid.UUID) -> None:
        """Refresh TTL for active session."""
        redis = get_redis()
        key = self._hot_key(session_id)
        ttl = self.config.hot_ttl_minutes * 60

        try:
            await redis.expire(key, ttl)
        except Exception as e:
            logger.warning("memory.refresh_ttl_failed", error=str(e))

    async def invalidate_hot(self, session_id: uuid.UUID) -> None:
        """Remove session from hot tier."""
        redis = get_redis()
        key = self._hot_key(session_id)

        try:
            await redis.delete(key)
            logger.debug("memory.hot_invalidated", session_id=str(session_id))
        except Exception as e:
            logger.warning("memory.hot_invalidate_failed", error=str(e))

    async def get_hot_stats(self) -> dict:
        """Get stats about hot tier usage."""
        redis = get_redis()

        try:
            # Count keys with our prefix
            cursor = 0
            count = 0
            while True:
                cursor, keys = await redis.scan(cursor, match=f"{self._hot_prefix}*", count=100)
                count += len(keys)
                if cursor == 0:
                    break

            return {"hot_sessions": count}
        except Exception as e:
            logger.warning("memory.stats_failed", error=str(e))
            return {"hot_sessions": 0, "error": str(e)}

    # ── Cold Tier Methods ────────────────────────────────────────────────────

    async def save_to_cold(
        self,
        session_id: uuid.UUID,
        messages: list[dict],
        db: AsyncSession,
    ) -> bool:
        """
        Save messages to cold tier (compressed disk).

        Args:
            session_id: Session UUID
            messages: List of message dicts to archive
            db: Database session

        Returns:
            True if successful, False otherwise
        """
        cold_path = self._cold_path(session_id)

        try:
            # Compress messages with Zstd
            data = json.dumps(messages, ensure_ascii=False).encode("utf-8")
            compressed = self._compressor.compress(data)

            # Write to disk
            cold_path.write_bytes(compressed)

            # Update session tier in database
            await db.execute(
                update(Session)
                .where(Session.id == session_id)
                .values(tier="cold", archived_at=datetime.now(timezone.utc))
            )
            await db.commit()

            compression_ratio = len(data) / len(compressed) if compressed else 0
            logger.info(
                "memory.cold_save",
                session_id=str(session_id),
                original_size=len(data),
                compressed_size=len(compressed),
                ratio=f"{compression_ratio:.1f}x",
            )
            return True

        except Exception as e:
            logger.error("memory.cold_save_failed", session_id=str(session_id), error=str(e))
            return False

    async def get_from_cold(
        self,
        session_id: uuid.UUID,
        db: AsyncSession,
        promote: bool = True,
    ) -> list[dict] | None:
        """
        Get messages from cold tier (compressed disk).

        Args:
            session_id: Session UUID
            db: Database session
            promote: If True, promote to Warm (PG) + Hot (Redis) on access

        Returns:
            Messages if found, None if not in cold storage
        """
        cold_path = self._cold_path(session_id)

        if not cold_path.exists():
            logger.debug("memory.cold_miss", session_id=str(session_id))
            return None

        try:
            # Read and decompress
            compressed = cold_path.read_bytes()
            data = self._decompressor.decompress(compressed)
            messages = json.loads(data.decode("utf-8"))

            logger.info(
                "memory.cold_hit",
                session_id=str(session_id),
                message_count=len(messages),
            )

            if promote:
                # Restore messages to Warm tier (PG)
                await self._restore_to_warm(session_id, messages, db)

                # Promote recent messages to Hot tier (Redis)
                await self.promote_to_hot(session_id, messages)

                # Remove cold storage file
                cold_path.unlink(missing_ok=True)

            return messages

        except Exception as e:
            logger.error("memory.cold_get_failed", session_id=str(session_id), error=str(e))
            return None

    async def _restore_to_warm(
        self,
        session_id: uuid.UUID,
        messages: list[dict],
        db: AsyncSession,
    ) -> None:
        """Restore messages from cold to warm tier (PG)."""
        try:
            # Recreate Message records in database
            for msg in messages:
                db_msg = Message(
                    session_id=session_id,
                    role=msg["role"],
                    content=msg["content"],
                    sources=msg.get("sources"),
                    model_used=msg.get("model_used"),
                )
                db.add(db_msg)

            # Update session tier
            await db.execute(
                update(Session)
                .where(Session.id == session_id)
                .values(tier="warm", archived_at=None)
            )
            await db.commit()

            logger.debug(
                "memory.restored_to_warm",
                session_id=str(session_id),
                message_count=len(messages),
            )
        except Exception as e:
            logger.error("memory.restore_to_warm_failed", session_id=str(session_id), error=str(e))
            await db.rollback()

    async def archive_warm_to_cold(
        self,
        db: AsyncSession,
        days_threshold: int | None = None,
    ) -> int:
        """
        Archive old warm sessions to cold storage.

        Args:
            db: Database session
            days_threshold: Override config retention days

        Returns:
            Number of sessions archived
        """
        threshold_days = days_threshold or self.config.warm_retention_days
        cutoff = datetime.now(timezone.utc) - timedelta(days=threshold_days)

        try:
            # Find warm sessions older than threshold
            result = await db.execute(
                select(Session)
                .where(Session.tier == "warm")
                .where(Session.updated_at < cutoff)
            )
            sessions = result.scalars().all()

            archived_count = 0
            for session in sessions:
                # Load messages
                msg_result = await db.execute(
                    select(Message)
                    .where(Message.session_id == session.id)
                    .order_by(Message.created_at)
                )
                messages = msg_result.scalars().all()

                if not messages:
                    continue

                # Convert to dicts
                msg_dicts = [
                    {
                        "role": m.role,
                        "content": m.content,
                        "sources": m.sources,
                        "model_used": m.model_used,
                        "created_at": m.created_at.isoformat() if m.created_at else None,
                    }
                    for m in messages
                ]

                # Save to cold storage
                if await self.save_to_cold(session.id, msg_dicts, db):
                    # Delete messages from PG (keep session row)
                    await db.execute(
                        delete(Message).where(Message.session_id == session.id)
                    )
                    await db.commit()
                    archived_count += 1

            logger.info(
                "memory.archive_complete",
                archived=archived_count,
                threshold_days=threshold_days,
            )
            return archived_count

        except Exception as e:
            logger.error("memory.archive_failed", error=str(e))
            await db.rollback()
            return 0

    async def get_cold_stats(self) -> dict:
        """Get stats about cold tier usage."""
        try:
            cold_files = list(COLD_STORAGE_DIR.glob("*.zst"))
            total_size = sum(f.stat().st_size for f in cold_files)

            return {
                "cold_sessions": len(cold_files),
                "cold_size_bytes": total_size,
                "cold_size_mb": round(total_size / (1024 * 1024), 2),
            }
        except Exception as e:
            logger.warning("memory.cold_stats_failed", error=str(e))
            return {"cold_sessions": 0, "cold_size_bytes": 0, "error": str(e)}


# Global instance
_memory_tiers: MemoryTiers | None = None


def get_memory_tiers() -> MemoryTiers:
    """Get the global memory tiers instance."""
    global _memory_tiers
    if _memory_tiers is None:
        _memory_tiers = MemoryTiers()
    return _memory_tiers
