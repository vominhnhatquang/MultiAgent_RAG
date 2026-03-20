"""Admin API endpoints for dashboard and monitoring."""
import asyncio
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
import structlog
from fastapi import APIRouter
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import func, select, text

from app.config import settings
from app.db.models.document import Chunk, Document
from app.db.models.session import Feedback, Message, Session
from app.db.postgres import AsyncSessionLocal
from app.db.qdrant import get_qdrant
from app.db.redis import get_redis

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["admin"])


# ── Response Models ──────────────────────────────────────────────────────────


class ServiceStatus(BaseModel):
    name: str
    status: str  # "healthy" | "unhealthy" | "unknown"
    latency_ms: float
    error: str | None = None


class HealthDetailedResponse(BaseModel):
    status: str  # "healthy" | "degraded" | "unhealthy"
    timestamp: str
    services: list[ServiceStatus]


class StatsResponse(BaseModel):
    documents: dict
    chunks: dict
    sessions: dict
    feedback: dict
    models: dict
    qdrant: dict


class MemoryServiceInfo(BaseModel):
    used_mb: float
    limit_mb: float


class MemoryResponse(BaseModel):
    total_gb: float
    used_gb: float
    services: dict[str, MemoryServiceInfo]


# ── Helper Functions ─────────────────────────────────────────────────────────


def _get_cgroup_memory_bytes() -> int | None:
    """
    Read container memory usage from cgroup (works in Docker/K8s containers).

    Returns memory usage in bytes, or None if not in a container.
    """
    # cgroup v2 path (modern containers)
    cgroup_v2_path = Path("/sys/fs/cgroup/memory.current")
    # cgroup v1 path (older containers)
    cgroup_v1_path = Path("/sys/fs/cgroup/memory/memory.usage_in_bytes")

    try:
        if cgroup_v2_path.exists():
            return int(cgroup_v2_path.read_text().strip())
        elif cgroup_v1_path.exists():
            return int(cgroup_v1_path.read_text().strip())
    except (OSError, ValueError) as e:
        logger.debug("cgroup.read_failed", error=str(e))

    return None


def _get_cgroup_memory_limit_bytes() -> int | None:
    """
    Read container memory limit from cgroup.

    Returns memory limit in bytes, or None if unlimited/not in container.
    """
    # cgroup v2 path
    cgroup_v2_path = Path("/sys/fs/cgroup/memory.max")
    # cgroup v1 path
    cgroup_v1_path = Path("/sys/fs/cgroup/memory/memory.limit_in_bytes")

    try:
        if cgroup_v2_path.exists():
            content = cgroup_v2_path.read_text().strip()
            if content == "max":
                return None  # No limit set
            return int(content)
        elif cgroup_v1_path.exists():
            limit = int(cgroup_v1_path.read_text().strip())
            # Very large values indicate no limit
            if limit > 2**62:
                return None
            return limit
    except (OSError, ValueError) as e:
        logger.debug("cgroup.limit_read_failed", error=str(e))

    return None


async def _check_postgres() -> ServiceStatus:
    """Check PostgreSQL connectivity."""
    start = time.perf_counter()
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        latency = (time.perf_counter() - start) * 1000
        return ServiceStatus(name="postgres", status="healthy", latency_ms=round(latency, 2))
    except Exception as e:
        latency = (time.perf_counter() - start) * 1000
        return ServiceStatus(name="postgres", status="unhealthy", latency_ms=round(latency, 2), error=str(e)[:100])


async def _check_redis() -> ServiceStatus:
    """Check Redis connectivity."""
    start = time.perf_counter()
    try:
        redis = get_redis()
        await redis.ping()
        latency = (time.perf_counter() - start) * 1000
        return ServiceStatus(name="redis", status="healthy", latency_ms=round(latency, 2))
    except Exception as e:
        latency = (time.perf_counter() - start) * 1000
        return ServiceStatus(name="redis", status="unhealthy", latency_ms=round(latency, 2), error=str(e)[:100])


