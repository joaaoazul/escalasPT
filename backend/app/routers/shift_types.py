"""
ShiftTypes router — CRUD for shift type templates.
"""

from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_user, get_db, require_role
from app.exceptions import NotFoundError
from app.models.shift_type import ShiftType
from app.models.user import User, UserRole
from app.schemas.shift_type import (
    ShiftTypeCreate,
    ShiftTypeListResponse,
    ShiftTypeResponse,
    ShiftTypeUpdate,
)
from app.services.audit_service import create_audit_log

router = APIRouter(prefix="/shift-types", tags=["Shift Types"])


@router.post("/", response_model=ShiftTypeResponse, status_code=201)
async def create_shift_type(
    data: ShiftTypeCreate,
    current_user: User = Depends(require_role(UserRole.COMANDANTE)),
    db: AsyncSession = Depends(get_db),
):
    """Create a new shift type for the commander's station."""
    shift_type = ShiftType(
        id=uuid.uuid4(),
        station_id=current_user.station_id,
        name=data.name,
        code=data.code,
        description=data.description,
        start_time=data.start_time,
        end_time=data.end_time,
        color=data.color,
        min_staff=data.min_staff,
        is_absence=data.is_absence,
        fixed_slots=data.fixed_slots,
    )
    db.add(shift_type)
    await db.flush()

    await create_audit_log(
        db, user_id=current_user.id, action="create",
        resource_type="shift_type", resource_id=str(shift_type.id),
        new_data={"name": data.name, "code": data.code},
    )

    return ShiftTypeResponse.model_validate(shift_type)


@router.get("/", response_model=ShiftTypeListResponse)
async def list_shift_types(
    is_active: Optional[bool] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List shift types for the user's station."""
    from app.exceptions import AuthorizationError

    if current_user.role == UserRole.ADMIN:
        raise AuthorizationError("Admin does not have access to shift types")

    query = select(ShiftType).where(ShiftType.station_id == current_user.station_id)
    count_query = select(func.count(ShiftType.id)).where(
        ShiftType.station_id == current_user.station_id
    )

    if is_active is not None:
        query = query.where(ShiftType.is_active == is_active)
        count_query = count_query.where(ShiftType.is_active == is_active)

    query = query.order_by(ShiftType.name).offset(skip).limit(limit)

    result = await db.execute(query)
    shift_types = list(result.scalars().all())

    count_result = await db.execute(count_query)
    total = count_result.scalar()

    return ShiftTypeListResponse(
        shift_types=[ShiftTypeResponse.model_validate(st) for st in shift_types],
        total=total,
    )


@router.patch("/{shift_type_id}", response_model=ShiftTypeResponse)
async def update_shift_type(
    shift_type_id: uuid.UUID,
    data: ShiftTypeUpdate,
    current_user: User = Depends(require_role(UserRole.COMANDANTE)),
    db: AsyncSession = Depends(get_db),
):
    """Update a shift type. Comandante only."""
    from app.exceptions import AuthorizationError

    shift_type = await db.get(ShiftType, shift_type_id)
    if shift_type is None:
        raise NotFoundError("Shift type")

    if shift_type.station_id != current_user.station_id:
        raise AuthorizationError("Cannot modify shift types from another station")

    update_dict = data.model_dump(exclude_unset=True)
    for field, value in update_dict.items():
        setattr(shift_type, field, value)

    db.add(shift_type)
    await db.flush()

    await create_audit_log(
        db, user_id=current_user.id, action="update",
        resource_type="shift_type", resource_id=str(shift_type.id),
        new_data=update_dict,
    )

    return ShiftTypeResponse.model_validate(shift_type)
