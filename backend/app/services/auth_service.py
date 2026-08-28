"""
Auth service — login, refresh, logout, TOTP, sessions.

Ported from escalasPT with the same guarantees:
  - refresh token rotation with reuse (theft) detection that revokes the family
  - account lockout after N failed attempts
  - active session registry with a concurrent session cap
  - TOTP secret encrypted at rest
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.exceptions import AuthenticationError
from app.models.user import ActiveSession, RefreshToken, User
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
    hash_token,
    verify_password,
    verify_totp,
)

settings = get_settings()
logger = get_logger(__name__)


async def _register_failed_attempt(db: AsyncSession, user: User) -> None:
    user.failed_login_attempts += 1
    if user.failed_login_attempts >= settings.ACCOUNT_LOCKOUT_ATTEMPTS:
        user.locked_until = datetime.now(timezone.utc) + timedelta(
            minutes=settings.ACCOUNT_LOCKOUT_MINUTES
        )
        logger.warning("Account locked: user_id=%s attempts=%d", user.id, user.failed_login_attempts)
    db.add(user)
    # Commit before raising — a rollback would undo the lockout.
    await db.commit()


async def authenticate_user(
    db: AsyncSession,
    username: str,
    password: str,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> dict:
    """Username + password. Returns requires_totp when 2FA is enabled."""
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()

    # Lockout is checked before the password so a locked account cannot be probed.
    if user is not None and user.locked_until and user.locked_until > datetime.now(timezone.utc):
        raise AuthenticationError("Credenciais inválidas")

    if user is None or not verify_password(password, user.password_hash):
        if user is not None:
            await _register_failed_attempt(db, user)
        raise AuthenticationError("Credenciais inválidas")

    if not user.is_active:
        raise AuthenticationError("Conta desactivada")

    if user.totp_enabled:
        await create_audit_log(
            db, user_id=user.id, action="login_totp_required",
            resource_type="user", resource_id=str(user.id), ip_address=ip_address,
        )
        return {"requires_totp": True, "user_id": str(user.id)}

    user.failed_login_attempts = 0
    user.locked_until = None
    db.add(user)

    tokens = await _generate_tokens(db, user, ip_address, user_agent)
    await create_audit_log(
        db, user_id=user.id, action="login_success",
        resource_type="user", resource_id=str(user.id), ip_address=ip_address,
    )
    return {"requires_totp": False, **tokens}


async def authenticate_with_totp(
    db: AsyncSession,
    username: str,
    password: str,
    totp_code: str,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> dict:
    """Username + password + TOTP code."""
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()

    if user is not None and user.locked_until and user.locked_until > datetime.now(timezone.utc):
        raise AuthenticationError("Credenciais inválidas")

    if user is None or not verify_password(password, user.password_hash):
        if user is not None:
            await _register_failed_attempt(db, user)
        raise AuthenticationError("Credenciais inválidas")

    if not user.is_active:
        raise AuthenticationError("Conta desactivada")

    if not user.totp_enabled or not user.totp_secret_encrypted:
        raise AuthenticationError("2FA não está activa nesta conta")

    if not verify_totp(decrypt_field(user.totp_secret_encrypted), totp_code):
        await create_audit_log(
            db, user_id=user.id, action="login_totp_failed",
            resource_type="user", resource_id=str(user.id), ip_address=ip_address,
        )
        await _register_failed_attempt(db, user)
        raise AuthenticationError("Código inválido")

    user.failed_login_attempts = 0
    user.locked_until = None
    db.add(user)

    tokens = await _generate_tokens(db, user, ip_address, user_agent)
    await create_audit_log(
        db, user_id=user.id, action="login_totp_success",
        resource_type="user", resource_id=str(user.id), ip_address=ip_address,
    )
    return tokens


async def refresh_access_token(
    db: AsyncSession, raw_refresh_token: str, ip_address: Optional[str] = None
) -> dict:
    """
    Rotate the refresh token. Reuse of a spent token means the token leaked:
    the whole family is revoked and the user has to log in again.
    """
    try:
        payload = decode_token(raw_refresh_token)
    except Exception:
        raise AuthenticationError("Refresh token inválido")

    if payload.get("type") != "refresh":
        raise AuthenticationError("Tipo de token inválido")

    token_hash_value = hash_token(raw_refresh_token)
    family_id = payload.get("family")
    user_id = payload.get("sub")

    result = await db.execute(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash_value)
    )
    stored_token = result.scalar_one_or_none()

    if stored_token is None:
        if family_id:
            await _revoke_token_family(db, family_id)
            logger.warning("Possible token theft: family=%s user=%s", family_id, user_id)
            await create_audit_log(
                db, user_id=uuid.UUID(user_id) if user_id else None,
                action="token_theft_detected", resource_type="refresh_token",
                ip_address=ip_address,
            )
            # Commit before raising. The request-scoped session rolls back on
            # exception, which would undo both the revocation and its audit
            # trail — the response would say "invalidated" while nothing was.
            await db.commit()
        raise AuthenticationError("Refresh token inválido — sessão invalidada")

    if stored_token.is_revoked:
        await _revoke_token_family(db, str(stored_token.family_id))
        await db.execute(
            update(ActiveSession)
            .where(ActiveSession.user_id == stored_token.user_id)
            .values(is_revoked=True)
        )
        logger.warning("Token reuse detected: family=%s", stored_token.family_id)
        await create_audit_log(
            db, user_id=stored_token.user_id, action="token_theft_reuse",
            resource_type="refresh_token", ip_address=ip_address,
        )
        # Same reason as above: commit the revocation before the exception
        # unwinds the session.
        await db.commit()
        raise AuthenticationError("Sessão comprometida — todas as sessões foram invalidadas")

    if stored_token.expires_at < datetime.now(timezone.utc):
        raise AuthenticationError("Refresh token expirado")

    stored_token.is_revoked = True

    user_result = await db.execute(select(User).where(User.id == stored_token.user_id))
    user = user_result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise AuthenticationError("Utilizador inexistente ou desactivado")

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
        role=user.role.value if hasattr(user.role, "value") else str(user.role),
        equipa_id=str(user.equipa_id) if user.equipa_id else None,
        session_id=sid,
    )
    new_raw, new_hash, _, new_expires = create_refresh_token(
        user_id=str(user.id), family_id=str(stored_token.family_id)
    )
    db.add(
        RefreshToken(
            id=uuid.uuid4(),
            user_id=user.id,
            token_hash=new_hash,
            family_id=stored_token.family_id,
            expires_at=new_expires,
        )
    )

    return {"access_token": access_token, "refresh_token": new_raw}


async def logout_user(
    db: AsyncSession, raw_refresh_token: str, ip_address: Optional[str] = None
) -> None:
    """Revoke the token family and the session behind it."""
    result = await db.execute(
        select(RefreshToken).where(RefreshToken.token_hash == hash_token(raw_refresh_token))
    )
    stored_token = result.scalar_one_or_none()
    if stored_token is None:
        return

    await _revoke_token_family(db, str(stored_token.family_id))
    await db.execute(
        update(ActiveSession)
        .where(ActiveSession.user_id == stored_token.user_id)
        .values(is_revoked=True)
    )
    await create_audit_log(
        db, user_id=stored_token.user_id, action="logout",
        resource_type="user", resource_id=str(stored_token.user_id), ip_address=ip_address,
    )


async def setup_totp(db: AsyncSession, user: User) -> dict:
    """Create a TOTP secret. Stored encrypted, not enabled until verified."""
    secret = generate_totp_secret()
    user.totp_secret_encrypted = encrypt_field(secret)
    db.add(user)
    return {"secret": secret, "uri": get_totp_uri(secret, user.username)}


async def verify_and_enable_totp(db: AsyncSession, user: User, code: str) -> bool:
    if not user.totp_secret_encrypted:
        raise AuthenticationError("2FA não foi iniciada")

    if not verify_totp(decrypt_field(user.totp_secret_encrypted), code):
        return False

    user.totp_enabled = True
    db.add(user)
    await create_audit_log(
        db, user_id=user.id, action="totp_enabled",
        resource_type="user", resource_id=str(user.id),
    )
    return True


# ── Private helpers ───────────────────────────────────────


async def _generate_tokens(
    db: AsyncSession,
    user: User,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> dict:
    """Issue an access/refresh pair, register the session, cap concurrency."""
    session_id = uuid.uuid4()

    count_result = await db.execute(
        select(func.count())
        .select_from(ActiveSession)
        .where(ActiveSession.user_id == user.id, ActiveSession.is_revoked == False)  # noqa: E712
    )
    active_count = count_result.scalar() or 0

    if active_count >= settings.MAX_CONCURRENT_SESSIONS:
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

    db.add(
        ActiveSession(
            id=uuid.uuid4(),
            user_id=user.id,
            session_id=str(session_id),
            ip_address=ip_address,
            user_agent=user_agent[:500] if user_agent else None,
        )
    )

    access_token = create_access_token(
        user_id=str(user.id),
        role=user.role.value if hasattr(user.role, "value") else str(user.role),
        equipa_id=str(user.equipa_id) if user.equipa_id else None,
        session_id=str(session_id),
    )
    raw_refresh, token_hash_val, family_id, expires_at = create_refresh_token(user_id=str(user.id))

    db.add(
        RefreshToken(
            id=uuid.uuid4(),
            user_id=user.id,
            token_hash=token_hash_val,
            family_id=uuid.UUID(family_id),
            expires_at=expires_at,
        )
    )

    return {"access_token": access_token, "refresh_token": raw_refresh}


async def _revoke_token_family(db: AsyncSession, family_id: str) -> None:
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.family_id == uuid.UUID(family_id))
        .values(is_revoked=True)
    )
    logger.info("Revoked refresh token family=%s", family_id)
