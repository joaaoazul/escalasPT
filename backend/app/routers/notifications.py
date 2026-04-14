"""
Notifications router — in-app + push subscription management.
"""

from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.notification import (
    NotificationListResponse,
    NotificationMarkReadRequest,
    NotificationResponse,
)
from app.services import notification_service
from app.services import push_service

settings = get_settings()

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("/", response_model=NotificationListResponse)
async def list_notifications(
    unread_only: bool = Query(False),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get notifications for the current user."""
    notifications, total, unread_count = await notification_service.get_user_notifications(
        db, current_user.id, skip=skip, limit=limit, unread_only=unread_only,
    )
    return NotificationListResponse(
        notifications=[NotificationResponse.model_validate(n) for n in notifications],
        total=total,
        unread_count=unread_count,
    )


@router.post("/read")
async def mark_read(
    data: NotificationMarkReadRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Mark notifications as read."""
    count = await notification_service.mark_notifications_read(
        db, current_user.id, data.notification_ids,
    )
    return {"updated": count}


# ── Push Subscription Management ──────────────────────────


class PushSubscriptionRequest(BaseModel):
    endpoint: str
    keys: dict  # { p256dh: str, auth: str }


class PushUnsubscribeRequest(BaseModel):
    endpoint: str


@router.get("/push/vapid-key")
async def get_vapid_public_key(
    current_user: User = Depends(get_current_user),
):
    """Get the VAPID public key for push subscription."""
    return {
        "vapid_public_key": settings.VAPID_PUBLIC_KEY,
        "push_enabled": settings.PUSH_ENABLED and bool(settings.VAPID_PUBLIC_KEY),
    }


@router.post("/push/subscribe")
async def push_subscribe(
    data: PushSubscriptionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Register a push subscription for the current user/device."""
    sub = await push_service.subscribe(
        db,
        user_id=current_user.id,
        endpoint=data.endpoint,
        p256dh_key=data.keys.get("p256dh", ""),
        auth_key=data.keys.get("auth", ""),
    )
    return {"id": str(sub.id), "status": "subscribed"}


@router.post("/push/unsubscribe")
async def push_unsubscribe(
    data: PushUnsubscribeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Remove a push subscription."""
    removed = await push_service.unsubscribe(db, current_user.id, data.endpoint)
    return {"status": "unsubscribed" if removed else "not_found"}
