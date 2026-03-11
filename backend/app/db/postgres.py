from collections.abc import AsyncGenerator

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

logger = structlog.get_logger(__name__)


class Base(DeclarativeBase):
    pass


if settings.dev_mode:
    engine = create_async_engine(
        settings.sqlite_dsn,
        echo=settings.debug,
        connect_args={"check_same_thread": False},
    )
else:
    engine = create_async_engine(
        settings.postgres_dsn,
        echo=settings.debug,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
    )

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db() -> None:
    if settings.dev_mode:
        # Import models to register them with metadata, then create tables directly
        import app.db.models.document  # noqa: F401
        import app.db.models.session   # noqa: F401
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("sqlite.dev_db_created", path="./dev.db")
    else:
        logger.info("postgres.init", url=settings.postgres_dsn)
        async with engine.begin() as conn:
            await conn.run_sync(lambda _: None)
        logger.info("postgres.ready")


async def close_db() -> None:
    await engine.dispose()
    logger.info("postgres.closed")
