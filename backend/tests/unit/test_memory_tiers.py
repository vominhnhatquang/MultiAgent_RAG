"""Tests for memory tiers."""
import uuid

import pytest
from unittest.mock import AsyncMock, patch

from app.core.memory.memory_tiers import MemoryTiers, MemoryTierConfig


class TestMemoryTiers:
    """Unit tests for MemoryTiers."""

    @pytest.fixture
    def mock_redis(self):
        """Create mock Redis client."""
        redis = AsyncMock()
        redis.setex = AsyncMock()
        redis.get = AsyncMock()
        redis.expire = AsyncMock()
        redis.delete = AsyncMock()
        redis.scan = AsyncMock(return_value=(0, []))
        return redis

    @pytest.fixture
    def memory_tiers(self, mock_redis):
        """Create MemoryTiers with mock Redis."""
        with patch('app.core.memory.memory_tiers.get_redis', return_value=mock_redis):
            yield MemoryTiers(config=MemoryTierConfig(hot_ttl_minutes=30))

    @pytest.mark.asyncio
    async def test_save_to_hot(self, memory_tiers, mock_redis):
        """save_to_hot should save to Redis with TTL."""
        session_id = uuid.uuid4()
        messages = [{"role": "user", "content": "test"}]

        with patch('app.core.memory.memory_tiers.get_redis', return_value=mock_redis):
            await memory_tiers.save_to_hot(session_id, messages)

        mock_redis.setex.assert_called_once()
        call_args = mock_redis.setex.call_args
        assert str(session_id) in call_args[0][0]  # Key contains session_id
        assert call_args[0][1] == 30 * 60  # TTL in seconds

    @pytest.mark.asyncio
    async def test_get_from_hot_hit(self, memory_tiers, mock_redis):
        """get_from_hot should return messages on cache hit."""
        import json

        session_id = uuid.uuid4()
        messages = [{"role": "user", "content": "cached"}]
        mock_redis.get.return_value = json.dumps(messages)

        with patch('app.core.memory.memory_tiers.get_redis', return_value=mock_redis):
            result = await memory_tiers.get_from_hot(session_id)

        assert result == messages

    @pytest.mark.asyncio
    async def test_get_from_hot_miss(self, memory_tiers, mock_redis):
        """get_from_hot should return None on cache miss."""
        session_id = uuid.uuid4()
        mock_redis.get.return_value = None

        with patch('app.core.memory.memory_tiers.get_redis', return_value=mock_redis):
            result = await memory_tiers.get_from_hot(session_id)

        assert result is None

    @pytest.mark.asyncio
    async def test_promote_to_hot_limits_messages(self, memory_tiers, mock_redis):
        """promote_to_hot should only cache recent messages."""
        import json

        session_id = uuid.uuid4()
        messages = [{"role": "user", "content": f"msg{i}"} for i in range(20)]

        with patch('app.core.memory.memory_tiers.get_redis', return_value=mock_redis):
            await memory_tiers.promote_to_hot(session_id, messages, limit=6)

        # Check that only last 6 messages were saved
        call_args = mock_redis.setex.call_args
        saved_data = json.loads(call_args[0][2])
        assert len(saved_data) == 6
        assert saved_data[0]["content"] == "msg14"  # Should be last 6

    @pytest.mark.asyncio
    async def test_refresh_hot_ttl(self, memory_tiers, mock_redis):
        """refresh_hot_ttl should extend TTL."""
        session_id = uuid.uuid4()

        with patch('app.core.memory.memory_tiers.get_redis', return_value=mock_redis):
            await memory_tiers.refresh_hot_ttl(session_id)

        mock_redis.expire.assert_called_once()
        call_args = mock_redis.expire.call_args
        assert call_args[0][1] == 30 * 60  # TTL

    @pytest.mark.asyncio
    async def test_invalidate_hot(self, memory_tiers, mock_redis):
        """invalidate_hot should delete from Redis."""
        session_id = uuid.uuid4()

        with patch('app.core.memory.memory_tiers.get_redis', return_value=mock_redis):
            await memory_tiers.invalidate_hot(session_id)

        mock_redis.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_hot_stats(self, memory_tiers, mock_redis):
        """get_hot_stats should count hot sessions."""
        mock_redis.scan.return_value = (0, ["key1", "key2", "key3"])

        with patch('app.core.memory.memory_tiers.get_redis', return_value=mock_redis):
            stats = await memory_tiers.get_hot_stats()

        assert stats["hot_sessions"] == 3

    def test_config_defaults(self):
        """MemoryTierConfig should have sensible defaults."""
        config = MemoryTierConfig()

        assert config.hot_ttl_minutes == 30
        assert config.warm_retention_days == 7
        assert config.cold_compression_level == 3
