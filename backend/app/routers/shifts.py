"""
Shifts router — CRUD + publish + validate.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_user, get_db, require_role
from app.models.notification import NotificationType
from app.models.shift import ShiftStatus
from app.models.user import User, UserRole
from app.schemas.shift import (
    ShiftBulkCreate,
    ShiftCreate,
    ShiftListResponse,
    ShiftPublishRequest,
    ShiftPublishResponse,
    ShiftResponse,
    ShiftUpdate,
    ShiftValidateRequest,
    ShiftValidateResponse,
)
from app.services import notification_service, shift_service
from app.services.shift_service import _shift_to_response

router = APIRouter(prefix="/shifts", tags=["Shifts"])


@router.post("/", response_model=dict, status_code=201)
async def create_shift(
    data: ShiftCreate,
    current_user: User = Depends(require_role(UserRole.COMANDANTE, UserRole.ADJUNTO)),
    db: AsyncSession = Depends(get_db),
):
    """Create a new shift in draft status. Comandante or Adjunto."""
    shift, warnings = await shift_service.create_shift(
        db, data,
        station_id=current_user.station_id,
        created_by=current_user.id,
    )
    return {
        "shift": _shift_to_response(shift).model_dump(mode="json"),
        "warnings": [w.model_dump() for w in warnings],
    }


@router.get("/", response_model=ShiftListResponse)
async def list_shifts(
    station_id: Optional[uuid.UUID] = Query(None),
    user_id: Optional[uuid.UUID] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    status: Optional[ShiftStatus] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    List shifts with filters.
    - Militar: sees only published shifts from their station
    - Comandante: sees all shifts from their station
    - Admin: no shift access
    """
    from app.exceptions import AuthorizationError

    if current_user.role == UserRole.ADMIN:
        raise AuthorizationError("Admin role does not have access to shifts")

    # Force station isolation
    effective_station = current_user.station_id

    # Militar and Secretaria can only see published shifts
    if current_user.role in (UserRole.MILITAR, UserRole.SECRETARIA):
        status = ShiftStatus.PUBLISHED

    shifts, total = await shift_service.list_shifts(
        db, station_id=effective_station, user_id=user_id,
        date_from=date_from, date_to=date_to, status=status,
        skip=skip, limit=limit,
    )

    return ShiftListResponse(
        shifts=[_shift_to_response(s) for s in shifts],
        total=total,
    )


