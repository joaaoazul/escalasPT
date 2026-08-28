"""
Middleware: RLS equipa context + security headers.

The security headers differ from escalasPT on purpose — see docs/PLANO.md §1.3.
escalasPT sends `camera=(), geolocation=()`, which denies those APIs to its own
origin. This app is a camera-and-GPS app, so it grants them to `self` and to
nobody else.
"""

from __future__ import annotations

import jwt
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.utils.logging import get_logger
from app.utils.security import decode_token

logger = get_logger(__name__)


class RLSMiddleware(BaseHTTPMiddleware):
    """
    Pre-parse the JWT to extract equipa_id and stash it on request.state so
    get_db() can SET LOCAL the RLS variable. Full validation still happens in
    get_current_user — this is only the tenant hint.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        equipa_id = None
        auth_header = request.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header.removeprefix("Bearer ").strip()
            try:
                equipa_id = decode_token(token).get("equipa_id")
            except jwt.InvalidTokenError:
                pass  # auth fails later, in the dependency
            except Exception:
                logger.debug("Middleware JWT pre-parse failed", exc_info=True)

        request.state.rls_equipa_id = str(equipa_id) if equipa_id else None

        return await call_next(request)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Security headers for API responses (nginx sets its own for the SPA)."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "0"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        # camera/geolocation granted to this origin only — the whole point of the app.
        response.headers["Permissions-Policy"] = (
            "camera=(self), geolocation=(self), microphone=(), payment=(), interest-cohort=()"
        )
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; worker-src 'self' blob:; "
            "style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; "
            "font-src 'self'; connect-src 'self'; frame-ancestors 'none'; "
            "base-uri 'self'; form-action 'self'"
        )
        return response
