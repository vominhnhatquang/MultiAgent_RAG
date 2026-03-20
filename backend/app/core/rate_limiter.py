"""Sliding window rate limiter using Redis."""
import time
from collections.abc import Callable

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.config import settings
from app.db.redis import get_redis

logger = structlog.get_logger(__name__)


class RateLimitExceeded(Exception):
    """Raised when rate limit is exceeded."""

    def __init__(self, limit: int, window: int, retry_after: int):
        self.limit = limit
        self.window = window
        self.retry_after = retry_after
        super().__init__(f"Rate limit exceeded: {limit} requests per {window}s")


def _get_endpoint_group(path: str) -> str:
    """Determine rate limit group based on request path."""
    if "/chat" in path:
        return "chat"
    if "/documents/upload" in path:
        return "upload"
    return "default"


def _get_limit_for_group(group: str) -> int:
    """Get rate limit for endpoint group."""
    limits = {
        "chat": settings.rate_limit_chat,       # 10/min
        "upload": settings.rate_limit_upload,   # 5/min
        "default": settings.rate_limit_default,  # 60/min
    }
    return limits.get(group, settings.rate_limit_default)


async def check_rate_limit(
    client_ip: str,
    endpoint_group: str,
    window_seconds: int = 60,
) -> tuple[int, int, int]:
    """
    Check and increment rate limit counter using Redis sliding window.

    Args:
        client_ip: Client IP address
        endpoint_group: Rate limit group (chat, upload, default)
        window_seconds: Time window in seconds

    Returns:
        Tuple of (current_count, limit, remaining)

    Raises:
        RateLimitExceeded: If rate limit is exceeded
    """
    limit = _get_limit_for_group(endpoint_group)
    key = f"ratelimit:{client_ip}:{endpoint_group}"

    try:
        redis = get_redis()

        # Use Redis pipeline for atomic operations
        pipe = redis.pipeline()
        pipe.incr(key)
        pipe.ttl(key)
        results = await pipe.execute()

        current_count = results[0]
        ttl = results[1]

        # Set expiry on first request in window
        if ttl == -1:  # Key exists but no TTL
            await redis.expire(key, window_seconds)
            ttl = window_seconds
        elif ttl == -2:  # Key doesn't exist (shouldn't happen after INCR)
            await redis.expire(key, window_seconds)
            ttl = window_seconds

        remaining = max(0, limit - current_count)

        if current_count > limit:
            retry_after = max(1, ttl if ttl > 0 else window_seconds)
            raise RateLimitExceeded(limit, window_seconds, retry_after)

        return current_count, limit, remaining

    except RateLimitExceeded:
        raise
    except Exception as e:
        # If Redis fails, allow the request (fail open)
        logger.warning("rate_limit.redis_error", error=str(e))
        return 0, limit, limit


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware for rate limiting.

    Applies sliding window rate limiting based on client IP and endpoint group.
    Returns 429 Too Many Requests when limit is exceeded.
    """

    # Paths to exclude from rate limiting
    EXCLUDED_PATHS = {"/health", "/docs", "/redoc", "/openapi.json", "/favicon.ico"}

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path

        # Skip rate limiting for excluded paths
        if path in self.EXCLUDED_PATHS or path.startswith("/docs"):
            return await call_next(request)

        # Get client IP (handle proxies)
        client_ip = request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
        if not client_ip:
            client_ip = request.client.host if request.client else "unknown"

        endpoint_group = _get_endpoint_group(path)

        try:
            current, limit, remaining = await check_rate_limit(client_ip, endpoint_group)

            # Process request
            response = await call_next(request)

            # Add rate limit headers to response
            response.headers["X-RateLimit-Limit"] = str(limit)
            response.headers["X-RateLimit-Remaining"] = str(remaining)
            response.headers["X-RateLimit-Reset"] = str(int(time.time()) + 60)

            return response

        except RateLimitExceeded as e:
            logger.warning(
                "rate_limit.exceeded",
                client_ip=client_ip,
                endpoint_group=endpoint_group,
                limit=e.limit,
            )
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Too many requests",
                    "code": "RATE_LIMIT_EXCEEDED",
                    "retry_after": e.retry_after,
                },
                headers={
                    "Retry-After": str(e.retry_after),
                    "X-RateLimit-Limit": str(e.limit),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int(time.time()) + e.retry_after),
                },
            )
