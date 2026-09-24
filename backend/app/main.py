"""
EscalasPT — FastAPI application factory.
"""

from __future__ import annotations

import asyncio
import hmac
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, HTTPException, Response, status
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.config import get_settings
from app.rate_limit import limiter
from app.dependencies import close_redis
from app.exceptions import register_exception_handlers
from app.middleware import RLSMiddleware, SecurityHeadersMiddleware
from app.routers import admin, auth, integracao, notifications, realtime, reports, shifts, shift_types, stations, swaps, users, websocket
from app.utils.logging import get_logger, setup_logging

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup/shutdown lifecycle."""
    setup_logging()
    logger = get_logger(__name__)
    logger.info("Starting %s (env=%s)", settings.APP_NAME, settings.APP_ENV)

    # Start background cleanup task for expired tokens/sessions. Not on
    # serverless: an instance there is frozen between requests, so an hourly
    # loop would run whenever it happened to be thawed, or never. Vercel Cron
    # calls /api/internal/cleanup instead.
    cleanup_task = None
    if not settings.SERVERLESS:
        cleanup_task = asyncio.create_task(_cleanup_expired_tokens_loop())

    yield

    if cleanup_task is not None:
        cleanup_task.cancel()
        try:
            await cleanup_task
        except asyncio.CancelledError:
            pass
    await close_redis()
    logger.info("Shutting down %s", settings.APP_NAME)


async def cleanup_expired_tokens() -> tuple[int, int]:
    """Remove expired refresh tokens and stale sessions. Returns the counts."""
    from datetime import datetime, timedelta, timezone
    from sqlalchemy import delete
    from app.database import async_session_factory
    from app.models.user import ActiveSession, RefreshToken

    async with async_session_factory() as db:
        now = datetime.now(timezone.utc)
        # Delete expired refresh tokens
        result = await db.execute(
            delete(RefreshToken).where(RefreshToken.expires_at < now)
        )
        expired_tokens = result.rowcount
        # Delete revoked sessions older than 7 days
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
        get_logger(__name__).info(
            "Cleanup: removed %d expired tokens, %d stale sessions",
            expired_tokens, stale_sessions,
        )
    return expired_tokens, stale_sessions


async def _cleanup_expired_tokens_loop():
    """Periodically remove expired refresh tokens and stale sessions."""
    logger = get_logger(__name__)
    INTERVAL = 3600  # every hour

    while True:
        try:
            await asyncio.sleep(INTERVAL)
            await cleanup_expired_tokens()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Token cleanup task error")


async def _check_database() -> bool:
    """One trivial round trip — enough to prove the pool can still reach Postgres."""
    from sqlalchemy import text
    from app.database import async_session_factory

    try:
        async with async_session_factory() as db:
            await db.execute(text("SELECT 1"))
        return True
    except Exception:
        get_logger(__name__).warning("Health check: database unreachable", exc_info=True)
        return False


async def _check_redis() -> bool:
    """Redis holds the rate-limit counters; without it the limits stop applying."""
    from app.dependencies import get_redis

    try:
        client = await get_redis()
        await client.ping()
        return True
    except Exception:
        get_logger(__name__).warning("Health check: redis unreachable", exc_info=True)
        return False


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
    # SlowAPIMiddleware is what applies default_limits. Without it, only the
    # endpoints carrying an explicit @limiter.limit decorator were ever
    # checked, and RATE_LIMIT_DEFAULT was decoration.
    application.state.limiter = limiter
    application.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    application.add_middleware(SlowAPIMiddleware)

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
    application.include_router(realtime.router, prefix="/api")
    application.include_router(integracao.router, prefix="/api")
    application.include_router(websocket.router)

    # ── Health Check ──────────────────────────────────────
    # Exempt from the default limit: this is what Docker polls, and a
    # throttled health check reads as a dead container.
    @application.get("/api/health", tags=["Health"])
    @limiter.exempt
    async def health_check(response: Response):
        """
        Reports on the dependencies the app cannot serve a request without.

        It used to answer "healthy" unconditionally, which meant the Docker
        health check passed with the database down — and nginx waits on
        exactly that condition before it starts, so a broken stack looked
        like a working one.
        """
        checks = {"database": await _check_database()}
        # memory:// keeps the rate-limit counters in-process: nothing to reach.
        if not settings.REDIS_URL.startswith("memory://"):
            checks["redis"] = await _check_redis()
        healthy = all(checks.values())
        if not healthy:
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {
            "status": "healthy" if healthy else "unhealthy",
            "service": settings.APP_NAME,
            "checks": {name: "up" if ok else "down" for name, ok in checks.items()},
        }

    # ── Scheduled cleanup (Vercel Cron) ───────────────────
    # Vercel calls this on the schedule in vercel.json, with CRON_SECRET as a
    # bearer token. Without a secret configured it does not exist at all, so
    # the self-hosted deployment, which runs the loop above, exposes nothing.
    @application.get("/api/internal/cleanup", include_in_schema=False)
    @limiter.exempt
    async def scheduled_cleanup(authorization: str | None = Header(None)):
        expected = f"Bearer {settings.CRON_SECRET}"
        if not settings.CRON_SECRET or not hmac.compare_digest(
            (authorization or "").encode(), expected.encode()
        ):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
        expired_tokens, stale_sessions = await cleanup_expired_tokens()
        return {"expired_tokens": expired_tokens, "stale_sessions": stale_sessions}

    return application


app = create_app()
