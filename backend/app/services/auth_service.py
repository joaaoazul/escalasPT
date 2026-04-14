"""
Auth service — login, refresh, logout, TOTP, session management.
Implements:
- Refresh token rotation with theft detection
- Account lockout after N failed attempts
- Active session tracking with concurrent session limits
- TOTP secret encryption at rest
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.exceptions import AuthenticationError, TOTPRequiredError
from app.models.user import ActiveSession, RefreshToken, User, UserRole
from app.services.audit_service import create_audit_log
from app.utils.logging import get_logger
from app.utils.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    decrypt_field,
    encrypt_field,
    generate_totp_secret,
    get_totp_uri,
    hash_password,
    hash_token,
    verify_password,
    verify_totp,
)

settings = get_settings()

logger = get_logger(__name__)


async def authenticate_user(
    db: AsyncSession,
    username: str,
    password: str,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> dict:
    """
    Authenticate user by username and password.
    Implements account lockout after N failed attempts.
    """
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()

    # Check lockout BEFORE password verification
    if user is not None and user.locked_until and user.locked_until > datetime.now(timezone.utc):
        remaining = (user.locked_until - datetime.now(timezone.utc)).seconds // 60
        raise AuthenticationError(
            f"Account is locked. Try again in {remaining + 1} minutes"
        )

    if user is None or not verify_password(password, user.password_hash):
        # Increment failed attempts if user exists
        if user is not None:
            user.failed_login_attempts += 1
            if user.failed_login_attempts >= settings.ACCOUNT_LOCKOUT_ATTEMPTS:
                user.locked_until = datetime.now(timezone.utc) + timedelta(
                    minutes=settings.ACCOUNT_LOCKOUT_MINUTES
                )
                logger.warning(
                    "Account locked: user=%s attempts=%d",
                    username, user.failed_login_attempts,
                )
            db.add(user)
            # Commit lockout state before raising — otherwise rollback undoes it
            await db.commit()
        raise AuthenticationError("Invalid username or password")

    if not user.is_active:
        raise AuthenticationError("Account is deactivated")

    # If TOTP is enabled, require 2FA
    if user.totp_enabled:
        await create_audit_log(
            db, user_id=user.id, action="login_totp_required",
            resource_type="user", resource_id=str(user.id),
            ip_address=ip_address,
        )
        return {
            "requires_totp": True,
            "user_id": str(user.id),
        }

    # Reset failed attempts on successful login
    user.failed_login_attempts = 0
    user.locked_until = None
    db.add(user)

    # Generate tokens with session
    tokens = await _generate_tokens(db, user, ip_address, user_agent)

    await create_audit_log(
        db, user_id=user.id, action="login_success",
        resource_type="user", resource_id=str(user.id),
        ip_address=ip_address,
    )

    return {
        "requires_totp": False,
        **tokens,
    }


async def authenticate_with_totp(
    db: AsyncSession,
    username: str,
    password: str,
    totp_code: str,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> dict:
    """Authenticate with username + password + TOTP code."""
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()

    # Check lockout BEFORE password verification (same as authenticate_user)
    if user is not None and user.locked_until and user.locked_until > datetime.now(timezone.utc):
        remaining = (user.locked_until - datetime.now(timezone.utc)).seconds // 60
        raise AuthenticationError(
            f"Account is locked. Try again in {remaining + 1} minutes"
        )

    if user is None or not verify_password(password, user.password_hash):
        if user is not None:
            user.failed_login_attempts += 1
            if user.failed_login_attempts >= settings.ACCOUNT_LOCKOUT_ATTEMPTS:
                user.locked_until = datetime.now(timezone.utc) + timedelta(
                    minutes=settings.ACCOUNT_LOCKOUT_MINUTES
                )
            db.add(user)
            await db.commit()
        raise AuthenticationError("Invalid username or password")

    if not user.is_active:
        raise AuthenticationError("Account is deactivated")

    if not user.totp_enabled or not user.totp_secret_encrypted:
        raise AuthenticationError("TOTP is not enabled for this account")

    secret = decrypt_field(user.totp_secret_encrypted)
    if not verify_totp(secret, totp_code):
        user.failed_login_attempts += 1
        if user.failed_login_attempts >= settings.ACCOUNT_LOCKOUT_ATTEMPTS:
            user.locked_until = datetime.now(timezone.utc) + timedelta(
                minutes=settings.ACCOUNT_LOCKOUT_MINUTES
            )
        db.add(user)
        await db.commit()
        raise AuthenticationError("Invalid TOTP code")

    # Reset failed attempts
    user.failed_login_attempts = 0
    user.locked_until = None
    db.add(user)

    tokens = await _generate_tokens(db, user, ip_address, user_agent)

    await create_audit_log(
        db, user_id=user.id, action="login_totp_success",
        resource_type="user", resource_id=str(user.id),
        ip_address=ip_address,
    )

    return tokens


async def refresh_access_token(
    db: AsyncSession,
    raw_refresh_token: str,
    ip_address: Optional[str] = None,
) -> dict:
    """
    Rotate the refresh token and issue a new access token.
    Implements theft detection: if a previously-used refresh token is reused,
    the entire token family is invalidated.
    """
    try:
        payload = decode_token(raw_refresh_token)
    except Exception:
        raise AuthenticationError("Invalid refresh token")

    if payload.get("type") != "refresh":
        raise AuthenticationError("Invalid token type")

    token_hash_value = hash_token(raw_refresh_token)
    family_id = payload.get("family")
    user_id = payload.get("sub")

    # Find the token in the DB
    result = await db.execute(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash_value)
    )
    stored_token = result.scalar_one_or_none()

    if stored_token is None:
        # Token not found — might be a reuse attack
        # Invalidate entire family as precaution
        if family_id:
            await _revoke_token_family(db, family_id)
            logger.warning(
                "Potential token theft detected: family=%s user=%s",
                family_id, user_id,
            )
            await create_audit_log(
                db, user_id=uuid.UUID(user_id) if user_id else None,
                action="token_theft_detected",
                resource_type="refresh_token",
                ip_address=ip_address,
            )
        raise AuthenticationError("Invalid refresh token — session invalidated for security")

    if stored_token.is_revoked:
        # Previously revoked token reused — theft indicator!
        await _revoke_token_family(db, str(stored_token.family_id))
        logger.warning(
            "Token reuse detected (theft): family=%s user=%s",
            stored_token.family_id, user_id,
        )
        await create_audit_log(
            db, user_id=stored_token.user_id,
            action="token_theft_reuse",
            resource_type="refresh_token",
            ip_address=ip_address,
        )
        raise AuthenticationError("Session compromised — all sessions invalidated")

    if stored_token.expires_at < datetime.now(timezone.utc):
        raise AuthenticationError("Refresh token has expired")

    # Mark current token as revoked (used)
    stored_token.is_revoked = True

    # Fetch user
    user_result = await db.execute(select(User).where(User.id == stored_token.user_id))
    user = user_result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise AuthenticationError("User not found or deactivated")

    # Issue new tokens in the same family
    # Find the user's active session for this token family
    session_result = await db.execute(
        select(ActiveSession)
        .where(ActiveSession.user_id == user.id, ActiveSession.is_revoked == False)  # noqa: E712
        .order_by(ActiveSession.created_at.desc())
        .limit(1)
    )
    active_session = session_result.scalar_one_or_none()
    sid = active_session.session_id if active_session else str(uuid.uuid4())

    access_token = create_access_token(
        user_id=str(user.id),
        role=user.role.value,
        station_id=str(user.station_id) if user.station_id else None,
        session_id=sid,
    )
    new_raw, new_hash, _, new_expires = create_refresh_token(
        user_id=str(user.id),
        family_id=str(stored_token.family_id),
    )

    new_refresh = RefreshToken(
        id=uuid.uuid4(),
        user_id=user.id,
        token_hash=new_hash,
        family_id=stored_token.family_id,
        expires_at=new_expires,
    )
    db.add(new_refresh)

    return {
        "access_token": access_token,
        "refresh_token": new_raw,
    }


async def logout_user(
    db: AsyncSession,
    raw_refresh_token: str,
    ip_address: Optional[str] = None,
) -> None:
    """Revoke the refresh token on logout."""
    token_hash_value = hash_token(raw_refresh_token)
    result = await db.execute(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash_value)
    )
    stored_token = result.scalar_one_or_none()

    if stored_token:
        # Revoke entire family on logout for security
        await _revoke_token_family(db, str(stored_token.family_id))
        await create_audit_log(
            db, user_id=stored_token.user_id, action="logout",
            resource_type="user", resource_id=str(stored_token.user_id),
            ip_address=ip_address,
        )


async def setup_totp(db: AsyncSession, user: User) -> dict:
    """Generate TOTP secret for a user (must be comandante)."""
    secret = generate_totp_secret()
    uri = get_totp_uri(secret, user.username)

    # Store encrypted secret; don't enable yet — user must verify first
    user.totp_secret_encrypted = encrypt_field(secret)
    db.add(user)

    return {"secret": secret, "uri": uri}


async def verify_and_enable_totp(
    db: AsyncSession,
    user: User,
    code: str,
) -> bool:
    """Verify TOTP code and enable 2FA if valid."""
    if not user.totp_secret_encrypted:
        raise AuthenticationError("TOTP not set up — call setup first")

    secret = decrypt_field(user.totp_secret_encrypted)
    if not verify_totp(secret, code):
        return False

    user.totp_enabled = True
    db.add(user)

    await create_audit_log(
        db, user_id=user.id, action="totp_enabled",
        resource_type="user", resource_id=str(user.id),
    )

    return True


# ── Private Helpers ───────────────────────────────────────


async def _generate_tokens(
    db: AsyncSession,
    user: User,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> dict:
    """Generate access + refresh tokens, create active session, enforce session limit."""
    session_id = uuid.uuid4()

    # Enforce max concurrent sessions — evict oldest
    count_result = await db.execute(
        select(func.count())
        .select_from(ActiveSession)
        .where(ActiveSession.user_id == user.id, ActiveSession.is_revoked == False)  # noqa: E712
    )
    active_count = count_result.scalar() or 0

    if active_count >= settings.MAX_CONCURRENT_SESSIONS:
        # Revoke oldest sessions to make room
        oldest = await db.execute(
            select(ActiveSession.id)
            .where(ActiveSession.user_id == user.id, ActiveSession.is_revoked == False)  # noqa: E712
            .order_by(ActiveSession.created_at.asc())
            .limit(active_count - settings.MAX_CONCURRENT_SESSIONS + 1)
        )
        oldest_ids = [row[0] for row in oldest.all()]
        if oldest_ids:
            await db.execute(
                update(ActiveSession)
                .where(ActiveSession.id.in_(oldest_ids))
                .values(is_revoked=True)
            )

    # Create new session
    session = ActiveSession(
        id=uuid.uuid4(),
        user_id=user.id,
        session_id=str(session_id),
        ip_address=ip_address,
        user_agent=user_agent[:500] if user_agent else None,
    )
    db.add(session)

    access_token = create_access_token(
        user_id=str(user.id),
        role=user.role.value,
        station_id=str(user.station_id) if user.station_id else None,
        session_id=str(session_id),
    )
    raw_refresh, token_hash_val, family_id, expires_at = create_refresh_token(
        user_id=str(user.id),
    )

    refresh_entry = RefreshToken(
        id=uuid.uuid4(),
        user_id=user.id,
        token_hash=token_hash_val,
        family_id=uuid.UUID(family_id),
        expires_at=expires_at,
    )
    db.add(refresh_entry)

    return {
        "access_token": access_token,
        "refresh_token": raw_refresh,
    }


async def _revoke_token_family(db: AsyncSession, family_id: str) -> None:
    """Revoke all tokens in a family (theft detection)."""
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.family_id == uuid.UUID(family_id))
        .values(is_revoked=True)
    )
    logger.info("Revoked all tokens in family=%s", family_id)
