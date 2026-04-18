"""
Shift service — CRUD + publish + bulk operations.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from typing import List, Optional

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.exceptions import AuthorizationError, NotFoundError, ValidationError
from app.models.shift import Shift, ShiftStatus
from app.models.user import User
from app.schemas.shift import (
    ConflictDetail,
    ShiftCreate,
    ShiftResponse,
    ShiftUpdate,
)
from app.services.audit_service import create_audit_log
from app.services.conflict_detector import validate_shifts, validate_single_shift
from app.services.notification_service import ws_manager
from app.utils.logging import get_logger

logger = get_logger(__name__)


def _shift_to_response(shift: Shift) -> ShiftResponse:
    """Convert Shift model to response schema with nested info."""
    return ShiftResponse(
        id=shift.id,
        user_id=shift.user_id,
        station_id=shift.station_id,
        shift_type_id=shift.shift_type_id,
        date=shift.date,
        start_datetime=shift.start_datetime,
        end_datetime=shift.end_datetime,
        status=shift.status,
        notes=shift.notes,
        location=shift.location,
        grat_type=shift.grat_type,
        created_by=shift.created_by,
        published_at=shift.published_at,
        created_at=shift.created_at,
        updated_at=shift.updated_at,
        user_name=shift.user.full_name if shift.user else None,
        user_numero_ordem=shift.user.numero_ordem if shift.user else None,
        shift_type_name=shift.shift_type.name if shift.shift_type else None,
        shift_type_code=shift.shift_type.code if shift.shift_type else None,
        shift_type_color=shift.shift_type.color if shift.shift_type else None,
    )


async def create_shift(
    db: AsyncSession,
    data: ShiftCreate,
    station_id: uuid.UUID,
    created_by: uuid.UUID,
) -> tuple[Shift, List[ConflictDetail]]:
    """
    Create a new shift in draft status.
    Returns the shift and any validation warnings.
    """
    # Validate conflicts
    warnings = await validate_single_shift(
        db, data.user_id, data.start_datetime, data.end_datetime,
        shift_type_id=data.shift_type_id,
    )

    # Block on hard errors (overlap / fullday / duplicate service)
    errors = [w for w in warnings if w.severity == "error"]
    if errors:
        descriptions = "; ".join(e.description for e in errors)
        raise ValidationError(f"Cannot create shift: {descriptions}")

    shift = Shift(
        id=uuid.uuid4(),
        user_id=data.user_id,
        station_id=station_id,
        shift_type_id=data.shift_type_id,
        date=data.date,
        start_datetime=data.start_datetime,
        end_datetime=data.end_datetime,
        status=ShiftStatus.DRAFT,
        notes=data.notes,
        location=data.location,
        grat_type=data.grat_type,
        created_by=created_by,
    )
    db.add(shift)
    await db.flush()

    await create_audit_log(
        db, user_id=created_by, action="create",
        resource_type="shift", resource_id=str(shift.id),
        new_data={
            "user_id": str(data.user_id),
            "date": str(data.date),
            "start": str(data.start_datetime),
            "end": str(data.end_datetime),
        },
    )

    logger.info("Shift created: id=%s user=%s date=%s", shift.id, data.user_id, data.date)
    await db.refresh(shift, ["user", "shift_type"])
    return shift, [w for w in warnings if w.severity == "warning"]


async def update_shift(
    db: AsyncSession,
    shift_id: uuid.UUID,
    data: ShiftUpdate,
    station_id: uuid.UUID,
    updated_by: uuid.UUID,
) -> tuple[Shift, List[ConflictDetail]]:
    """Update a draft shift."""
    shift = await db.get(Shift, shift_id)
    if shift is None:
        raise NotFoundError("Shift")

    if shift.station_id != station_id:
        raise AuthorizationError("Cannot modify shifts from another station")

    if shift.status != ShiftStatus.DRAFT:
        raise ValidationError("Only draft shifts can be edited")

    old_data = {
        "date": str(shift.date),
        "start": str(shift.start_datetime),
        "end": str(shift.end_datetime),
        "notes": shift.notes,
    }

    update_dict = data.model_dump(exclude_unset=True)
    for field, value in update_dict.items():
        setattr(shift, field, value)

    # Re-validate after update
    warnings = await validate_single_shift(
        db, shift.user_id, shift.start_datetime, shift.end_datetime,
        exclude_shift_id=shift.id,
        shift_type_id=shift.shift_type_id,
    )
    errors = [w for w in warnings if w.severity == "error"]
    if errors:
        descriptions = "; ".join(e.description for e in errors)
        raise ValidationError(f"Cannot update shift: {descriptions}")

    db.add(shift)
    await db.flush()

    await create_audit_log(
        db, user_id=updated_by, action="update",
        resource_type="shift", resource_id=str(shift.id),
        old_data=old_data,
        new_data={k: str(v) for k, v in update_dict.items()},
    )

    await db.refresh(shift, ["user", "shift_type"])
    return shift, [w for w in warnings if w.severity == "warning"]


async def delete_shift(
    db: AsyncSession,
    shift_id: uuid.UUID,
    station_id: uuid.UUID,
    deleted_by: uuid.UUID,
) -> None:
    """Cancel a shift (soft delete via status change). Notifies the affected military if published."""
    shift = await db.get(Shift, shift_id, options=[selectinload(Shift.shift_type)])
    if shift is None:
        raise NotFoundError("Shift")

    if shift.station_id != station_id:
        raise AuthorizationError("Cannot modify shifts from another station")

    if shift.status == ShiftStatus.CANCELLED:
        raise ValidationError("Shift is already cancelled")

    was_published = shift.status == ShiftStatus.PUBLISHED
    old_status = shift.status.value
    shift.status = ShiftStatus.CANCELLED
    db.add(shift)

    await create_audit_log(
        db, user_id=deleted_by, action="cancel",
        resource_type="shift", resource_id=str(shift.id),
        old_data={"status": old_status},
        new_data={"status": ShiftStatus.CANCELLED.value},
    )

    # Notify the affected military if the shift was already published
    if was_published and shift.user_id and shift.user_id != deleted_by:
        from app.models.notification import NotificationType
        from app.services.notification_service import create_notification

        shift_type_name = shift.shift_type.name if shift.shift_type else "Turno"
        shift_date = shift.date.strftime("%d/%m/%Y") if shift.date else ""

        await create_notification(
            db,
            user_id=shift.user_id,
            station_id=station_id,
            notification_type=NotificationType.SHIFT_CANCELLED,
            title="Turno cancelado",
            message=f"O seu turno de {shift_type_name} no dia {shift_date} foi cancelado pelo comandante.",
            data={"shift_id": str(shift.id)},
        )

    # Broadcast calendar sync to all station members
    await ws_manager.broadcast_to_station(str(station_id), {
        "type": "calendar_sync",
        "reason": "shift_cancelled",
    })


async def get_shift(db: AsyncSession, shift_id: uuid.UUID) -> Shift:
    """Get a single shift by ID."""
    shift = await db.get(Shift, shift_id)
    if shift is None:
        raise NotFoundError("Shift")
    return shift


async def list_shifts(
    db: AsyncSession,
    station_id: Optional[uuid.UUID] = None,
    user_id: Optional[uuid.UUID] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    status: Optional[ShiftStatus] = None,
    skip: int = 0,
    limit: int = 100,
) -> tuple[list[Shift], int]:
    """List shifts with filters."""
    query = select(Shift)
    count_query = select(func.count(Shift.id))

    if station_id:
        query = query.where(Shift.station_id == station_id)
        count_query = count_query.where(Shift.station_id == station_id)
    if user_id:
        query = query.where(Shift.user_id == user_id)
        count_query = count_query.where(Shift.user_id == user_id)
    if date_from:
        query = query.where(Shift.date >= date_from)
        count_query = count_query.where(Shift.date >= date_from)
    if date_to:
        query = query.where(Shift.date <= date_to)
        count_query = count_query.where(Shift.date <= date_to)
    if status is not None:
        query = query.where(Shift.status == status)
        count_query = count_query.where(Shift.status == status)
    else:
        # By default exclude cancelled shifts
        query = query.where(Shift.status != ShiftStatus.CANCELLED)
        count_query = count_query.where(Shift.status != ShiftStatus.CANCELLED)

    query = query.order_by(Shift.date, Shift.start_datetime).offset(skip).limit(limit)
    query = query.options(selectinload(Shift.user), selectinload(Shift.shift_type))

    result = await db.execute(query)
    shifts = list(result.scalars().all())

    count_result = await db.execute(count_query)
    total = count_result.scalar()

    return shifts, total


async def publish_shifts(
    db: AsyncSession,
    shift_ids: List[uuid.UUID],
    station_id: uuid.UUID,
    published_by: uuid.UUID,
) -> tuple[int, List[ConflictDetail], List[Shift]]:
    """
    Publish a batch of draft shifts.
    Validates for conflicts first — blocks on errors, warns on rest issues.
    """
    # Fetch all shifts
    shifts = []
    for sid in shift_ids:
        shift = await db.get(Shift, sid)
        if shift is None:
            raise NotFoundError(f"Shift {sid}")
        if shift.station_id != station_id:
            raise AuthorizationError("Cannot publish shifts from another station")
        if shift.status != ShiftStatus.DRAFT:
            raise ValidationError(f"Shift {sid} is not in draft status")
        shifts.append(shift)

    # Validate all at once
    conflicts = await validate_shifts(db, shift_ids)
    errors = [c for c in conflicts if c.severity == "error"]

    if errors:
        return 0, conflicts

    # Publish
    now = datetime.now(timezone.utc)
    for shift in shifts:
        shift.status = ShiftStatus.PUBLISHED
        shift.published_at = now
        db.add(shift)

    await db.flush()

    await create_audit_log(
        db, user_id=published_by, action="publish",
        resource_type="shift",
        new_data={"shift_ids": [str(s) for s in shift_ids], "count": len(shifts)},
    )

    logger.info(
        "Published %d shifts for station=%s by user=%s",
        len(shifts), station_id, published_by,
    )

    # Reload with eager relationships for notification building
    loaded_result = await db.execute(
        select(Shift)
        .where(Shift.id.in_(shift_ids))
        .options(selectinload(Shift.shift_type), selectinload(Shift.user))
    )
    loaded_shifts = list(loaded_result.scalars().all())

    warnings = [c for c in conflicts if c.severity == "warning"]
    return len(shifts), warnings, loaded_shifts


async def bulk_create_shifts(
    db: AsyncSession,
    shifts_data: List[ShiftCreate],
    station_id: uuid.UUID,
    created_by: uuid.UUID,
) -> tuple[List[Shift], List[ConflictDetail]]:
    """Create multiple shifts at once (from template)."""
    created_shifts = []
    all_warnings: List[ConflictDetail] = []

    for data in shifts_data:
        shift, warnings = await create_shift(db, data, station_id, created_by)
        created_shifts.append(shift)
        all_warnings.extend(warnings)

    return created_shifts, all_warnings
