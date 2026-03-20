"""Shared FastAPI dependency providers."""
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.postgres import get_session


async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Alias for get_session, used in FastAPI Depends."""
    async for session in get_session():
        yield session
