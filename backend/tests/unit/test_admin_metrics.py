"""Unit tests for admin Prometheus metrics and cgroup memory."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path


class TestCgroupMemory:
    """Tests for cgroup memory reading functions."""

    def test_get_cgroup_memory_v2(self, tmp_path: Path):
        """Test reading memory from cgroup v2."""
        from app.api.v1.admin import _get_cgroup_memory_bytes

        # Create mock cgroup v2 file
        with patch("app.api.v1.admin.Path") as mock_path:
            mock_v2 = MagicMock()
            mock_v2.exists.return_value = True
            mock_v2.read_text.return_value = "123456789\n"

            mock_v1 = MagicMock()
            mock_v1.exists.return_value = False

            def path_factory(p):
                if "memory.current" in str(p):
                    return mock_v2
                return mock_v1

            mock_path.side_effect = path_factory

            result = _get_cgroup_memory_bytes()
            assert result == 123456789

    def test_get_cgroup_memory_not_in_container(self):
        """Test returns None when not in container."""
        from app.api.v1.admin import _get_cgroup_memory_bytes

        with patch("app.api.v1.admin.Path") as mock_path:
            mock_file = MagicMock()
            mock_file.exists.return_value = False
            mock_path.return_value = mock_file

            result = _get_cgroup_memory_bytes()
            assert result is None

    def test_get_cgroup_limit_max(self):
        """Test reading 'max' limit (no limit set)."""
        from app.api.v1.admin import _get_cgroup_memory_limit_bytes

        with patch("app.api.v1.admin.Path") as mock_path:
            mock_v2 = MagicMock()
            mock_v2.exists.return_value = True
            mock_v2.read_text.return_value = "max\n"

            mock_path.return_value = mock_v2

            result = _get_cgroup_memory_limit_bytes()
            assert result is None


class TestPrometheusMetrics:
    """Tests for Prometheus metrics endpoint."""

    @pytest.mark.asyncio
    async def test_prometheus_metrics_returns_text(self):
        """Test metrics endpoint returns text/plain."""
        from app.api.v1.admin import prometheus_metrics

        with patch("app.api.v1.admin.get_redis") as mock_redis, \
             patch("app.api.v1.admin._check_postgres") as mock_pg, \
             patch("app.api.v1.admin._check_redis") as mock_rd, \
             patch("app.api.v1.admin._check_qdrant") as mock_qd, \
             patch("app.api.v1.admin._check_ollama") as mock_ol, \
             patch("app.api.v1.admin._get_cgroup_memory_bytes") as mock_cgroup:

            # Mock Redis
            mock_redis_client = AsyncMock()
            mock_redis_client.scan_iter = AsyncMock(return_value=iter([]))
            mock_redis.return_value = mock_redis_client

            # Mock health checks
            from app.api.v1.admin import ServiceStatus
            mock_pg.return_value = ServiceStatus(name="postgres", status="healthy", latency_ms=1.0)
            mock_rd.return_value = ServiceStatus(name="redis", status="healthy", latency_ms=0.5)
            mock_qd.return_value = ServiceStatus(name="qdrant", status="healthy", latency_ms=2.0)
            mock_ol.return_value = ServiceStatus(name="ollama", status="healthy", latency_ms=10.0)

            # Mock cgroup
            mock_cgroup.return_value = 100_000_000  # 100MB

            response = await prometheus_metrics()

            assert response.media_type == "text/plain; charset=utf-8"
            content = response.body.decode()

            # Check expected metrics are present
            assert "rate_limit_requests_total" in content
            assert "rate_limit_current" in content
            assert "service_health" in content
            assert "process_memory_bytes" in content

    @pytest.mark.asyncio
    async def test_prometheus_metrics_includes_rate_limit_groups(self):
        """Test all rate limit groups are reported."""
        from app.api.v1.admin import prometheus_metrics

        with patch("app.api.v1.admin.get_redis") as mock_redis, \
             patch("app.api.v1.admin._check_postgres") as mock_pg, \
             patch("app.api.v1.admin._check_redis") as mock_rd, \
             patch("app.api.v1.admin._check_qdrant") as mock_qd, \
             patch("app.api.v1.admin._check_ollama") as mock_ol, \
             patch("app.api.v1.admin._get_cgroup_memory_bytes") as mock_cgroup:

            # Mock Redis with rate limit keys
            mock_redis_client = AsyncMock()

            async def mock_scan_iter(match=None):
                if match == "ratelimit:*":
                    for key in ["ratelimit:1.2.3.4:chat", "ratelimit:1.2.3.4:upload"]:
                        yield key
                elif match == "ratelimit_exceeded:*":
                    return
                    yield  # Empty generator

            mock_redis_client.scan_iter = mock_scan_iter
            mock_redis_client.get = AsyncMock(return_value="5")
            mock_redis.return_value = mock_redis_client

            # Mock health checks
            from app.api.v1.admin import ServiceStatus
            mock_pg.return_value = ServiceStatus(name="postgres", status="healthy", latency_ms=1.0)
            mock_rd.return_value = ServiceStatus(name="redis", status="healthy", latency_ms=0.5)
            mock_qd.return_value = ServiceStatus(name="qdrant", status="healthy", latency_ms=2.0)
            mock_ol.return_value = ServiceStatus(name="ollama", status="healthy", latency_ms=10.0)

            mock_cgroup.return_value = None  # Not in container

            # Mock psutil for non-container case
            with patch("psutil.Process") as mock_process:
                mock_proc = MagicMock()
                mock_proc.memory_info.return_value.rss = 200_000_000
                mock_process.return_value = mock_proc

                response = await prometheus_metrics()
                content = response.body.decode()

                # Check groups are present
                assert 'group="chat"' in content
                assert 'group="upload"' in content
                assert 'group="default"' in content

    @pytest.mark.asyncio
    async def test_prometheus_metrics_handles_redis_failure(self):
        """Test metrics gracefully handle Redis failure."""
        from app.api.v1.admin import prometheus_metrics

        with patch("app.api.v1.admin.get_redis") as mock_redis, \
             patch("app.api.v1.admin._check_postgres") as mock_pg, \
             patch("app.api.v1.admin._check_redis") as mock_rd, \
             patch("app.api.v1.admin._check_qdrant") as mock_qd, \
             patch("app.api.v1.admin._check_ollama") as mock_ol, \
             patch("app.api.v1.admin._get_cgroup_memory_bytes") as mock_cgroup:

            # Redis throws error
            mock_redis.side_effect = Exception("Redis unavailable")

            # Mock health checks
            from app.api.v1.admin import ServiceStatus
            mock_pg.return_value = ServiceStatus(name="postgres", status="healthy", latency_ms=1.0)
            mock_rd.return_value = ServiceStatus(name="redis", status="unhealthy", latency_ms=0, error="Connection refused")
            mock_qd.return_value = ServiceStatus(name="qdrant", status="healthy", latency_ms=2.0)
            mock_ol.return_value = ServiceStatus(name="ollama", status="healthy", latency_ms=10.0)

            mock_cgroup.return_value = 100_000_000

            response = await prometheus_metrics()
            content = response.body.decode()

            # Should still return valid metrics with zeros
            assert 'rate_limit_requests_total{group="chat"} 0' in content


class TestAdminMemoryWithCgroup:
    """Tests for admin memory endpoint with cgroup support."""

    @pytest.mark.asyncio
    async def test_memory_uses_cgroup_when_available(self):
        """Test memory endpoint uses cgroup values in container."""
        from app.api.v1.admin import admin_memory

        with patch("app.api.v1.admin.get_redis") as mock_redis, \
             patch("app.api.v1.admin.get_qdrant") as mock_qdrant, \
             patch("app.api.v1.admin.AsyncSessionLocal") as mock_session, \
             patch("httpx.AsyncClient") as mock_httpx, \
             patch("app.api.v1.admin._get_cgroup_memory_bytes") as mock_cgroup, \
             patch("app.api.v1.admin._get_cgroup_memory_limit_bytes") as mock_limit:

            # Mock Redis
            mock_redis_client = AsyncMock()
            mock_redis_client.info = AsyncMock(return_value={"used_memory": 50_000_000})
            mock_redis.return_value = mock_redis_client

            # Mock Qdrant
            mock_qdrant_client = AsyncMock()
            mock_collection = MagicMock()
            mock_collection.vectors_count = 1000
            mock_qdrant_client.get_collection = AsyncMock(return_value=mock_collection)
            mock_qdrant.return_value = mock_qdrant_client

            # Mock PostgreSQL
            mock_db = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalar_one.return_value = 100  # 100MB
            mock_db.execute = AsyncMock(return_value=mock_result)
            mock_ctx = AsyncMock()
            mock_ctx.__aenter__.return_value = mock_db
            mock_ctx.__aexit__.return_value = None
            mock_session.return_value = mock_ctx

            # Mock Ollama
            mock_client = AsyncMock()
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {"models": []}
            mock_client.__aenter__.return_value.get = AsyncMock(return_value=mock_resp)
            mock_httpx.return_value = mock_client

            # Mock cgroup - 256MB used, 512MB limit
            mock_cgroup.return_value = 256 * 1024 * 1024
            mock_limit.return_value = 512 * 1024 * 1024

            response = await admin_memory()

            # Find backend service
            backend_svc = next((s for s in response.services if s.name == "backend"), None)
            assert backend_svc is not None
            assert backend_svc.memory_mb == 256.0
            assert backend_svc.limit_mb == 512.0
