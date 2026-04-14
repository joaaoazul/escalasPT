"""
Users router — admin-only user management.
"""

from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, require_role
from app.models.user import User, UserRole
from app.schemas.user import UserCreate, UserListResponse, UserResponse, UserUpdate
from app.services import user_service

router = APIRouter(prefix="/users", tags=["Users"])


@router.post("/", response_model=UserResponse, status_code=201)
async def create_user(
    data: UserCreate,
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    """Create a new user. Admin only."""
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
    current_user: User = Depends(require_role(UserRole.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    """Update a user. Admin only."""
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