async def _check_qdrant() -> ServiceStatus:
    """Check Qdrant connectivity."""
    start = time.perf_counter()
    try:
        qdrant = get_qdrant()
        # Get collection info as health check
        await qdrant.get_collection(settings.qdrant_collection)
        latency = (time.perf_counter() - start) * 1000
        return ServiceStatus(name="qdrant", status="healthy", latency_ms=round(latency, 2))
    except Exception as e:
        latency = (time.perf_counter() - start) * 1000
        error_msg = str(e)[:100]
        # Collection not found is still "healthy" connection
        if "not found" in error_msg.lower():
            return ServiceStatus(name="qdrant", status="healthy", latency_ms=round(latency, 2))
        return ServiceStatus(name="qdrant", status="unhealthy", latency_ms=round(latency, 2), error=error_msg)


async def _check_ollama() -> ServiceStatus:
    """Check Ollama connectivity."""
    start = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{settings.ollama_base_url}/api/tags")
            resp.raise_for_status()
        latency = (time.perf_counter() - start) * 1000
        return ServiceStatus(name="ollama", status="healthy", latency_ms=round(latency, 2))
    except Exception as e:
        latency = (time.perf_counter() - start) * 1000
        return ServiceStatus(name="ollama", status="unhealthy", latency_ms=round(latency, 2), error=str(e)[:100])


# ── Endpoints ────────────────────────────────────────────────────────────────


@router.get("/api/v1/health/detailed", response_model=HealthDetailedResponse)
async def health_detailed() -> HealthDetailedResponse:
    """
    Detailed health check with per-service status and latency.

    Returns:
        Service status for PostgreSQL, Redis, Qdrant, and Ollama.
    """
    # Run all health checks in parallel
    results = await asyncio.gather(
        _check_postgres(),
        _check_redis(),
        _check_qdrant(),
        _check_ollama(),
        return_exceptions=True,
    )

    services = []
    for result in results:
        if isinstance(result, Exception):
            services.append(ServiceStatus(name="unknown", status="unhealthy", latency_ms=0, error=str(result)[:100]))
        else:
            services.append(result)

    # Determine overall status
    unhealthy_count = sum(1 for s in services if s.status == "unhealthy")
    if unhealthy_count == 0:
        overall_status = "healthy"
    elif unhealthy_count < len(services):
        overall_status = "degraded"
    else:
        overall_status = "unhealthy"

    return HealthDetailedResponse(
        status=overall_status,
        timestamp=datetime.now(timezone.utc).isoformat(),
        services=services,
    )


