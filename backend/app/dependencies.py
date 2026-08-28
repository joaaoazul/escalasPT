"""
FastAPI dependencies: DB session with RLS context, current user, RBAC, Redis.
"""

from __future__ import annotations

import uuid
from typing import AsyncGenerator, Callable

import jwt
import redis.asyncio as aioredis
from fastapi import Depends, Header, Request
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import async_session_factory
from app.exceptions import AuthenticationError, AuthorizationError
from app.models.user import ActiveSession, User, UserRole
from app.utils.logging import get_logger
from app.utils.security import decode_token

logger = get_logger(__name__)
settings = get_settings()

# ── Redis ─────────────────────────────────────────────────

_redis_pool: aioredis.Redis | None = None


async def get_redis() -> aioredis.Redis:
    """Shared Redis pool. Degrades gracefully when Redis is unreachable."""
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=3,
            retry_on_timeout=True,
        )
    try:
        await _redis_pool.ping()
    except Exception:
        logger.warning("Redis unreachable — rate limiting degraded")
    return _redis_pool


async def close_redis() -> None:
    global _redis_pool
    if _redis_pool is not None:
        await _redis_pool.close()
        _redis_pool = None


# ── Database Session ──────────────────────────────────────


async def get_db(request: Request) -> AsyncGenerator[AsyncSession, None]:
    """
    Yield a DB session with the RLS equipa context applied.

    Unlike escalasPT, an absent or malformed equipa_id sets the variable to the
    empty string AND the policies treat empty as "deny" (migration 001). There
    is no configuration in which a bad tenant hint means "see everything".
    """
    async with async_session_factory() as session:
        try:
            raw = getattr(request.state, "rls_equipa_id", None)
            value = ""
            if raw:
                try:
                    value = str(uuid.UUID(raw))
                except (ValueError, AttributeError):
                    logger.warning("Malformed equipa_id in token — RLS context left empty")
            # SET LOCAL takes no bind parameters in asyncpg; the strict UUID
            # parse above is what makes the interpolation safe.
            await session.execute(text(f"SET LOCAL app.current_equipa_id = '{value}'"))
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ── Authentication ────────────────────────────────────────


async def get_current_user(
    request: Request,
    authorization: str | None = Header(None, alias="Authorization"),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Validate the bearer token and the session behind it."""
    if not authorization or not authorization.startswith("Bearer "):
        raise AuthenticationError("Missing or invalid Authorization header")

    token = authorization.removeprefix("Bearer ").strip()

    try:
        payload = decode_token(token)
    except jwt.ExpiredSignatureError:
        raise AuthenticationError("Access token has expired")
    except jwt.InvalidTokenError:
        raise AuthenticationError("Invalid access token")

    if payload.get("type") != "access":
        raise AuthenticationError("Invalid token type")

    user_id = payload.get("sub")
    if not user_id:
        raise AuthenticationError("Invalid token payload")

    # Zero trust: the session embedded in the JWT must still be active.
    session_id = payload.get("sid")
    if not session_id:
        raise AuthenticationError("Invalid token — missing session")

    session_result = await db.execute(
        select(ActiveSession).where(
            ActiveSession.session_id == session_id,
            ActiveSession.is_revoked == False,  # noqa: E712
        )
    )
    if session_result.scalar_one_or_none() is None:
        raise AuthenticationError("Session has been revoked")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        raise AuthenticationError("User not found")
    if not user.is_active:
        raise AuthenticationError("User account is deactivated")

    request.state.user_id = str(user.id)
    request.state.equipa_id = str(user.equipa_id) if user.equipa_id else None

    return user


def require_role(*allowed_roles: UserRole) -> Callable:
    """RBAC dependency factory: Depends(require_role(UserRole.ADMIN))."""

    async def _check_role(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            names = ", ".join(r.value for r in allowed_roles)
            raise AuthorizationError(f"Requires one of: {names}")
        return current_user

    return _check_role


def get_client_ip(request: Request) -> str:
    """Client IP, respecting the X-Forwarded-For that nginx sets."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
