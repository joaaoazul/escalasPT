"""
Users router — user management with station-scoped access.
Admin: full CRUD globally.
Comandante/Adjunto: create, update, deactivate users within their own station.
"""

from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, require_role
from app.exceptions import AuthorizationError, ValidationError
from app.models.user import User, UserRole
from app.schemas.user import UserCreate, UserListResponse, UserResponse, UserUpdate
from app.services import user_service

router = APIRouter(prefix="/users", tags=["Users"])

# Roles that a Comandante/Adjunto can assign within their station
_STATION_MANAGEABLE_ROLES = {UserRole.MILITAR, UserRole.SECRETARIA, UserRole.ADJUNTO}


@router.post("/", response_model=UserResponse, status_code=201)
async def create_user(
    data: UserCreate,
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.COMANDANTE, UserRole.ADJUNTO)),
    db: AsyncSession = Depends(get_db),
):
    """
    Create a new user.
    - Admin: can create any user in any station with any role.
    - Comandante/Adjunto: can only create users in their own station,
      with roles limited to militar, secretaria, or adjunto.
    """
    if current_user.role in (UserRole.COMANDANTE, UserRole.ADJUNTO):
        # Force the new user into the commander's station
        if data.station_id and data.station_id != current_user.station_id:
            raise AuthorizationError("Cannot create users in another station")
        data.station_id = current_user.station_id

        # Restrict assignable roles
        if data.role not in _STATION_MANAGEABLE_ROLES:
            raise AuthorizationError(
                f"Cannot assign role '{data.role.value}'. "
                f"Station commanders can only create: {', '.join(r.value for r in _STATION_MANAGEABLE_ROLES)}"
            )

    user = await user_service.create_user(db, data, created_by=current_user.id)
    return UserResponse.model_validate(user)


@router.get("/", response_model=UserListResponse)
async def list_users(
    station_id: Optional[uuid.UUID] = Query(None),
    role: Optional[UserRole] = Query(None),
    is_active: Optional[bool] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.COMANDANTE, UserRole.ADJUNTO, UserRole.SECRETARIA)),
    db: AsyncSession = Depends(get_db),
):
    """
    List users. Admin sees all; comandante/adjunto/secretaria see only their station.
    """
    if current_user.role in (UserRole.COMANDANTE, UserRole.ADJUNTO, UserRole.SECRETARIA):
        station_id = current_user.station_id

    users, total = await user_service.list_users(db, station_id, role, is_active, skip, limit)
    return UserListResponse(
        users=[UserResponse.model_validate(u) for u in users],
        total=total,
    )


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: uuid.UUID,
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.COMANDANTE, UserRole.ADJUNTO, UserRole.SECRETARIA)),
    db: AsyncSession = Depends(get_db),
):
    """Get a single user by ID."""
    user = await user_service.get_user_by_id(db, user_id)

    # Station-scoped roles can only see users from their station
    if current_user.role in (UserRole.COMANDANTE, UserRole.ADJUNTO, UserRole.SECRETARIA) and user.station_id != current_user.station_id:
        from app.exceptions import AuthorizationError
        raise AuthorizationError("Cannot access users from another station")

    return UserResponse.model_validate(user)


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: uuid.UUID,
    data: UserUpdate,
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.COMANDANTE, UserRole.ADJUNTO)),
    db: AsyncSession = Depends(get_db),
):
    """
    Update a user.
    - Admin: can update any user.
    - Comandante/Adjunto: can only update users within their station,
      cannot promote beyond station-manageable roles, cannot reassign
      users to another station.
    """
    if current_user.role in (UserRole.COMANDANTE, UserRole.ADJUNTO):
        target_user = await user_service.get_user_by_id(db, user_id)

        # Must be in the same station
        if target_user.station_id != current_user.station_id:
            raise AuthorizationError("Cannot update users from another station")

        # Cannot change station assignment
        update_dict = data.model_dump(exclude_unset=True)
        if "station_id" in update_dict and update_dict["station_id"] != current_user.station_id:
            raise AuthorizationError("Cannot reassign users to another station")

        # Restrict role changes
        if "role" in update_dict:
            new_role = UserRole(update_dict["role"])
            if new_role not in _STATION_MANAGEABLE_ROLES:
                raise AuthorizationError(
                    f"Cannot assign role '{new_role.value}'. "
                    f"Station commanders can only assign: {', '.join(r.value for r in _STATION_MANAGEABLE_ROLES)}"
                )

    user = await user_service.update_user(db, user_id, data, updated_by=current_user.id)
    return UserResponse.model_validate(user)


@router.post("/{user_id}/anonymize", response_model=UserResponse)
async def anonymize_user(
    user_id: uuid.UUID,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    """
    RGPD Art. 17 — Anonymize a deactivated user's personal data.
    Replaces name, email, NIP, and phone with anonymous values while
    preserving shift history for operational auditing. Admin only.
    """
    user = await user_service.anonymize_user(db, user_id, anonymized_by=current_user.id)
    return UserResponse.model_validate(user)
