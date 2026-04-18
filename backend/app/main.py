"""
EscalasPT — FastAPI application factory.
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
from app.routers import admin, auth, notifications, reports, shifts, shift_types, stations, swaps, users, websocket
from app.utils.logging import get_logger, setup_logging

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup/shutdown lifecycle."""
    setup_logging()
    logger = get_logger(__name__)
    logger.info("Starting %s (env=%s)", settings.APP_NAME, settings.APP_ENV)

    # Start background cleanup task for expired tokens/sessions
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
    """Periodically remove expired refresh tokens and stale sessions."""
    from datetime import datetime, timezone
    from sqlalchemy import delete
    from app.database import async_session_factory
    from app.models.user import ActiveSession, RefreshToken

    logger = get_logger(__name__)
    INTERVAL = 3600  # every hour

    while True:
        try:
            await asyncio.sleep(INTERVAL)
            async with async_session_factory() as db:
                now = datetime.now(timezone.utc)
                # Delete expired refresh tokens
                result = await db.execute(
                    delete(RefreshToken).where(RefreshToken.expires_at < now)
                )
                expired_tokens = result.rowcount
                # Delete revoked sessions older than 7 days
                from datetime import timedelta
                cutoff = now - timedelta(days=7)
                result2 = await db.execute(
                    delete(ActiveSession).where(
                        ActiveSession.is_revoked == True,
                        ActiveSession.created_at < cutoff,
                    )
                )
                stale_sessions = result2.rowcount
                await db.commit()
                if expired_tokens or stale_sessions:
                    logger.info(
                        "Cleanup: removed %d expired tokens, %d stale sessions",
                        expired_tokens, stale_sessions,
                    )
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Token cleanup task error")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    application = FastAPI(
        title=settings.APP_NAME,
        description="EscalasPT — Plataforma de gestão de escalas",
        version="1.0.0",
        docs_url="/api/docs" if settings.APP_DEBUG else None,
        redoc_url="/api/redoc" if settings.APP_DEBUG else None,
        openapi_url="/api/openapi.json" if settings.APP_DEBUG else None,
        lifespan=lifespan,
    )

    # ── Rate Limiting ─────────────────────────────────────
    limiter = Limiter(
        key_func=get_remote_address,
        default_limits=[settings.RATE_LIMIT_DEFAULT],
        storage_uri=settings.REDIS_URL,
    )
    application.state.limiter = limiter
    application.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # ── CORS ──────────────────────────────────────────────
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Accept", "X-Requested-With"],
    )

    # ── Custom Middleware ─────────────────────────────────
    application.add_middleware(SecurityHeadersMiddleware)
    application.add_middleware(RLSMiddleware)

    # ── Exception Handlers ────────────────────────────────
    register_exception_handlers(application)

    # ── Routers ───────────────────────────────────────────
    application.include_router(auth.router, prefix="/api")
    application.include_router(admin.router, prefix="/api")
    application.include_router(users.router, prefix="/api")
    application.include_router(stations.router, prefix="/api")
    application.include_router(shifts.router, prefix="/api")
    application.include_router(shift_types.router, prefix="/api")
    application.include_router(notifications.router, prefix="/api")
    application.include_router(swaps.router, prefix="/api")
    application.include_router(reports.router, prefix="/api")
    application.include_router(websocket.router)

    # ── Health Check ──────────────────────────────────────
    @application.get("/api/health", tags=["Health"])
    async def health_check():
        return {
            "status": "healthy",
            "service": settings.APP_NAME,
        }

    return application


app = create_app()
