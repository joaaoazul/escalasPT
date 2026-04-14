"""
Web Push notification service using VAPID.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import List, Optional

from pywebpush import WebPushException, webpush
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.push_subscription import PushSubscription
from app.utils.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


async def subscribe(
    db: AsyncSession,
    user_id: uuid.UUID,
    endpoint: str,
    p256dh_key: str,
    auth_key: str,
) -> PushSubscription:
    """Register or update a push subscription for a user/device."""
    # Upsert: delete existing subscription for same endpoint
    await db.execute(
        delete(PushSubscription).where(
            PushSubscription.user_id == user_id,
            PushSubscription.endpoint == endpoint,
        )
    )
    sub = PushSubscription(
        id=uuid.uuid4(),
        user_id=user_id,
        endpoint=endpoint,
        p256dh_key=p256dh_key,
        auth_key=auth_key,
    )
    db.add(sub)
    await db.flush()
    return sub


async def unsubscribe(
    db: AsyncSession,
    user_id: uuid.UUID,
    endpoint: str,
) -> bool:
    """Remove a push subscription. Returns True if found."""
    result = await db.execute(
        delete(PushSubscription).where(
            PushSubscription.user_id == user_id,
            PushSubscription.endpoint == endpoint,
        )
    )
    return result.rowcount > 0


async def get_user_subscriptions(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> List[PushSubscription]:
    """Get all push subscriptions for a user."""
    result = await db.execute(
        select(PushSubscription).where(PushSubscription.user_id == user_id)
    )
    return list(result.scalars().all())


def _send_push_sync(
    subscription_info: dict,
    payload: str,
) -> bool:
    """Synchronous web push send (runs in executor)."""
    if not settings.PUSH_ENABLED or not settings.VAPID_PRIVATE_KEY:
        return False

    try:
        webpush(
            subscription_info=subscription_info,
            data=payload,
            vapid_private_key=settings.VAPID_PRIVATE_KEY,
            vapid_claims={
                "sub": f"mailto:{settings.VAPID_CLAIMS_EMAIL}",
            },
        )
        return True
    except WebPushException as e:
        if e.response and e.response.status_code in (404, 410):
            # Subscription expired or invalid — should be cleaned up
            return False
        logger.warning("Web push failed: %s", e)
        return False
    except Exception:
        logger.exception("Unexpected web push error")
        return False


async def send_push_to_user(
    db: AsyncSession,
    user_id: uuid.UUID,
    title: str,
    message: str,
    notification_type: str,
    data: Optional[dict] = None,
) -> None:
    """Send push notification to all devices for a user (fire-and-forget)."""
    if not settings.PUSH_ENABLED:
        return

    subscriptions = await get_user_subscriptions(db, user_id)
    if not subscriptions:
        return

    payload = json.dumps({
        "title": title,
        "body": message,
        "type": notification_type,
        "data": data or {},
    })

    loop = asyncio.get_event_loop()
    stale_endpoints = []

    for sub in subscriptions:
        subscription_info = {
            "endpoint": sub.endpoint,
            "keys": {
                "p256dh": sub.p256dh_key,
                "auth": sub.auth_key,
            },
        }
        success = await loop.run_in_executor(
            None, _send_push_sync, subscription_info, payload
        )
        if not success:
            stale_endpoints.append(sub.endpoint)

    # Clean up stale subscriptions
    if stale_endpoints:
        for endpoint in stale_endpoints:
            await db.execute(
                delete(PushSubscription).where(
                    PushSubscription.user_id == user_id,
                    PushSubscription.endpoint == endpoint,
                )
            )
        logger.info("Cleaned up %d stale push subscriptions for user=%s", len(stale_endpoints), user_id)
