"""FastAPI application factory with lifespan events."""
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.core.rate_limiter import RateLimitMiddleware
from app.db.postgres import close_db, init_db
from app.db.qdrant import close_qdrant, init_qdrant
from app.db.redis import close_redis, init_redis
from app.exceptions import AppError

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("app.startup", version=settings.app_version)
    await init_db()
    try:
        await init_redis()
    except Exception as exc:
        logger.warning("redis.init_failed", error=str(exc))
    try:
        await init_qdrant()
    except Exception as exc:
        logger.warning("qdrant.init_failed", error=str(exc))
    yield
    logger.info("app.shutdown")
    await close_db()
    await close_redis()
    await close_qdrant()


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type"],
    )

    # Rate limiting middleware (after CORS so preflight requests work)
    app.add_middleware(RateLimitMiddleware)

    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.http_status,
            content={"error": exc.message, "code": exc.code},
        )

    from app.api.v1.admin import router as admin_router
    from app.api.v1.chat import router as chat_router
    from app.api.v1.documents import router as documents_router
    from app.api.v1.health import router as health_router

    prefix = "/api/v1"
    app.include_router(health_router)
    app.include_router(admin_router)  # Admin routes (no prefix, full path in router)
    app.include_router(documents_router, prefix=prefix)
    app.include_router(chat_router, prefix=prefix)

    return app


app = create_app()
