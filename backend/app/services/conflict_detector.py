"""
Conflict detector for shift validation.
GNR-specific rules:
- Minimum rest between shifts: 8 hours (configurable)
- No weekly hour limit
- Consecutive shifts allowed on different days (e.g., 16-24h day 7, 00-08h day 8)
- Overlap detection for the same military member
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import List

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.shift import Shift, ShiftStatus
from app.models.user import User
from app.schemas.shift import ConflictDetail
from app.utils.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


def _ensure_aware(dt: datetime) -> datetime:
    """Ensure a datetime is timezone-aware (assume UTC if naive)."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


async def check_overlap(
    db: AsyncSession,
    user_id: uuid.UUID,
    start_dt: datetime,
    end_dt: datetime,
    exclude_shift_id: uuid.UUID | None = None,
) -> List[ConflictDetail]:
    """
    Check if a shift overlaps with existing shifts for the same user.
    Returns list of overlap conflicts.
    """
    start_dt = _ensure_aware(start_dt)
    end_dt = _ensure_aware(end_dt)
    conflicts: List[ConflictDetail] = []

    query = select(Shift).where(
        and_(
            Shift.user_id == user_id,
            Shift.status != ShiftStatus.CANCELLED,
            Shift.start_datetime < end_dt,
            Shift.end_datetime > start_dt,
        )
    )

    if exclude_shift_id:
        query = query.where(Shift.id != exclude_shift_id)

    result = await db.execute(query)
    overlapping = result.scalars().all()

    # Load user once, not per conflict
    user = await db.get(User, user_id) if overlapping else None
    user_name = user.full_name if user else "Unknown"

    for existing in overlapping:
        conflicts.append(
            ConflictDetail(
                shift_id=existing.id,
                user_id=user_id,
                user_name=user_name,
                conflict_type="overlap",
                description=(
                    f"Sobreposição com turno existente: "
                    f"{existing.start_datetime.strftime('%d/%m %H:%M')}-"
                    f"{existing.end_datetime.strftime('%H:%M')}"
                ),
                severity="error",
            )
        )

    return conflicts


async def check_minimum_rest(
    db: AsyncSession,
    user_id: uuid.UUID,
    start_dt: datetime,
    end_dt: datetime,
    exclude_shift_id: uuid.UUID | None = None,
) -> List[ConflictDetail]:
    """
    Check if minimum rest period (8h) is respected between shifts.
    This is a WARNING, not an error — military can volunteer for less rest.
    """
    start_dt = _ensure_aware(start_dt)
    end_dt = _ensure_aware(end_dt)
    conflicts: List[ConflictDetail] = []
    min_rest = timedelta(hours=settings.MIN_REST_HOURS)

    # Load user once
    user = await db.get(User, user_id)
    user_name = user.full_name if user else "Unknown"

    # Check shifts ending before this one starts
    before_query = select(Shift).where(
        and_(
            Shift.user_id == user_id,
            Shift.status != ShiftStatus.CANCELLED,
            Shift.end_datetime <= start_dt,
            Shift.end_datetime > start_dt - min_rest,
        )
    )
    if exclude_shift_id:
        before_query = before_query.where(Shift.id != exclude_shift_id)

    result = await db.execute(before_query)
    before_shifts = result.scalars().all()

    for prev_shift in before_shifts:
        gap = start_dt - _ensure_aware(prev_shift.end_datetime)
        gap_hours = gap.total_seconds() / 3600
        conflicts.append(
            ConflictDetail(
                shift_id=prev_shift.id,
                user_id=user_id,
                user_name=user_name,
                conflict_type="min_rest",
                description=(
                    f"Descanso insuficiente: {gap_hours:.1f}h entre turnos "
                    f"(mínimo recomendado: {settings.MIN_REST_HOURS}h). "
                    f"Turno anterior: {prev_shift.end_datetime.strftime('%d/%m %H:%M')}"
                ),
                severity="warning",
            )
        )

    # Check shifts starting after this one ends
    after_query = select(Shift).where(
        and_(
            Shift.user_id == user_id,
            Shift.status != ShiftStatus.CANCELLED,
            Shift.start_datetime >= end_dt,
            Shift.start_datetime < end_dt + min_rest,
        )
    )
    if exclude_shift_id:
        after_query = after_query.where(Shift.id != exclude_shift_id)

    result = await db.execute(after_query)
    after_shifts = result.scalars().all()

    for next_shift in after_shifts:
        gap = _ensure_aware(next_shift.start_datetime) - end_dt
        gap_hours = gap.total_seconds() / 3600
        conflicts.append(
            ConflictDetail(
                shift_id=next_shift.id,
                user_id=user_id,
                user_name=user_name,
                conflict_type="min_rest",
                description=(
                    f"Descanso insuficiente: {gap_hours:.1f}h até próximo turno "
                    f"(mínimo recomendado: {settings.MIN_REST_HOURS}h). "
                    f"Próximo turno: {next_shift.start_datetime.strftime('%d/%m %H:%M')}"
                ),
                severity="warning",
            )
        )

    return conflicts


async def validate_shifts(
    db: AsyncSession,
    shift_ids: List[uuid.UUID],
) -> List[ConflictDetail]:
    """
    Validate a batch of shifts for conflicts.
    Runs overlap + minimum rest checks.
    Returns all conflicts found.
    """
    all_conflicts: List[ConflictDetail] = []

    for shift_id in shift_ids:
        shift = await db.get(Shift, shift_id)
        if shift is None:
            continue

        # Check overlap
        overlap_conflicts = await check_overlap(
            db, shift.user_id, shift.start_datetime, shift.end_datetime,
            exclude_shift_id=shift.id,
        )
        all_conflicts.extend(overlap_conflicts)

        # Check minimum rest
        rest_conflicts = await check_minimum_rest(
            db, shift.user_id, shift.start_datetime, shift.end_datetime,
            exclude_shift_id=shift.id,
        )
        all_conflicts.extend(rest_conflicts)

    # Deduplicate by shift_id + conflict_type
    seen = set()
    unique_conflicts = []
    for c in all_conflicts:
        key = (str(c.shift_id), c.conflict_type, str(c.user_id))
        if key not in seen:
            seen.add(key)
            unique_conflicts.append(c)

    return unique_conflicts


async def validate_single_shift(
    db: AsyncSession,
    user_id: uuid.UUID,
    start_dt: datetime,
    end_dt: datetime,
    exclude_shift_id: uuid.UUID | None = None,
) -> List[ConflictDetail]:
    """Validate a single shift (used during creation/update)."""
    conflicts = []
    conflicts.extend(
        await check_overlap(db, user_id, start_dt, end_dt, exclude_shift_id)
    )
    conflicts.extend(
        await check_minimum_rest(db, user_id, start_dt, end_dt, exclude_shift_id)
    )
    return conflicts
