"""
Admin router — system-wide administration endpoints.
Audit logs, system stats, password reset, session management.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, require_role
from app.models.audit_log import AuditLog
from app.models.shift import Shift
from app.models.station import Station
from app.models.user import ActiveSession, User, UserRole
from app.services.audit_service import create_audit_log
from app.utils.security import hash_password

router = APIRouter(prefix="/admin", tags=["Admin"])


# ── Schemas ───────────────────────────────────────────────

class AuditLogResponse(BaseModel):
    id: str
    user_id: str | None
    action: str
    resource_type: str
    resource_id: str | None
    old_data: dict | None
    new_data: dict | None
    ip_address: str | None
    user_agent: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class AuditLogListResponse(BaseModel):
    logs: list[AuditLogResponse]
    total: int


class SystemStatsResponse(BaseModel):
    total_users: int
    active_users: int
    inactive_users: int
    total_stations: int
    active_stations: int
    total_shifts: int
    published_shifts: int
    draft_shifts: int
    active_sessions: int
    users_by_role: dict[str, int]
    shifts_last_30_days: int


class PasswordResetRequest(BaseModel):
    new_password: str


class SessionResponse(BaseModel):
    id: str
    user_id: str
    session_id: str
    ip_address: str | None
    user_agent: str | None
    is_revoked: bool
    last_seen_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class SessionListResponse(BaseModel):
    sessions: list[SessionResponse]
    total: int


# ── System Stats ──────────────────────────────────────────

@router.get("/stats", response_model=SystemStatsResponse)
async def get_system_stats(
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    """Get system-wide statistics. Admin only."""
    # Users
    total_users = (await db.execute(select(func.count(User.id)))).scalar() or 0
    active_users = (await db.execute(
        select(func.count(User.id)).where(User.is_active == True)
    )).scalar() or 0
    inactive_users = total_users - active_users

    # Stations
    total_stations = (await db.execute(select(func.count(Station.id)))).scalar() or 0
    active_stations = (await db.execute(
        select(func.count(Station.id)).where(Station.is_active == True)
    )).scalar() or 0

    # Shifts
    total_shifts = (await db.execute(select(func.count(Shift.id)))).scalar() or 0
    published_shifts = (await db.execute(
        select(func.count(Shift.id)).where(Shift.status == "published")
    )).scalar() or 0
    draft_shifts = (await db.execute(
        select(func.count(Shift.id)).where(Shift.status == "draft")
    )).scalar() or 0

    # Active sessions
    active_sessions = (await db.execute(
        select(func.count(ActiveSession.id)).where(ActiveSession.is_revoked == False)
    )).scalar() or 0

    # Users by role
    role_query = await db.execute(
        select(User.role, func.count(User.id)).group_by(User.role)
    )
    users_by_role = {str(row[0].value) if hasattr(row[0], 'value') else str(row[0]): row[1] for row in role_query.all()}

    # Shifts last 30 days
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
    shifts_last_30 = (await db.execute(
        select(func.count(Shift.id)).where(Shift.created_at >= thirty_days_ago)
    )).scalar() or 0

    return SystemStatsResponse(
        total_users=total_users,
        active_users=active_users,
        inactive_users=inactive_users,
        total_stations=total_stations,
        active_stations=active_stations,
        total_shifts=total_shifts,
        published_shifts=published_shifts,
        draft_shifts=draft_shifts,
        active_sessions=active_sessions,
        users_by_role=users_by_role,
        shifts_last_30_days=shifts_last_30,
    )


# ── Audit Logs ────────────────────────────────────────────

@router.get("/audit-logs", response_model=AuditLogListResponse)
async def list_audit_logs(
    action: Optional[str] = Query(None),
    resource_type: Optional[str] = Query(None),
    user_id: Optional[uuid.UUID] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    """List audit logs with filters. Admin only."""
    query = select(AuditLog)
    count_query = select(func.count(AuditLog.id))

    if action:
        query = query.where(AuditLog.action == action)
        count_query = count_query.where(AuditLog.action == action)
    if resource_type:
        query = query.where(AuditLog.resource_type == resource_type)
        count_query = count_query.where(AuditLog.resource_type == resource_type)
    if user_id:
        query = query.where(AuditLog.user_id == user_id)
        count_query = count_query.where(AuditLog.user_id == user_id)
    if date_from:
        query = query.where(AuditLog.created_at >= date_from)
        count_query = count_query.where(AuditLog.created_at >= date_from)
    if date_to:
        query = query.where(AuditLog.created_at <= date_to)
        count_query = count_query.where(AuditLog.created_at <= date_to)

    query = query.order_by(AuditLog.created_at.desc()).offset(skip).limit(limit)

    result = await db.execute(query)
    logs = list(result.scalars().all())

    total = (await db.execute(count_query)).scalar() or 0

    return AuditLogListResponse(
        logs=[AuditLogResponse.model_validate(log) for log in logs],
        total=total,
    )


# ── Password Reset ────────────────────────────────────────

@router.post("/users/{user_id}/reset-password", status_code=200)
async def admin_reset_password(
    user_id: uuid.UUID,
    body: PasswordResetRequest,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    """Reset a user's password. Admin only."""
    user = await db.get(User, user_id)
    if user is None:
        from app.exceptions import NotFoundError
        raise NotFoundError("User")

    if len(body.new_password) < 12:
        from app.exceptions import ValidationError
        raise ValidationError("Password must be at least 12 characters")

    user.password_hash = hash_password(body.new_password)
    user.failed_login_attempts = 0
    user.locked_until = None
    db.add(user)

    await create_audit_log(
        db, user_id=current_user.id, action="password_reset",
        resource_type="user", resource_id=str(user_id),
    )

    return {"message": "Password reset successfully"}


