"""Unit tests for Rate Limiter middleware."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.rate_limiter import (
    RateLimitExceeded,
    RateLimitMiddleware,
    _get_endpoint_group,
    _get_limit_for_group,
    check_rate_limit,
)


class TestEndpointGroups:
    """Tests for endpoint group detection."""

    def test_chat_endpoint_group(self):
        """Test chat endpoints are grouped correctly."""
        assert _get_endpoint_group("/api/v1/chat") == "chat"
        assert _get_endpoint_group("/api/v1/chat/stream") == "chat"

    def test_upload_endpoint_group(self):
        """Test upload endpoints are grouped correctly."""
        assert _get_endpoint_group("/api/v1/documents/upload") == "upload"

    def test_default_endpoint_group(self):
        """Test other endpoints get default group."""
        assert _get_endpoint_group("/api/v1/documents") == "default"
        assert _get_endpoint_group("/api/v1/sessions") == "default"
        assert _get_endpoint_group("/health") == "default"


class TestRateLimits:
    """Tests for rate limit values."""

    def test_chat_limit(self):
        """Test chat rate limit is 10/min."""
        assert _get_limit_for_group("chat") == 10

    def test_upload_limit(self):
        """Test upload rate limit is 5/min."""
        assert _get_limit_for_group("upload") == 5

    def test_default_limit(self):
        """Test default rate limit is 60/min."""
        assert _get_limit_for_group("default") == 60


class TestCheckRateLimit:
    """Tests for check_rate_limit function."""

    @pytest.mark.asyncio
    async def test_first_request_allowed(self):
        """Test first request is allowed."""
        mock_redis = MagicMock()
        mock_pipe = MagicMock()
        mock_pipe.incr = MagicMock(return_value=mock_pipe)
        mock_pipe.ttl = MagicMock(return_value=mock_pipe)
        mock_pipe.execute = AsyncMock(return_value=[1, -1])  # First request, no TTL
        mock_redis.pipeline = MagicMock(return_value=mock_pipe)
        mock_redis.expire = AsyncMock()

        with patch("app.core.rate_limiter.get_redis", return_value=mock_redis):
            current, limit, remaining = await check_rate_limit("192.168.1.1", "chat")

            assert current == 1
            assert limit == 10
            assert remaining == 9

    @pytest.mark.asyncio
    async def test_request_within_limit_allowed(self):
        """Test request within limit is allowed."""
        mock_redis = MagicMock()
        mock_pipe = MagicMock()
        mock_pipe.incr = MagicMock(return_value=mock_pipe)
        mock_pipe.ttl = MagicMock(return_value=mock_pipe)
        mock_pipe.execute = AsyncMock(return_value=[5, 30])  # 5th request, 30s TTL
        mock_redis.pipeline = MagicMock(return_value=mock_pipe)

        with patch("app.core.rate_limiter.get_redis", return_value=mock_redis):
            current, limit, remaining = await check_rate_limit("192.168.1.1", "chat")

            assert current == 5
            assert limit == 10
            assert remaining == 5

    @pytest.mark.asyncio
    async def test_request_exceeding_limit_raises(self):
        """Test request exceeding limit raises RateLimitExceeded."""
        mock_redis = MagicMock()
        mock_pipe = MagicMock()
        mock_pipe.incr = MagicMock(return_value=mock_pipe)
        mock_pipe.ttl = MagicMock(return_value=mock_pipe)
        mock_pipe.execute = AsyncMock(return_value=[11, 45])  # 11th request (over limit), 45s TTL
        mock_redis.pipeline = MagicMock(return_value=mock_pipe)

        with patch("app.core.rate_limiter.get_redis", return_value=mock_redis):
            with pytest.raises(RateLimitExceeded) as exc_info:
                await check_rate_limit("192.168.1.1", "chat")

            assert exc_info.value.limit == 10
            assert exc_info.value.retry_after == 45

    @pytest.mark.asyncio
    async def test_redis_failure_allows_request(self):
        """Test Redis failure fails open (allows request)."""
        mock_redis = MagicMock()
        mock_redis.pipeline.side_effect = Exception("Redis connection failed")

        with patch("app.core.rate_limiter.get_redis", return_value=mock_redis):
            current, limit, remaining = await check_rate_limit("192.168.1.1", "chat")

            # Should fail open
            assert current == 0
            assert limit == 10
            assert remaining == 10


class TestRateLimitMiddleware:
    """Tests for RateLimitMiddleware."""

    @pytest.mark.asyncio
    async def test_excluded_paths_bypass_rate_limit(self):
        """Test health/docs endpoints are not rate limited."""
        middleware = RateLimitMiddleware(app=MagicMock())

        # Create mock request for /health
        mock_request = MagicMock()
        mock_request.url.path = "/health"

        mock_response = MagicMock()
        mock_call_next = AsyncMock(return_value=mock_response)

        with patch("app.core.rate_limiter.check_rate_limit") as mock_check:
            result = await middleware.dispatch(mock_request, mock_call_next)

            # Rate limit should not be called for excluded paths
            mock_check.assert_not_called()
            assert result == mock_response

    @pytest.mark.asyncio
    async def test_rate_limit_headers_added(self):
        """Test rate limit headers are added to response."""
        middleware = RateLimitMiddleware(app=MagicMock())

        mock_request = MagicMock()
        mock_request.url.path = "/api/v1/chat"
        mock_request.headers = {}
        mock_request.client.host = "192.168.1.1"

        mock_response = MagicMock()
        mock_response.headers = {}
        mock_call_next = AsyncMock(return_value=mock_response)

        with patch("app.core.rate_limiter.check_rate_limit", return_value=(1, 10, 9)):
            result = await middleware.dispatch(mock_request, mock_call_next)

            assert "X-RateLimit-Limit" in result.headers
            assert result.headers["X-RateLimit-Limit"] == "10"
            assert "X-RateLimit-Remaining" in result.headers
            assert result.headers["X-RateLimit-Remaining"] == "9"

    @pytest.mark.asyncio
    async def test_rate_limit_exceeded_returns_429(self):
        """Test 429 response when rate limit exceeded."""
        middleware = RateLimitMiddleware(app=MagicMock())

        mock_request = MagicMock()
        mock_request.url.path = "/api/v1/chat"
        mock_request.headers = {}
        mock_request.client.host = "192.168.1.1"

        mock_call_next = AsyncMock()

        with patch("app.core.rate_limiter.check_rate_limit", side_effect=RateLimitExceeded(10, 60, 30)):
            result = await middleware.dispatch(mock_request, mock_call_next)

            assert result.status_code == 429
            assert "Retry-After" in result.headers
            assert result.headers["Retry-After"] == "30"

    @pytest.mark.asyncio
    async def test_x_forwarded_for_header_used(self):
        """Test X-Forwarded-For header is used for client IP."""
        middleware = RateLimitMiddleware(app=MagicMock())

        mock_request = MagicMock()
        mock_request.url.path = "/api/v1/chat"
        mock_request.headers = {"X-Forwarded-For": "10.0.0.1, 192.168.1.1"}
        mock_request.client.host = "127.0.0.1"

        mock_response = MagicMock()
        mock_response.headers = {}
        mock_call_next = AsyncMock(return_value=mock_response)

        with patch("app.core.rate_limiter.check_rate_limit", return_value=(1, 10, 9)) as mock_check:
            await middleware.dispatch(mock_request, mock_call_next)

            # Should use first IP from X-Forwarded-For
            mock_check.assert_called_once()
            call_args = mock_check.call_args
            assert call_args[0][0] == "10.0.0.1"


class TestRateLimitExceededException:
    """Tests for RateLimitExceeded exception."""

    def test_exception_attributes(self):
        """Test exception has correct attributes."""
        exc = RateLimitExceeded(limit=10, window=60, retry_after=45)

        assert exc.limit == 10
        assert exc.window == 60
        assert exc.retry_after == 45
        assert "10 requests per 60s" in str(exc)
