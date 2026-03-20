"""Unit tests for Cold Tier storage."""
import json
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.memory.memory_tiers import MemoryTierConfig, MemoryTiers


class TestColdTier:
    """Tests for cold tier (compressed disk) storage."""

    @pytest.fixture
    def memory_tiers(self, tmp_path: Path):
        """Create MemoryTiers with temp directory for cold storage."""
        # Patch COLD_STORAGE_DIR to use temp directory
        with patch("app.core.memory.memory_tiers.COLD_STORAGE_DIR", tmp_path):
            config = MemoryTierConfig(
                hot_ttl_minutes=30,
                warm_retention_days=7,
                cold_compression_level=3,
            )
            tiers = MemoryTiers(config)
            # Also patch the internal path method
            tiers._cold_path = lambda sid: tmp_path / f"{sid}.zst"
            yield tiers

    @pytest.fixture
    def sample_messages(self):
        """Sample messages for testing."""
        return [
            {"role": "user", "content": "Hello", "sources": None, "model_used": None},
            {"role": "assistant", "content": "Hi! How can I help?", "sources": None, "model_used": "gemma2:2b"},
            {"role": "user", "content": "What is the revenue?", "sources": None, "model_used": None},
            {"role": "assistant", "content": "Revenue is 100M", "sources": [{"doc": "report.pdf"}], "model_used": "gemma2:2b"},
        ]

    @pytest.mark.asyncio
    async def test_save_to_cold_creates_compressed_file(self, memory_tiers, sample_messages, tmp_path):
        """Test that save_to_cold creates a compressed file on disk."""
        session_id = uuid.uuid4()
        mock_db = AsyncMock()

        # Save to cold
        result = await memory_tiers.save_to_cold(session_id, sample_messages, mock_db)

        assert result is True

        # Check file exists
        cold_path = tmp_path / f"{session_id}.zst"
        assert cold_path.exists()

        # Check file is smaller than original JSON
        original_size = len(json.dumps(sample_messages).encode("utf-8"))
        compressed_size = cold_path.stat().st_size
        assert compressed_size < original_size

        # Verify database was updated
        mock_db.execute.assert_called_once()
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_from_cold_returns_messages(self, memory_tiers, sample_messages, tmp_path):
        """Test that get_from_cold reads and decompresses messages."""
        session_id = uuid.uuid4()
        mock_db = AsyncMock()

        # First save
        await memory_tiers.save_to_cold(session_id, sample_messages, mock_db)

        # Reset mock for get operation
        mock_db.reset_mock()
        mock_db.add = MagicMock()

        # Get from cold (without promotion for simpler test)
        result = await memory_tiers.get_from_cold(session_id, mock_db, promote=False)

        assert result is not None
        assert len(result) == len(sample_messages)
        assert result[0]["role"] == "user"
        assert result[0]["content"] == "Hello"
        assert result[3]["sources"] == [{"doc": "report.pdf"}]

    @pytest.mark.asyncio
    async def test_get_from_cold_returns_none_if_not_exists(self, memory_tiers, tmp_path):
        """Test that get_from_cold returns None for non-existent session."""
        session_id = uuid.uuid4()
        mock_db = AsyncMock()

        result = await memory_tiers.get_from_cold(session_id, mock_db)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_from_cold_with_promotion(self, memory_tiers, sample_messages, tmp_path):
        """Test that get_from_cold promotes to hot when promote=True."""
        session_id = uuid.uuid4()
        mock_db = AsyncMock()
        mock_db.add = MagicMock()

        # Mock Redis for hot tier
        mock_redis = AsyncMock()
        with patch("app.core.memory.memory_tiers.get_redis", return_value=mock_redis):
            # First save to cold
            await memory_tiers.save_to_cold(session_id, sample_messages, mock_db)
            mock_db.reset_mock()

            # Get with promotion
            result = await memory_tiers.get_from_cold(session_id, mock_db, promote=True)

            assert result is not None
            # Redis should be called for hot promotion
            mock_redis.setex.assert_called_once()

            # Cold file should be deleted
            cold_path = tmp_path / f"{session_id}.zst"
            assert not cold_path.exists()

    @pytest.mark.asyncio
    async def test_compression_ratio(self, memory_tiers, tmp_path):
        """Test that Zstd compression achieves good ratio."""
        session_id = uuid.uuid4()
        mock_db = AsyncMock()

        # Create repetitive content (compresses well)
        messages = [
            {"role": "user", "content": "What is the revenue?" * 100, "sources": None, "model_used": None},
            {"role": "assistant", "content": "The revenue is 100 million dollars." * 100, "sources": None, "model_used": "gemma2:2b"},
        ]

        await memory_tiers.save_to_cold(session_id, messages, mock_db)

        cold_path = tmp_path / f"{session_id}.zst"
        original_size = len(json.dumps(messages).encode("utf-8"))
        compressed_size = cold_path.stat().st_size

        # Expect at least 2x compression for repetitive content
        compression_ratio = original_size / compressed_size
        assert compression_ratio > 2.0

    @pytest.mark.asyncio
    async def test_get_cold_stats(self, memory_tiers, sample_messages, tmp_path):
        """Test get_cold_stats returns correct counts."""
        mock_db = AsyncMock()

        # Create 3 cold sessions
        for _ in range(3):
            session_id = uuid.uuid4()
            await memory_tiers.save_to_cold(session_id, sample_messages, mock_db)

        with patch("app.core.memory.memory_tiers.COLD_STORAGE_DIR", tmp_path):
            stats = await memory_tiers.get_cold_stats()

        assert stats["cold_sessions"] == 3
        assert stats["cold_size_bytes"] > 0

    @pytest.mark.asyncio
    async def test_unicode_content_preserved(self, memory_tiers, tmp_path):
        """Test that Vietnamese/Unicode content is preserved through compression."""
        session_id = uuid.uuid4()
        mock_db = AsyncMock()

        messages = [
            {"role": "user", "content": "Doanh thu quý 3 là bao nhiêu?", "sources": None, "model_used": None},
            {"role": "assistant", "content": "Doanh thu Q3 đạt 150 tỷ VND, tăng 15% so với cùng kỳ.", "sources": None, "model_used": "gemma2:2b"},
        ]

        await memory_tiers.save_to_cold(session_id, messages, mock_db)
        mock_db.reset_mock()

        result = await memory_tiers.get_from_cold(session_id, mock_db, promote=False)

        assert result[0]["content"] == "Doanh thu quý 3 là bao nhiêu?"
        assert "150 tỷ VND" in result[1]["content"]

    @pytest.mark.asyncio
    async def test_archive_warm_to_cold_with_mock(self, memory_tiers, tmp_path):
        """Test archive_warm_to_cold finds and archives old sessions."""
        from datetime import datetime, timedelta, timezone

        # Create mock session and messages
        mock_session = MagicMock()
        mock_session.id = uuid.uuid4()
        mock_session.tier = "warm"
        mock_session.updated_at = datetime.now(timezone.utc) - timedelta(days=10)

        mock_message = MagicMock()
        mock_message.role = "user"
        mock_message.content = "Test message"
        mock_message.sources = None
        mock_message.model_used = None
        mock_message.created_at = datetime.now(timezone.utc)

        mock_db = AsyncMock()

        # Mock the session query
        session_result = MagicMock()
        session_result.scalars.return_value.all.return_value = [mock_session]

        # Mock the message query
        msg_result = MagicMock()
        msg_result.scalars.return_value.all.return_value = [mock_message]

        mock_db.execute.side_effect = [session_result, msg_result, MagicMock(), MagicMock()]

        # Run archive
        archived = await memory_tiers.archive_warm_to_cold(mock_db, days_threshold=7)

        assert archived == 1

        # Verify cold file was created
        cold_path = tmp_path / f"{mock_session.id}.zst"
        assert cold_path.exists()
