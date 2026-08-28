"""
Caderno de Serviço — FastAPI application factory.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.config import get_settings
from app.dependencies import close_redis
from app.exceptions import register_exception_handlers
from app.middleware import RLSMiddleware, SecurityHeadersMiddleware
from app.routers import auth
from app.utils.logging import get_logger, setup_logging

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    logger = get_logger(__name__)
    logger.info("Starting %s (env=%s)", settings.APP_NAME, settings.APP_ENV)

    cleanup_task = asyncio.create_task(_cleanup_expired_tokens_loop())

    yield

    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass
    await close_redis()
    logger.info("Shutting down %s", settings.APP_NAME)


async def _cleanup_expired_tokens_loop():
    """Hourly sweep of expired refresh tokens and stale revoked sessions."""
    from datetime import datetime, timedelta, timezone

    from sqlalchemy import delete

    from app.database import async_session_factory
    from app.models.user import ActiveSession, RefreshToken

    logger = get_logger(__name__)
    INTERVAL = 3600

    while True:
        try:
            await asyncio.sleep(INTERVAL)
            async with async_session_factory() as db:
                now = datetime.now(timezone.utc)
                expired = await db.execute(
                    delete(RefreshToken).where(RefreshToken.expires_at < now)
                )
                stale = await db.execute(
                    delete(ActiveSession).where(
                        ActiveSession.is_revoked == True,  # noqa: E712
                        ActiveSession.created_at < now - timedelta(days=7),
                    )
                )
                await db.commit()
                if expired.rowcount or stale.rowcount:
                    logger.info(
                        "Cleanup: %d expired tokens, %d stale sessions",
                        expired.rowcount, stale.rowcount,
                    )
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Token cleanup task error")


def create_app() -> FastAPI:
    application = FastAPI(
        title=settings.APP_NAME,
        description="Caderno de Serviço — registo de actividade no terreno",
        version="0.1.0",
        docs_url="/api/docs" if settings.APP_DEBUG else None,
        redoc_url="/api/redoc" if settings.APP_DEBUG else None,
        openapi_url="/api/openapi.json" if settings.APP_DEBUG else None,
        lifespan=lifespan,
    )

    # ── Rate limiting ─────────────────────────────────────
    limiter = Limiter(
        key_func=get_remote_address,
        default_limits=[settings.RATE_LIMIT_DEFAULT],
        storage_uri=settings.REDIS_URL,
    )
    application.state.limiter = limiter
    application.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # ── CORS (only matters for `npm run dev`; production is same-origin) ──
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Accept", "X-Requested-With"],
    )

    application.add_middleware(SecurityHeadersMiddleware)
    application.add_middleware(RLSMiddleware)

    register_exception_handlers(application)

    application.include_router(auth.router, prefix="/api")

    @application.get("/api/health", tags=["Health"])
    async def health_check():
        return {"status": "healthy", "service": settings.APP_NAME}

    return application


app = create_app()
