"""
Notification service — create + push via WebSocket, email, and Web Push.
"""

from __future__ import annotations

import json
import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification, NotificationType
from app.models.user import User
from app.services.email_service import send_notification_email
from app.services.push_service import send_push_to_user
from app.utils.logging import get_logger

logger = get_logger(__name__)


# ── WebSocket Connection Manager ──────────────────────────

class ConnectionManager:
    """
    Manages WebSocket connections organized by station rooms.
    Thread-safe for asyncio (single event loop).
    """

    def __init__(self):
        # { station_id: { user_id: websocket } }
        self._connections: Dict[str, Dict[str, Any]] = {}

    async def connect(self, websocket, user_id: str, station_id: str) -> None:
        if station_id not in self._connections:
            self._connections[station_id] = {}
        self._connections[station_id][user_id] = websocket
        logger.info("WS connected: user=%s station=%s", user_id, station_id)

    def disconnect(self, user_id: str, station_id: str) -> None:
        if station_id in self._connections:
            self._connections[station_id].pop(user_id, None)
            if not self._connections[station_id]:
                del self._connections[station_id]
        logger.info("WS disconnected: user=%s station=%s", user_id, station_id)

    async def send_to_user(self, user_id: str, station_id: str, message: dict) -> None:
        """Send a message to a specific user."""
        ws = self._connections.get(station_id, {}).get(user_id)
        if ws:
            try:
                await ws.send_json(message)
            except Exception:
                logger.warning("Failed to send WS message to user=%s", user_id)
                self.disconnect(user_id, station_id)

    async def broadcast_to_station(self, station_id: str, message: dict) -> None:
        """Broadcast a message to all connected users in a station."""
        station_conns = self._connections.get(station_id, {})
        disconnected = []
        for uid, ws in station_conns.items():
            try:
                await ws.send_json(message)
            except Exception:
                disconnected.append(uid)

        for uid in disconnected:
            self.disconnect(uid, station_id)

    @property
    def active_connections(self) -> int:
        return sum(len(conns) for conns in self._connections.values())


# Singleton
ws_manager = ConnectionManager()


# ── Notification CRUD ─────────────────────────────────────


async def create_notification(
    db: AsyncSession,
    user_id: uuid.UUID,
    station_id: uuid.UUID,
    notification_type: NotificationType,
    title: str,
    message: str,
    data: Optional[dict] = None,
) -> Notification:
    """Create a notification and push via WebSocket."""
    notification = Notification(
        id=uuid.uuid4(),
        user_id=user_id,
        station_id=station_id,
        type=notification_type,
        title=title,
        message=message,
        data=data,
    )
    db.add(notification)
    await db.flush()

    # Push via WebSocket
    ws_payload = {
        "type": "notification",
        "data": {
            "id": str(notification.id),
            "notification_type": notification_type.value,
            "title": title,
            "message": message,
            "data": data,
            "created_at": notification.created_at.isoformat() if notification.created_at else None,
        },
    }
    await ws_manager.send_to_user(str(user_id), str(station_id), ws_payload)

    # Email notification (fire-and-forget)
    user_result = await db.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one_or_none()
    if user and user.email:
        await send_notification_email(
            user.email, notification_type.value, title, message,
        )

    # Web Push notification (fire-and-forget)
    await send_push_to_user(
        db, user_id, title, message, notification_type.value, data,
    )

    return notification


async def notify_station(
    db: AsyncSession,
    station_id: uuid.UUID,
    notification_type: NotificationType,
    title: str,
    message: str,
    data: Optional[dict] = None,
    exclude_user_id: Optional[uuid.UUID] = None,
    exclude_user_ids: Optional[set] = None,
) -> List[Notification]:
    """Create notifications for all users in a station and broadcast."""
    # Get all active users in the station
    query = select(User).where(
        and_(User.station_id == station_id, User.is_active == True)
    )
    if exclude_user_id:
        query = query.where(User.id != exclude_user_id)
    if exclude_user_ids:
        query = query.where(User.id.notin_(exclude_user_ids))

    result = await db.execute(query)
    users = result.scalars().all()

    notifications = []
    for user in users:
        notif = await create_notification(
            db, user.id, station_id, notification_type,
            title, message, data,
        )
        notifications.append(notif)

    return notifications


async def get_user_notifications(
    db: AsyncSession,
    user_id: uuid.UUID,
    skip: int = 0,
    limit: int = 50,
    unread_only: bool = False,
) -> tuple[list[Notification], int, int]:
    """
    Get notifications for a user.
    Returns: (notifications, total, unread_count)
    """
    query = select(Notification).where(Notification.user_id == user_id)
    count_query = select(func.count(Notification.id)).where(Notification.user_id == user_id)

    if unread_only:
        query = query.where(Notification.is_read == False)
        count_query = count_query.where(Notification.is_read == False)

    query = query.order_by(Notification.created_at.desc()).offset(skip).limit(limit)

    result = await db.execute(query)
    notifications = list(result.scalars().all())

    count_result = await db.execute(count_query)
    total = count_result.scalar()

    # Unread count (always total unread, regardless of filter)
    unread_result = await db.execute(
        select(func.count(Notification.id)).where(
            and_(Notification.user_id == user_id, Notification.is_read == False)
        )
    )
    unread_count = unread_result.scalar()

    return notifications, total, unread_count


async def mark_notifications_read(
    db: AsyncSession,
    user_id: uuid.UUID,
    notification_ids: List[uuid.UUID],
) -> int:
    """Mark notifications as read. Returns count of updated notifications."""
    result = await db.execute(
        update(Notification)
        .where(
            and_(
                Notification.id.in_(notification_ids),
                Notification.user_id == user_id,
            )
        )
        .values(is_read=True)
    )
    return result.rowcount
