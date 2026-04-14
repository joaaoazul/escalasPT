"""
FastAPI dependencies: DB session, current user, RBAC, Redis.
"""

from __future__ import annotations

from typing import AsyncGenerator, Callable, List

import jwt
import redis.asyncio as aioredis
from fastapi import Cookie, Depends, Header, Request
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
    """Return a shared Redis connection pool. NIS2 Art.29: fail gracefully if unavailable."""
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=3,
            retry_on_timeout=True,
        )
    # Verify reachability
    try:
        await _redis_pool.ping()
    except Exception:
        logger.warning("Redis unreachable — some features (rate limiting, WS) may be degraded")
    return _redis_pool


async def close_redis() -> None:
    """Close Redis pool on shutdown."""
    global _redis_pool
    if _redis_pool is not None:
        await _redis_pool.close()
        _redis_pool = None


# ── Database Session ──────────────────────────────────────


async def get_db(request: Request) -> AsyncGenerator[AsyncSession, None]:
    """Yield an async DB session with auto-commit/rollback and RLS context."""
    async with async_session_factory() as session:
        try:
            # Set RLS station context if resolved by middleware
            rls_station_id = getattr(request.state, "rls_station_id", None)
            if rls_station_id:
                # SET LOCAL doesn't support parameterized queries in asyncpg.
                # Strict UUID parse guarantees the value is safe for interpolation.
                import uuid as _uuid
                try:
                    validated_id = str(_uuid.UUID(rls_station_id))
                    await session.execute(
                        text(f"SET LOCAL app.current_station_id = '{validated_id}'")
                    )
                except (ValueError, AttributeError):
                    await session.execute(
                        text("SET LOCAL app.current_station_id = ''")
                    )
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
    """
    Extract and validate the current user from the Authorization header.
    Expects: Authorization: Bearer <access_token>
    """
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

    # Zero Trust: verify session_id from JWT is still active
    session_id = payload.get("sid")
    if not session_id:
        raise AuthenticationError("Invalid token — missing session")

    session_result = await db.execute(
        select(ActiveSession).where(
            ActiveSession.session_id == session_id,
            ActiveSession.is_revoked == False,  # noqa: E712
        )
    )
    active_session = session_result.scalar_one_or_none()
    if active_session is None:
        raise AuthenticationError("Session has been revoked")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        raise AuthenticationError("User not found")
    if not user.is_active:
        raise AuthenticationError("User account is deactivated")

    # Store station_id for RLS middleware
    request.state.station_id = str(user.station_id) if user.station_id else None
    request.state.user_id = str(user.id)

    return user


def require_role(*allowed_roles: UserRole) -> Callable:
    """
    Dependency factory for RBAC.
    Usage: Depends(require_role(UserRole.COMANDANTE, UserRole.ADMIN))
    """

    async def _check_role(
        current_user: User = Depends(get_current_user),
    ) -> User:
        if current_user.role not in allowed_roles:
            role_names = ", ".join(r.value for r in allowed_roles)
            raise AuthorizationError(
                f"This action requires one of the following roles: {role_names}"
            )
        return current_user

    return _check_role
