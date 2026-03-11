import redis.asyncio as aioredis
import structlog

from app.config import settings

logger = structlog.get_logger(__name__)

_redis_client: aioredis.Redis | None = None


async def init_redis() -> None:
    global _redis_client
    if settings.dev_mode:
        import fakeredis
        _redis_client = fakeredis.FakeAsyncRedis(decode_responses=True)
        logger.info("redis.dev_fakeredis")
    else:
        _redis_client = aioredis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
            max_connections=20,
        )
        await _redis_client.ping()
        logger.info("redis.ready", url=settings.redis_url)


async def close_redis() -> None:
    global _redis_client
    if _redis_client:
        await _redis_client.aclose()
        _redis_client = None
    logger.info("redis.closed")


def get_redis() -> aioredis.Redis:
    if _redis_client is None:
        raise RuntimeError("Redis client not initialized")
    return _redis_client
