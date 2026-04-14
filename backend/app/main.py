"""
Shifting — FastAPI application factory.
"""

from __future__ import annotations

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
    yield
    await close_redis()
    logger.info("Shutting down %s", settings.APP_NAME)


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    application = FastAPI(
        title=settings.APP_NAME,
        description="Shifting — Shift scheduling and management platform",
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
