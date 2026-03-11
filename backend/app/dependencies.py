"""Shared FastAPI dependency providers."""
from collections.abc import AsyncGenerator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.postgres import get_session
from app.db.redis import get_redis
from app.db.qdrant import get_qdrant


async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Alias for get_session, used in FastAPI Depends."""
    async for session in get_session():
        yield session