# ── Session Management ────────────────────────────────────

@router.get("/sessions", response_model=SessionListResponse)
async def list_sessions(
    user_id: Optional[uuid.UUID] = Query(None),
    active_only: bool = Query(True),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    """List active sessions. Admin only."""
    query = select(ActiveSession)
    count_query = select(func.count(ActiveSession.id))

    if user_id:
        query = query.where(ActiveSession.user_id == user_id)
        count_query = count_query.where(ActiveSession.user_id == user_id)
    if active_only:
        query = query.where(ActiveSession.is_revoked == False)
        count_query = count_query.where(ActiveSession.is_revoked == False)

    query = query.order_by(ActiveSession.created_at.desc()).offset(skip).limit(limit)

    result = await db.execute(query)
    sessions = list(result.scalars().all())
    total = (await db.execute(count_query)).scalar() or 0

    return SessionListResponse(
        sessions=[SessionResponse.model_validate(s) for s in sessions],
        total=total,
    )


@router.post("/sessions/{session_id}/revoke", status_code=200)
async def revoke_session(
    session_id: str,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    """Revoke a specific session. Admin only."""
    result = await db.execute(
        select(ActiveSession).where(ActiveSession.session_id == session_id)
    )
    session = result.scalar_one_or_none()
    if session is None:
        from app.exceptions import NotFoundError
        raise NotFoundError("Session")

    session.is_revoked = True
    db.add(session)

    await create_audit_log(
        db, user_id=current_user.id, action="revoke_session",
        resource_type="session", resource_id=session_id,
    )

    return {"message": "Session revoked"}


@router.post("/users/{user_id}/revoke-all-sessions", status_code=200)
async def revoke_all_user_sessions(
    user_id: uuid.UUID,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    """Revoke all sessions for a user. Admin only."""
    result = await db.execute(
        select(ActiveSession).where(
            ActiveSession.user_id == user_id,
            ActiveSession.is_revoked == False,
        )
    )
    sessions = result.scalars().all()
    count = 0
    for session in sessions:
        session.is_revoked = True
        db.add(session)
        count += 1

    await create_audit_log(
        db, user_id=current_user.id, action="revoke_all_sessions",
        resource_type="user", resource_id=str(user_id),
        new_data={"revoked_count": count},
    )

    return {"message": f"Revoked {count} sessions"}


# ── User Unlock ───────────────────────────────────────────

@router.post("/users/{user_id}/unlock", status_code=200)
async def unlock_user(
    user_id: uuid.UUID,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    """Unlock a locked user account. Admin only."""
    user = await db.get(User, user_id)
    if user is None:
        from app.exceptions import NotFoundError
        raise NotFoundError("User")

    user.failed_login_attempts = 0
    user.locked_until = None
    db.add(user)

    await create_audit_log(
        db, user_id=current_user.id, action="unlock_account",
        resource_type="user", resource_id=str(user_id),
    )

    return {"message": "Account unlocked"}
