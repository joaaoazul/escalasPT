"""
Middleware: RLS station isolation + request logging.
"""

from __future__ import annotations

import jwt
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from sqlalchemy import text

from app.config import get_settings
from app.utils.logging import get_logger
from app.utils.security import decode_token

logger = get_logger(__name__)
settings = get_settings()


class RLSMiddleware(BaseHTTPMiddleware):
    """
    Extracts station_id from the JWT (if present) and stores it on
    request.state so that get_db() can SET LOCAL the RLS variable.
    This runs before route handlers, so the DB dependency picks it up.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # Pre-parse JWT to extract station_id for RLS context.
        # Full auth validation still happens in get_current_user.
        station_id = None
        auth_header = request.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header.removeprefix("Bearer ").strip()
            try:
                payload = decode_token(token)
                station_id = payload.get("station_id")
            except jwt.InvalidTokenError:
                pass  # Auth will fail later in the dependency
            except Exception:
                logger.debug("Middleware JWT pre-parse failed", exc_info=True)

        request.state.rls_station_id = str(station_id) if station_id else None

        response = await call_next(request)
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security-related HTTP headers to every response."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "0"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), payment=()"
        )
        response.headers["Strict-Transport-Security"] = (
            "max-age=63072000; includeSubDomains; preload"
        )
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; font-src 'self'; connect-src 'self' wss:; "
            "frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        )
        return response


async def set_rls_context(db_session, station_id: str | None) -> None:
    """
    Set the RLS context variable for the current DB session.
    Called from get_db() after station_id is resolved.
    """
    import re
    if station_id and re.match(r'^[0-9a-f\-]{36}$', station_id):
        await db_session.execute(
            text(f"SET LOCAL app.current_station_id = '{station_id}'"),
        )
    else:
        await db_session.execute(
            text("SET LOCAL app.current_station_id = ''")
        )
