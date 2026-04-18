"""
User service — CRUD operations.
"""

from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions import ConflictError, NotFoundError
from app.models.user import User, UserRole
from app.schemas.user import UserCreate, UserUpdate
from app.services.audit_service import create_audit_log
from app.utils.logging import get_logger
from app.utils.security import (
    check_password_hibp,
    hash_password,
    validate_password_strength,
)

logger = get_logger(__name__)


async def create_user(
    db: AsyncSession,
    data: UserCreate,
    created_by: Optional[uuid.UUID] = None,
) -> User:
    """Create a new user."""
    # OWASP ASVS V2: validate password strength
    pw_issues = validate_password_strength(data.password)
    if pw_issues:
        from app.exceptions import ValidationError
        raise ValidationError("; ".join(pw_issues))

    # OWASP ASVS V2: check HaveIBeenPwned (non-blocking on failure)
    if await check_password_hibp(data.password):
        from app.exceptions import ValidationError
        raise ValidationError(
            "This password has been exposed in a data breach. "
            "Please choose a different password."
        )

    # Check uniqueness
    for field, value in [("username", data.username), ("email", data.email), ("nip", data.nip)]:
        existing = await db.execute(
            select(User).where(getattr(User, field) == value)
        )
        if existing.scalar_one_or_none():
            raise ConflictError(f"A user with this {field} already exists")

    user = User(
        id=uuid.uuid4(),
        username=data.username,
        email=data.email,
        password_hash=hash_password(data.password),
        full_name=data.full_name,
        nip=data.nip,
        numero_ordem=data.numero_ordem,
        role=data.role,
        station_id=data.station_id,
        phone=data.phone,
    )
    db.add(user)
    await db.flush()

    await create_audit_log(
        db,
        user_id=created_by,
        action="create",
        resource_type="user",
        resource_id=str(user.id),
        new_data={
            "role": user.role.value,
            "station_id": str(user.station_id) if user.station_id else None,
        },
    )

    logger.info("User created: username=%s role=%s", user.username, user.role.value)
    return user


async def get_user_by_id(db: AsyncSession, user_id: uuid.UUID) -> User:
    """Get a single user by ID."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise NotFoundError("User")
    return user


async def list_users(
    db: AsyncSession,
    station_id: Optional[uuid.UUID] = None,
    role: Optional[UserRole] = None,
    is_active: Optional[bool] = None,
    skip: int = 0,
    limit: int = 50,
) -> tuple[list[User], int]:
    """List users with optional filters."""
    query = select(User)
    count_query = select(func.count(User.id))

    if station_id:
        query = query.where(User.station_id == station_id)
        count_query = count_query.where(User.station_id == station_id)
    if role:
        query = query.where(User.role == role)
        count_query = count_query.where(User.role == role)
    if is_active is not None:
        query = query.where(User.is_active == is_active)
        count_query = count_query.where(User.is_active == is_active)

    query = query.order_by(User.full_name).offset(skip).limit(limit)

    result = await db.execute(query)
    users = list(result.scalars().all())

    count_result = await db.execute(count_query)
    total = count_result.scalar()

    return users, total


async def update_user(
    db: AsyncSession,
    user_id: uuid.UUID,
    data: UserUpdate,
    updated_by: Optional[uuid.UUID] = None,
) -> User:
    """Update a user's details."""
    user = await get_user_by_id(db, user_id)
    old_data = {
        "role": user.role.value,
        "station_id": str(user.station_id) if user.station_id else None,
        "is_active": user.is_active,
    }

    update_dict = data.model_dump(exclude_unset=True)
    for field, value in update_dict.items():
        setattr(user, field, value)

    db.add(user)
    await db.flush()

    await create_audit_log(
        db, user_id=updated_by, action="update",
        resource_type="user", resource_id=str(user.id),
        old_data=old_data,
        new_data=update_dict,
    )

    return user


async def anonymize_user(
    db: AsyncSession,
    user_id: uuid.UUID,
    anonymized_by: uuid.UUID,
) -> User:
    """
    RGPD Art. 17 — Right to erasure (anonymization).
    Replaces PII fields with anonymous values while preserving
    the historical shift records for operational auditing.
    The user account is deactivated and cannot be reactivated.
    """
    from app.exceptions import ValidationError

    user = await get_user_by_id(db, user_id)

    # Prevent anonymizing active accounts without explicit deactivation first
    if user.is_active:
        raise ValidationError(
            "User must be deactivated before anonymization. "
            "Set is_active=false first."
        )

    anon_suffix = str(user_id)[:8]
    user.full_name = f"[Anonimizado-{anon_suffix}]"
    user.email = f"anon-{anon_suffix}@removed.invalid"
    user.username = f"anon-{anon_suffix}"
    user.nip = f"ANON-{anon_suffix}"
    user.phone = None
    user.totp_secret_encrypted = None
    user.totp_enabled = False
    # Keep: id, role, station_id, shift history (via foreign keys), created/updated

    db.add(user)
    await db.flush()

    await create_audit_log(
        db, user_id=anonymized_by, action="anonymize",
        resource_type="user", resource_id=str(user.id),
        new_data={"reason": "RGPD Art.17 right to erasure"},
    )

    logger.info("User anonymized: id=%s by=%s", user_id, anonymized_by)
    return user