@router.get("/{shift_id}", response_model=ShiftResponse)
async def get_shift(
    shift_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a single shift."""
    from app.exceptions import AuthorizationError

    shift = await shift_service.get_shift(db, shift_id)

    if current_user.role == UserRole.ADMIN:
        raise AuthorizationError("Admin role does not have access to shifts")

    if shift.station_id != current_user.station_id:
        raise AuthorizationError("Cannot access shifts from another station")

    if current_user.role in (UserRole.MILITAR, UserRole.SECRETARIA) and shift.status != ShiftStatus.PUBLISHED:
        raise AuthorizationError("Cannot access unpublished shifts")

    return _shift_to_response(shift)


@router.put("/{shift_id}", response_model=dict)
async def update_shift(
    shift_id: uuid.UUID,
    data: ShiftUpdate,
    current_user: User = Depends(require_role(UserRole.COMANDANTE, UserRole.ADJUNTO)),
    db: AsyncSession = Depends(get_db),
):
    """Update a draft shift. Comandante or Adjunto."""
    shift, warnings = await shift_service.update_shift(
        db, shift_id, data,
        station_id=current_user.station_id,
        updated_by=current_user.id,
    )
    return {
        "shift": _shift_to_response(shift).model_dump(mode="json"),
        "warnings": [w.model_dump() for w in warnings],
    }


@router.delete("/{shift_id}", status_code=204)
async def delete_shift(
    shift_id: uuid.UUID,
    current_user: User = Depends(require_role(UserRole.COMANDANTE)),
    db: AsyncSession = Depends(get_db),
):
    """Cancel a shift. Comandante only."""
    await shift_service.delete_shift(
        db, shift_id,
        station_id=current_user.station_id,
        deleted_by=current_user.id,
    )


@router.post("/publish", response_model=ShiftPublishResponse)
async def publish_shifts(
    data: ShiftPublishRequest,
    current_user: User = Depends(require_role(UserRole.COMANDANTE)),
    db: AsyncSession = Depends(get_db),
):
    """
    Publish a batch of draft shifts.
    Validates conflicts first — blocks on overlaps, warns on rest issues.
    After publishing, notifies all station members via WebSocket.
    """
    published_count, conflicts, published_shifts = await shift_service.publish_shifts(
        db, data.shift_ids,
        station_id=current_user.station_id,
        published_by=current_user.id,
    )

    if published_count > 0:
        # Build per-user personalized notifications carrying each person's shift details
        shifts_by_user: dict = defaultdict(list)
        for shift in published_shifts:
            shifts_by_user[shift.user_id].append(shift)

        notified_user_ids: set = set()
        for uid, user_shifts in shifts_by_user.items():
            shift_entries = [
                {
                    "date": str(s.date),
                    "shift_type_code": s.shift_type.code if s.shift_type else "?",
                    "shift_type_color": s.shift_type.color if s.shift_type else "#6B7280",
                    "shift_type_name": s.shift_type.name if s.shift_type else "",
                }
                for s in user_shifts
            ]
            # Preserve insertion order of codes
            codes = ", ".join(dict.fromkeys(
                s.shift_type.code for s in user_shifts if s.shift_type
            ))
            count = len(user_shifts)
            await notification_service.create_notification(
                db,
                user_id=uid,
                station_id=current_user.station_id,
                notification_type=NotificationType.SHIFT_PUBLISHED,
                title="Escala publicada",
                message=f"Foram publicados {count} turno(s) seus: {codes}.",
                data={"shifts": shift_entries},
            )
            notified_user_ids.add(uid)

        # Summary broadcast to station staff not directly involved (commanders, etc.)
        await notification_service.notify_station(
            db,
            station_id=current_user.station_id,
            notification_type=NotificationType.SHIFT_PUBLISHED,
            title="Nova Escala Publicada",
            message=f"{current_user.full_name} publicou {published_count} turno(s) na escala.",
            data={"published_count": published_count},
            exclude_user_id=current_user.id,
            exclude_user_ids=notified_user_ids,
        )

    if published_count == 0:
        message = "Publishing blocked due to conflicts"
    elif conflicts:
        message = f"Published {published_count} shifts with {len(conflicts)} warning(s)"
    else:
        message = f"Published {published_count} shifts successfully"

    return ShiftPublishResponse(
        published_count=published_count,
        conflicts=conflicts,
        message=message,
    )


@router.post("/validate", response_model=ShiftValidateResponse)
async def validate_shifts(
    data: ShiftValidateRequest,
    current_user: User = Depends(require_role(UserRole.COMANDANTE, UserRole.ADJUNTO)),
    db: AsyncSession = Depends(get_db),
):
    """Dry-run validation — check for conflicts without publishing."""
    from app.services.conflict_detector import validate_shifts as do_validate

    conflicts = await do_validate(db, data.shift_ids)
    errors = [c for c in conflicts if c.severity == "error"]

    return ShiftValidateResponse(
        valid=len(errors) == 0,
        conflicts=conflicts,
    )


@router.post("/bulk", response_model=dict, status_code=201)
async def bulk_create_shifts(
    data: ShiftBulkCreate,
    current_user: User = Depends(require_role(UserRole.COMANDANTE, UserRole.ADJUNTO)),
    db: AsyncSession = Depends(get_db),
):
    """Create multiple shifts at once (e.g., from template)."""
    shifts, warnings = await shift_service.bulk_create_shifts(
        db, data.shifts,
        station_id=current_user.station_id,
        created_by=current_user.id,
    )
    return {
        "shifts": [_shift_to_response(s).model_dump(mode="json") for s in shifts],
        "warnings": [w.model_dump() for w in warnings],
        "created_count": len(shifts),
    }