@router.get("/api/v1/admin/stats", response_model=StatsResponse)
async def admin_stats() -> StatsResponse:
    """
    Aggregate statistics for admin dashboard.

    Returns:
        Counts for documents, chunks, sessions, feedback, loaded models, and Qdrant info.
    """
    async with AsyncSessionLocal() as session:
        # Document stats
        doc_total = await session.execute(select(func.count()).select_from(Document))
        doc_indexed = await session.execute(
            select(func.count()).select_from(Document).where(Document.status == "indexed")
        )
        doc_error = await session.execute(
            select(func.count()).select_from(Document).where(Document.status == "error")
        )
        doc_processing = await session.execute(
            select(func.count()).select_from(Document).where(Document.status.in_(["queued", "processing"]))
        )

        # Chunk stats
        chunk_total = await session.execute(select(func.count()).select_from(Chunk))

        # Session stats — count by tier for frontend (hot/warm/cold)
        session_total = await session.execute(select(func.count()).select_from(Session))
        session_hot = await session.execute(
            select(func.count()).select_from(Session).where(Session.tier == "hot")
        )
        session_warm = await session.execute(
            select(func.count()).select_from(Session).where(Session.tier == "warm")
        )
        session_cold = await session.execute(
            select(func.count()).select_from(Session).where(Session.tier == "cold")
        )

        # Message stats
        message_total = await session.execute(select(func.count()).select_from(Message))

        # Feedback stats
        feedback_total = await session.execute(select(func.count()).select_from(Feedback))
        feedback_positive = await session.execute(
            select(func.count()).select_from(Feedback).where(Feedback.rating == "thumbs_up")
        )
        feedback_negative = await session.execute(
            select(func.count()).select_from(Feedback).where(Feedback.rating == "thumbs_down")
        )

        # Extract scalars inside session context
        feedback_positive_val = feedback_positive.scalar_one()
        feedback_negative_val = feedback_negative.scalar_one()

    # Qdrant stats
    qdrant_stats = {"vectors": 0, "points": 0, "segments": 0}
    try:
        qdrant = get_qdrant()
        collection_info = await qdrant.get_collection(settings.qdrant_collection)
        qdrant_stats = {
            "vectors": collection_info.vectors_count or 0,
            "points": collection_info.points_count or 0,
            "segments": collection_info.segments_count or 0,
        }
    except Exception as e:
        logger.warning("admin.qdrant_stats_failed", error=str(e))

    # Ollama loaded models
    models = {"loaded": [], "available": []}
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            # Get running models
            ps_resp = await client.get(f"{settings.ollama_base_url}/api/ps")
            if ps_resp.status_code == 200:
                ps_data = ps_resp.json()
                models["loaded"] = [m.get("name", "unknown") for m in ps_data.get("models", [])]

            # Get available models
            tags_resp = await client.get(f"{settings.ollama_base_url}/api/tags")
            if tags_resp.status_code == 200:
                tags_data = tags_resp.json()
                models["available"] = [m.get("name", "unknown") for m in tags_data.get("models", [])]
    except Exception as e:
        logger.warning("admin.ollama_stats_failed", error=str(e))

    # Compute satisfaction_rate
    total_fb = feedback_positive_val + feedback_negative_val
    satisfaction_rate = feedback_positive_val / total_fb if total_fb > 0 else 0.0

    return StatsResponse(
        documents={
            "total": doc_total.scalar_one(),
            "indexed": doc_indexed.scalar_one(),
            "error": doc_error.scalar_one(),
            "processing": doc_processing.scalar_one(),
        },
        chunks={
            "total": chunk_total.scalar_one(),
        },
        sessions={
            "total": session_total.scalar_one(),
            "hot": session_hot.scalar_one(),
            "warm": session_warm.scalar_one(),
            "cold": session_cold.scalar_one(),
        },
        feedback={
            "thumbs_up": feedback_positive_val,
            "thumbs_down": feedback_negative_val,
            "satisfaction_rate": round(satisfaction_rate, 2),
        },
        models=models,
        qdrant=qdrant_stats,
    )


