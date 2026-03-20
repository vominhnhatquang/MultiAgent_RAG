"""Unit tests for Admin API endpoints."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestHealthDetailed:
    """Tests for /api/v1/health/detailed endpoint."""

    @pytest.mark.asyncio
    async def test_health_detailed_all_healthy(self):
        """Test health check returns healthy when all services up."""
        from app.api.v1.admin import ServiceStatus

        # Mock all service checks to return healthy
        with patch("app.api.v1.admin._check_postgres") as mock_pg, \
             patch("app.api.v1.admin._check_redis") as mock_redis, \
             patch("app.api.v1.admin._check_qdrant") as mock_qdrant, \
             patch("app.api.v1.admin._check_ollama") as mock_ollama:

            mock_pg.return_value = ServiceStatus(name="postgres", status="healthy", latency_ms=5.0)
            mock_redis.return_value = ServiceStatus(name="redis", status="healthy", latency_ms=2.0)
            mock_qdrant.return_value = ServiceStatus(name="qdrant", status="healthy", latency_ms=10.0)
            mock_ollama.return_value = ServiceStatus(name="ollama", status="healthy", latency_ms=50.0)

            from app.api.v1.admin import health_detailed
            result = await health_detailed()

            assert result.status == "healthy"
            assert len(result.services) == 4
            assert all(s.status == "healthy" for s in result.services)

    @pytest.mark.asyncio
    async def test_health_detailed_degraded(self):
        """Test health check returns degraded when some services down."""
        from app.api.v1.admin import ServiceStatus

        with patch("app.api.v1.admin._check_postgres") as mock_pg, \
             patch("app.api.v1.admin._check_redis") as mock_redis, \
             patch("app.api.v1.admin._check_qdrant") as mock_qdrant, \
             patch("app.api.v1.admin._check_ollama") as mock_ollama:

            mock_pg.return_value = ServiceStatus(name="postgres", status="healthy", latency_ms=5.0)
            mock_redis.return_value = ServiceStatus(name="redis", status="unhealthy", latency_ms=0, error="Connection refused")
            mock_qdrant.return_value = ServiceStatus(name="qdrant", status="healthy", latency_ms=10.0)
            mock_ollama.return_value = ServiceStatus(name="ollama", status="healthy", latency_ms=50.0)

            from app.api.v1.admin import health_detailed
            result = await health_detailed()

            assert result.status == "degraded"

    @pytest.mark.asyncio
    async def test_health_detailed_unhealthy(self):
        """Test health check returns unhealthy when all services down."""
        from app.api.v1.admin import ServiceStatus

        with patch("app.api.v1.admin._check_postgres") as mock_pg, \
             patch("app.api.v1.admin._check_redis") as mock_redis, \
             patch("app.api.v1.admin._check_qdrant") as mock_qdrant, \
             patch("app.api.v1.admin._check_ollama") as mock_ollama:

            mock_pg.return_value = ServiceStatus(name="postgres", status="unhealthy", latency_ms=0, error="Down")
            mock_redis.return_value = ServiceStatus(name="redis", status="unhealthy", latency_ms=0, error="Down")
            mock_qdrant.return_value = ServiceStatus(name="qdrant", status="unhealthy", latency_ms=0, error="Down")
            mock_ollama.return_value = ServiceStatus(name="ollama", status="unhealthy", latency_ms=0, error="Down")

            from app.api.v1.admin import health_detailed
            result = await health_detailed()

            assert result.status == "unhealthy"


class TestAdminStats:
    """Tests for /api/v1/admin/stats endpoint."""

    @pytest.mark.asyncio
    async def test_admin_stats_returns_counts(self):
        """Test admin stats returns document/session/feedback counts."""
        # Mock database session
        mock_session = AsyncMock()

        # Mock scalar results
        mock_result = MagicMock()
        mock_result.scalar_one.return_value = 10
        mock_session.execute.return_value = mock_result

        # Create async context manager
        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__.return_value = mock_session
        mock_session_ctx.__aexit__.return_value = None

        # Mock Qdrant
        mock_qdrant = AsyncMock()
        mock_collection_info = MagicMock()
        mock_collection_info.vectors_count = 1000
        mock_collection_info.points_count = 1000
        mock_collection_info.segments_count = 5
        mock_qdrant.get_collection.return_value = mock_collection_info

        with patch("app.api.v1.admin.AsyncSessionLocal", return_value=mock_session_ctx), \
             patch("app.api.v1.admin.get_qdrant", return_value=mock_qdrant), \
             patch("app.api.v1.admin.httpx.AsyncClient") as mock_client:

            # Mock Ollama HTTP responses
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"models": [{"name": "gemma2:2b"}]}

            mock_client_instance = AsyncMock()
            mock_client_instance.get.return_value = mock_response
            mock_client_instance.__aenter__.return_value = mock_client_instance
            mock_client_instance.__aexit__.return_value = None
            mock_client.return_value = mock_client_instance

            from app.api.v1.admin import admin_stats
            result = await admin_stats()

            assert "documents" in result.model_dump()
            assert "chunks" in result.model_dump()
            assert "sessions" in result.model_dump()
            assert "feedback" in result.model_dump()
            assert "models" in result.model_dump()
            assert "qdrant" in result.model_dump()


class TestAdminMemory:
    """Tests for /api/v1/admin/memory endpoint."""

    @pytest.mark.asyncio
    async def test_admin_memory_returns_services(self):
        """Test admin memory returns per-service breakdown."""
        # Mock Redis
        mock_redis = AsyncMock()
        mock_redis.info.return_value = {"used_memory": 50 * 1024 * 1024}  # 50MB

        # Mock Qdrant
        mock_qdrant = AsyncMock()
        mock_collection_info = MagicMock()
        mock_collection_info.vectors_count = 10000
        mock_qdrant.get_collection.return_value = mock_collection_info

        # Mock PostgreSQL session
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one.return_value = 100  # 100MB
        mock_session.execute.return_value = mock_result

        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__.return_value = mock_session
        mock_session_ctx.__aexit__.return_value = None

        with patch("app.api.v1.admin.get_redis", return_value=mock_redis), \
             patch("app.api.v1.admin.get_qdrant", return_value=mock_qdrant), \
             patch("app.api.v1.admin.AsyncSessionLocal", return_value=mock_session_ctx), \
             patch("app.api.v1.admin.httpx.AsyncClient") as mock_client:

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"models": [{"name": "gemma2:2b", "size": 2 * 1024 * 1024 * 1024}]}

            mock_client_instance = AsyncMock()
            mock_client_instance.get.return_value = mock_response
            mock_client_instance.__aenter__.return_value = mock_client_instance
            mock_client_instance.__aexit__.return_value = None
            mock_client.return_value = mock_client_instance

            from app.api.v1.admin import admin_memory
            result = await admin_memory()

            assert result.total_mb > 0
            assert len(result.services) > 0
            service_names = [s.name for s in result.services]
            assert "redis" in service_names

