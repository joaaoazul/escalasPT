"""
Stations router — admin-only station management.
"""

from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, require_role
from app.exceptions import ConflictError, NotFoundError
from app.models.station import Station
from app.models.user import User, UserRole
from app.schemas.station import (
    StationCreate,
    StationListResponse,
    StationResponse,
    StationUpdate,
)
from app.services.audit_service import create_audit_log

router = APIRouter(prefix="/stations", tags=["Stations"])


@router.post("/", response_model=StationResponse, status_code=201)
async def create_station(
    data: StationCreate,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    """Create a new station. Admin only."""
    # Check code uniqueness
    existing = await db.execute(select(Station).where(Station.code == data.code))
    if existing.scalar_one_or_none():
        raise ConflictError(f"Station with code '{data.code}' already exists")

    station = Station(
        id=uuid.uuid4(),
        name=data.name,
        code=data.code,
        address=data.address,
        phone=data.phone,
    )
    db.add(station)
    await db.flush()

    await create_audit_log(
        db, user_id=current_user.id, action="create",
        resource_type="station", resource_id=str(station.id),
        new_data={"name": station.name, "code": station.code},
    )

    return StationResponse.model_validate(station)


@router.get("/", response_model=StationListResponse)
async def list_stations(
    is_active: Optional[bool] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    """List all stations. Admin only."""
    query = select(Station)
    count_query = select(func.count(Station.id))

    if is_active is not None:
        query = query.where(Station.is_active == is_active)
        count_query = count_query.where(Station.is_active == is_active)

    query = query.order_by(Station.name).offset(skip).limit(limit)

    result = await db.execute(query)
    stations = list(result.scalars().all())

    count_result = await db.execute(count_query)
    total = count_result.scalar()

    return StationListResponse(
        stations=[StationResponse.model_validate(s) for s in stations],
        total=total,
    )


@router.get("/{station_id}", response_model=StationResponse)
async def get_station(
    station_id: uuid.UUID,
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.COMANDANTE, UserRole.ADJUNTO)),
    db: AsyncSession = Depends(get_db),
):
    """Get a single station."""
    station = await db.get(Station, station_id)
    if station is None:
        raise NotFoundError("Station")

    # Comandante can only see their own station
    if current_user.role in (UserRole.COMANDANTE, UserRole.ADJUNTO) and current_user.station_id != station_id:
        from app.exceptions import AuthorizationError
        raise AuthorizationError("Cannot access another station")

    return StationResponse.model_validate(station)


@router.patch("/{station_id}", response_model=StationResponse)
async def update_station(
    station_id: uuid.UUID,
    data: StationUpdate,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    """Update a station. Admin only."""
    station = await db.get(Station, station_id)
    if station is None:
        raise NotFoundError("Station")

    update_dict = data.model_dump(exclude_unset=True)

    # Check code uniqueness if changing
    if "code" in update_dict:
        existing = await db.execute(
            select(Station).where(Station.code == update_dict["code"], Station.id != station_id)
        )
        if existing.scalar_one_or_none():
            raise ConflictError(f"Station with code '{update_dict['code']}' already exists")

    old_data = {"name": station.name, "code": station.code}
    for field, value in update_dict.items():
        setattr(station, field, value)

    db.add(station)
    await db.flush()

    await create_audit_log(
        db, user_id=current_user.id, action="update",
        resource_type="station", resource_id=str(station.id),
        old_data=old_data, new_data=update_dict,
    )

    return StationResponse.model_validate(station)