@router.get("/api/v1/admin/memory", response_model=MemoryResponse)
async def admin_memory() -> MemoryResponse:
    """
    Memory usage breakdown per service.

    Returns:
        Memory usage in GB (total/used) and per-service breakdown in MB.
    """
    # Memory budgets from infra/monitoring/check_ram.py
    memory_budgets = {
        "postgres": 512,
        "redis": 256,
        "qdrant": 1024,
        "ollama": 6144,
        "backend": 512,
        "frontend": 150,
    }

    services: dict[str, MemoryServiceInfo] = {}
    total_used_mb = 0.0

    # Redis
    try:
        redis = get_redis()
        info = await redis.info("memory")
        redis_mb = info.get("used_memory", 0) / (1024 * 1024)
        services["redis"] = MemoryServiceInfo(used_mb=round(redis_mb, 2), limit_mb=memory_budgets["redis"])
        total_used_mb += redis_mb
    except Exception:
        services["redis"] = MemoryServiceInfo(used_mb=0, limit_mb=memory_budgets["redis"])

    # Qdrant
    try:
        qdrant = get_qdrant()
        collection_info = await qdrant.get_collection(settings.qdrant_collection)
        vectors = collection_info.vectors_count or 0
        qdrant_mb = (vectors * 768 * 4) / (1024 * 1024)
        services["qdrant"] = MemoryServiceInfo(used_mb=round(qdrant_mb, 2), limit_mb=memory_budgets["qdrant"])
        total_used_mb += qdrant_mb
    except Exception:
        services["qdrant"] = MemoryServiceInfo(used_mb=0, limit_mb=memory_budgets["qdrant"])

    # PostgreSQL
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(text("""
                SELECT pg_database_size(current_database()) / (1024 * 1024) as size_mb
            """))
            pg_mb = result.scalar_one() or 0
            services["postgres"] = MemoryServiceInfo(used_mb=round(float(pg_mb), 2), limit_mb=memory_budgets["postgres"])
            total_used_mb += float(pg_mb)
    except Exception:
        services["postgres"] = MemoryServiceInfo(used_mb=0, limit_mb=memory_budgets["postgres"])

    # Ollama
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            ps_resp = await client.get(f"{settings.ollama_base_url}/api/ps")
            if ps_resp.status_code == 200:
                ps_data = ps_resp.json()
                loaded_models = ps_data.get("models", [])
                ollama_mb = sum(m.get("size", 0) / (1024 * 1024) for m in loaded_models)
                services["ollama"] = MemoryServiceInfo(used_mb=round(ollama_mb, 2), limit_mb=memory_budgets["ollama"])
                total_used_mb += ollama_mb
            else:
                services["ollama"] = MemoryServiceInfo(used_mb=0, limit_mb=memory_budgets["ollama"])
    except Exception:
        services["ollama"] = MemoryServiceInfo(used_mb=0, limit_mb=memory_budgets["ollama"])

    # Backend process
    cgroup_mem = _get_cgroup_memory_bytes()
    cgroup_limit = _get_cgroup_memory_limit_bytes()
    if cgroup_mem is not None:
        backend_mb = cgroup_mem / (1024 * 1024)
        backend_limit = cgroup_limit / (1024 * 1024) if cgroup_limit else memory_budgets["backend"]
        services["backend"] = MemoryServiceInfo(used_mb=round(backend_mb, 2), limit_mb=round(backend_limit, 2))
        total_used_mb += backend_mb
    else:
        try:
            import psutil
            process = psutil.Process()
            backend_mb = process.memory_info().rss / (1024 * 1024)
            services["backend"] = MemoryServiceInfo(used_mb=round(backend_mb, 2), limit_mb=memory_budgets["backend"])
            total_used_mb += backend_mb
        except Exception:
            services["backend"] = MemoryServiceInfo(used_mb=0, limit_mb=memory_budgets["backend"])

    # Frontend — not accessible from backend, report budget only
    services["frontend"] = MemoryServiceInfo(used_mb=0, limit_mb=memory_budgets["frontend"])

    total_budget_mb = sum(memory_budgets.values())

    return MemoryResponse(
        total_gb=round(total_budget_mb / 1024, 2),
        used_gb=round(total_used_mb / 1024, 2),
        services=services,
    )


