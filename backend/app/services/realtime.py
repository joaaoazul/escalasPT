"""
Live updates through Supabase Realtime, for where /ws cannot run.

On Vercel the API is a function: it answers and is gone, so it cannot hold
the browser's WebSocket. Supabase Realtime holds it instead. The API sends
over its REST endpoint, and the browser subscribes with the publishable key.

Two rules keep that from leaking anything:

- Channels are public in Realtime terms (anyone with the publishable key can
  join one by name), so the names are unguessable: an HMAC of the user or
  station id under REALTIME_CHANNEL_SECRET. A user only learns their own and
  their station's, from /api/realtime/config, after authenticating.
- Messages carry no data, only which kind of thing changed. The browser then
  asks the API, which checks who is asking as it does for any other request.
  A leaked channel name tells someone when a user got a notification, never
  what it said.

Signals are queued on the DB session and sent by get_db only after the
commit, so a browser that reacts at once finds the change already there.
"""

from __future__ import annotations

import hashlib
import hmac
from typing import Iterable

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.utils.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()

_QUEUE_KEY = "realtime_signals"


def _channel(kind: str, ident: str) -> str:
    digest = hmac.new(
        settings.REALTIME_CHANNEL_SECRET.encode(),
        f"{kind}:{ident}".encode(),
        hashlib.sha256,
    ).hexdigest()
    return f"{kind}-{digest[:40]}"


def user_channel(user_id: str) -> str:
    return _channel("user", str(user_id))


def station_channel(station_id: str) -> str:
    return _channel("station", str(station_id))


def queue(db: AsyncSession, topic: str, event: str) -> None:
    """Send ``event`` on ``topic`` once the session's transaction commits."""
    if not settings.realtime_enabled:
        return
    pending: set = db.info.setdefault(_QUEUE_KEY, set())
    pending.add((topic, event))


def discard(db: AsyncSession) -> None:
    """Drop queued signals — the transaction they described rolled back."""
    db.info.pop(_QUEUE_KEY, None)


async def flush(db: AsyncSession) -> None:
    """Send what the committed transaction queued. Never raises."""
    pending = db.info.pop(_QUEUE_KEY, None)
    if pending:
        await _broadcast(pending)


async def _broadcast(signals: Iterable[tuple[str, str]]) -> None:
    messages = [
        {"topic": topic, "event": event, "payload": {}}
        for topic, event in sorted(signals)
    ]
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(
                f"{settings.SUPABASE_URL.rstrip('/')}/realtime/v1/api/broadcast",
                json={"messages": messages},
                # apikey alone, as Supabase documents for this endpoint: the
                # sb_secret_ keys are not JWTs, and putting one in
                # Authorization gets the request rejected as a bad token.
                headers={"apikey": settings.SUPABASE_SECRET_KEY},
            )
            response.raise_for_status()
    except Exception:
        # The change is committed either way; a missed signal only means the
        # browser shows it on its next refetch instead of straight away.
        logger.warning("Realtime broadcast failed (%d messages)", len(messages), exc_info=True)
