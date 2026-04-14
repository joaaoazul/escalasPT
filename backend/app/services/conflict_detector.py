"""
Conflict detector for shift validation.
GNR-specific rules:
1. Full-day types (Folga, Férias, absences) block ALL other shifts on the same day.
2. Normal services (AT, OC, INQ, SEC, T, INST) — max 1 per day per militar.
3. Gratificados (GRAT) — can accumulate with a normal service but cannot overlap in time.
4. Time overlap — never allowed between any two shifts.
5. Minimum rest between shifts: 8 hours (configurable) — warning only.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from typing import List, Optional

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.models.shift import Shift, ShiftStatus
from app.models.shift_type import ShiftType
from app.models.user import User
from app.schemas.shift import ConflictDetail
from app.utils.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()

# Shift type codes that are "gratificados" — can accumulate with normal services
_GRAT_CODES = {"GRAT"}

# Shift type codes that are full-day blockers (nothing else allowed)
# is_absence=True types + Folga
_FULLDAY_CODES = {"F", "FER", "CONV", "MF", "DIL", "LIC"}


def _is_fullday(shift_type: Optional[ShiftType]) -> bool:
    """Check if a shift type is a full-day blocker."""
    if shift_type is None:
        return False
    return shift_type.is_absence or shift_type.code in _FULLDAY_CODES


def _is_grat(shift_type: Optional[ShiftType]) -> bool:
    """Check if a shift type is a gratificado."""
    if shift_type is None:
        return False
    return shift_type.code in _GRAT_CODES


def _is_normal_service(shift_type: Optional[ShiftType]) -> bool:
    """Check if a shift type is a normal service (not GRAT, not absence/folga)."""
    if shift_type is None:
        return True  # conservative: treat unknown as normal
    return not _is_fullday(shift_type) and not _is_grat(shift_type)


def _ensure_aware(dt: datetime) -> datetime:
    """Ensure a datetime is timezone-aware (assume UTC if naive)."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


async def _get_user_shifts_on_date(
    db: AsyncSession,
    user_id: uuid.UUID,
    shift_date: date,
    exclude_shift_id: Optional[uuid.UUID] = None,
) -> List[Shift]:
    """Get all active shifts for a user on a given date."""
    query = (
        select(Shift)
        .options(selectinload(Shift.shift_type))
        .where(
            and_(
                Shift.user_id == user_id,
                Shift.date == shift_date,
                Shift.status != ShiftStatus.CANCELLED,
            )
        )
    )
    if exclude_shift_id:
        query = query.where(Shift.id != exclude_shift_id)
    result = await db.execute(query)
    return list(result.scalars().all())


async def check_overlap(
    db: AsyncSession,
    user_id: uuid.UUID,
    start_dt: datetime,
    end_dt: datetime,
    exclude_shift_id: uuid.UUID | None = None,
) -> List[ConflictDetail]:
    """
    Check if a shift overlaps in TIME with existing shifts for the same user.
    Returns list of overlap conflicts.
    """
    start_dt = _ensure_aware(start_dt)
    end_dt = _ensure_aware(end_dt)
    conflicts: List[ConflictDetail] = []

    query = (
        select(Shift)
        .options(selectinload(Shift.shift_type))
        .where(
            and_(
                Shift.user_id == user_id,
                Shift.status != ShiftStatus.CANCELLED,
                Shift.start_datetime < end_dt,
                Shift.end_datetime > start_dt,
            )
        )
    )

    if exclude_shift_id:
        query = query.where(Shift.id != exclude_shift_id)

    result = await db.execute(query)
    overlapping = result.scalars().all()

    user = await db.get(User, user_id) if overlapping else None
    user_name = user.full_name if user else "Desconhecido"

    for existing in overlapping:
        conflicts.append(
            ConflictDetail(
                shift_id=existing.id,
                user_id=user_id,
                user_name=user_name,
                conflict_type="overlap",
                description=(
                    f"Sobreposição horária com turno existente: "
                    f"{existing.start_datetime.strftime('%d/%m %H:%M')}-"
                    f"{existing.end_datetime.strftime('%H:%M')}"
                    f" ({existing.shift_type.code if existing.shift_type else '?'})"
                ),
                severity="error",
            )
        )

    return conflicts


async def check_fullday_conflict(
    db: AsyncSession,
    user_id: uuid.UUID,
    shift_date: date,
    shift_type: Optional[ShiftType],
    exclude_shift_id: uuid.UUID | None = None,
) -> List[ConflictDetail]:
    """
    Check full-day type conflicts:
    - If the new shift is a full-day type, no other shifts allowed that day.
    - If existing shifts include a full-day type, new shift is blocked.
    """
    conflicts: List[ConflictDetail] = []
    existing = await _get_user_shifts_on_date(db, user_id, shift_date, exclude_shift_id)

    if not existing:
        return conflicts

    user = await db.get(User, user_id)
    user_name = user.full_name if user else "Desconhecido"

    new_is_fullday = _is_fullday(shift_type)

    for ex in existing:
        ex_is_fullday = _is_fullday(ex.shift_type)
        ex_code = ex.shift_type.code if ex.shift_type else "?"

        if new_is_fullday:
            # New shift is full-day → conflicts with ANY existing shift
            conflicts.append(
                ConflictDetail(
                    shift_id=ex.id,
                    user_id=user_id,
                    user_name=user_name,
                    conflict_type="fullday_block",
                    description=(
                        f"Tipo de dia inteiro ({shift_type.code if shift_type else '?'}) "
                        f"não pode coexistir com {ex_code} em {shift_date.strftime('%d/%m')}"
                    ),
                    severity="error",
                )
            )
        elif ex_is_fullday:
            # Existing shift is full-day → blocks new shift
            conflicts.append(
                ConflictDetail(
                    shift_id=ex.id,
                    user_id=user_id,
                    user_name=user_name,
                    conflict_type="fullday_block",
                    description=(
                        f"Militar tem {ex_code} em {shift_date.strftime('%d/%m')} — "
                        f"não pode acumular outros serviços"
                    ),
                    severity="error",
                )
            )

    return conflicts