@router.get("/api/v1/metrics", response_class=Response)
async def prometheus_metrics() -> Response:
    """
    Prometheus-compatible metrics endpoint.

    Returns metrics in Prometheus text format for scraping.
    Includes rate limiter counters, request counts, and service health.
    """
    from fastapi.responses import Response

    metrics_lines = []

    # HELP and TYPE declarations
    metrics_lines.append("# HELP rate_limit_requests_total Total rate-limited requests by group and status")
    metrics_lines.append("# TYPE rate_limit_requests_total counter")
    metrics_lines.append("# HELP rate_limit_current Current request count in rate limit window by group")
    metrics_lines.append("# TYPE rate_limit_current gauge")
    metrics_lines.append("# HELP service_health Service health status (1=healthy, 0=unhealthy)")
    metrics_lines.append("# TYPE service_health gauge")

    # Get rate limiter counters from Redis
    try:
        redis = get_redis()

        # Scan for all rate limit keys
        rate_limit_keys = []
        async for key in redis.scan_iter(match="ratelimit:*"):
            rate_limit_keys.append(key)

        # Aggregate by group
        group_counts: dict[str, int] = {"chat": 0, "upload": 0, "default": 0}
        group_clients: dict[str, int] = {"chat": 0, "upload": 0, "default": 0}

        for key in rate_limit_keys:
            # key format: ratelimit:{ip}:{group}
            parts = key.split(":")
            if len(parts) >= 3:
                group = parts[2]
                if group in group_counts:
                    count = await redis.get(key)
                    if count:
                        group_counts[group] += int(count)
                        group_clients[group] += 1

        # Emit rate limit metrics
        for group, total_requests in group_counts.items():
            metrics_lines.append(f'rate_limit_requests_total{{group="{group}"}} {total_requests}')

        for group, client_count in group_clients.items():
            metrics_lines.append(f'rate_limit_current{{group="{group}"}} {client_count}')

        # Rate limit exceeded counter (stored separately if we track it)
        exceeded_keys = []
        async for key in redis.scan_iter(match="ratelimit_exceeded:*"):
            exceeded_keys.append(key)

        exceeded_counts: dict[str, int] = {"chat": 0, "upload": 0, "default": 0}
        for key in exceeded_keys:
            parts = key.split(":")
            if len(parts) >= 2:
                group = parts[1]
                if group in exceeded_counts:
                    count = await redis.get(key)
                    if count:
                        exceeded_counts[group] += int(count)

        metrics_lines.append("# HELP rate_limit_exceeded_total Total rate limit exceeded events by group")
        metrics_lines.append("# TYPE rate_limit_exceeded_total counter")
        for group, count in exceeded_counts.items():
            metrics_lines.append(f'rate_limit_exceeded_total{{group="{group}"}} {count}')

    except Exception as e:
        logger.warning("metrics.redis_error", error=str(e))
        # Emit zeros if Redis unavailable
        for group in ["chat", "upload", "default"]:
            metrics_lines.append(f'rate_limit_requests_total{{group="{group}"}} 0')
            metrics_lines.append(f'rate_limit_current{{group="{group}"}} 0')

    # Service health metrics
    try:
        health_checks = await asyncio.gather(
            _check_postgres(),
            _check_redis(),
            _check_qdrant(),
            _check_ollama(),
            return_exceptions=True,
        )

        for result in health_checks:
            if isinstance(result, ServiceStatus):
                health_value = 1 if result.status == "healthy" else 0
                metrics_lines.append(f'service_health{{service="{result.name}"}} {health_value}')
                metrics_lines.append(f'service_latency_ms{{service="{result.name}"}} {result.latency_ms}')
    except Exception as e:
        logger.warning("metrics.health_error", error=str(e))

    # Memory metrics
    cgroup_mem = _get_cgroup_memory_bytes()
    cgroup_limit = _get_cgroup_memory_limit_bytes()

    metrics_lines.append("# HELP process_memory_bytes Process memory usage in bytes")
    metrics_lines.append("# TYPE process_memory_bytes gauge")

    if cgroup_mem is not None:
        metrics_lines.append(f"process_memory_bytes {cgroup_mem}")
    else:
        import psutil
        process = psutil.Process()
        metrics_lines.append(f"process_memory_bytes {process.memory_info().rss}")

    if cgroup_limit is not None:
        metrics_lines.append("# HELP process_memory_limit_bytes Process memory limit in bytes")
        metrics_lines.append("# TYPE process_memory_limit_bytes gauge")
        metrics_lines.append(f"process_memory_limit_bytes {cgroup_limit}")

    # Join with newlines and return as text/plain
    metrics_output = "\n".join(metrics_lines) + "\n"

    return Response(content=metrics_output, media_type="text/plain; charset=utf-8")