async def check_duplicate_normal_service(
    db: AsyncSession,
    user_id: uuid.UUID,
    shift_date: date,
    shift_type: Optional[ShiftType],
    exclude_shift_id: uuid.UUID | None = None,
) -> List[ConflictDetail]:
    """
    Check that a militar has at most 1 normal service per day.
    Gratificados don't count towards this limit.
    """
    conflicts: List[ConflictDetail] = []

    if not _is_normal_service(shift_type):
        return conflicts  # GRAT / absence / folga — skip this check

    existing = await _get_user_shifts_on_date(db, user_id, shift_date, exclude_shift_id)

    user = await db.get(User, user_id)
    user_name = user.full_name if user else "Desconhecido"

    for ex in existing:
        if _is_normal_service(ex.shift_type):
            ex_code = ex.shift_type.code if ex.shift_type else "?"
            new_code = shift_type.code if shift_type else "?"
            conflicts.append(
                ConflictDetail(
                    shift_id=ex.id,
                    user_id=user_id,
                    user_name=user_name,
                    conflict_type="duplicate_service",
                    description=(
                        f"Já tem serviço normal ({ex_code}) em "
                        f"{shift_date.strftime('%d/%m')} — não pode acumular "
                        f"outro serviço normal ({new_code})"
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

    user = await db.get(User, user_id)
    user_name = user.full_name if user else "Desconhecido"

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
    Runs all checks: overlap, full-day, duplicate normal, min rest.
    """
    all_conflicts: List[ConflictDetail] = []

    for shift_id in shift_ids:
        shift = await db.get(Shift, shift_id)
        if shift is None:
            continue
        await db.refresh(shift, ["shift_type"])

        shift_type = shift.shift_type

        # Time overlap
        all_conflicts.extend(
            await check_overlap(
                db, shift.user_id, shift.start_datetime, shift.end_datetime,
                exclude_shift_id=shift.id,
            )
        )
        # Full-day block
        all_conflicts.extend(
            await check_fullday_conflict(
                db, shift.user_id, shift.date, shift_type,
                exclude_shift_id=shift.id,
            )
        )
        # Duplicate normal service
        all_conflicts.extend(
            await check_duplicate_normal_service(
                db, shift.user_id, shift.date, shift_type,
                exclude_shift_id=shift.id,
            )
        )
        # Minimum rest
        all_conflicts.extend(
            await check_minimum_rest(
                db, shift.user_id, shift.start_datetime, shift.end_datetime,
                exclude_shift_id=shift.id,
            )
        )

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
    shift_type_id: uuid.UUID | None = None,
) -> List[ConflictDetail]:
    """Validate a single shift (used during creation/update)."""
    # Resolve shift type
    shift_type: Optional[ShiftType] = None
    if shift_type_id:
        shift_type = await db.get(ShiftType, shift_type_id)

    # Derive date from start_datetime
    shift_date = _ensure_aware(start_dt).date()

    conflicts: List[ConflictDetail] = []

    # Time overlap
    conflicts.extend(
        await check_overlap(db, user_id, start_dt, end_dt, exclude_shift_id)
    )
    # Full-day block
    conflicts.extend(
        await check_fullday_conflict(db, user_id, shift_date, shift_type, exclude_shift_id)
    )
    # Duplicate normal service
    conflicts.extend(
        await check_duplicate_normal_service(db, user_id, shift_date, shift_type, exclude_shift_id)
    )
    # Minimum rest
    conflicts.extend(
        await check_minimum_rest(db, user_id, start_dt, end_dt, exclude_shift_id)
    )

    return conflicts


async def validate_swap(
    db: AsyncSession,
    requester_shift: Shift,
    target_shift: Shift,
) -> List[ConflictDetail]:
    """
    Validate a swap: check if swapping user_ids on two shifts creates conflicts.
    Simulates the swap and checks both parties.
    """
    conflicts: List[ConflictDetail] = []

    # After swap: requester gets target's shift, target gets requester's shift
    # Check requester in target's shift slot
    await db.refresh(target_shift, ["shift_type"])
    conflicts.extend(
        await validate_single_shift(
            db,
            user_id=requester_shift.user_id,
            start_dt=target_shift.start_datetime,
            end_dt=target_shift.end_datetime,
            exclude_shift_id=requester_shift.id,
            shift_type_id=target_shift.shift_type_id,
        )
    )

    # Check target in requester's shift slot
    await db.refresh(requester_shift, ["shift_type"])
    conflicts.extend(
        await validate_single_shift(
            db,
            user_id=target_shift.user_id,
            start_dt=requester_shift.start_datetime,
            end_dt=requester_shift.end_datetime,
            exclude_shift_id=target_shift.id,
            shift_type_id=requester_shift.shift_type_id,
        )
    )

    return conflicts
