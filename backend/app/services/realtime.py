"""
Live updates through Supabase Realtime, for where /ws cannot run.

On Vercel the API is a function: it answers and is gone, so it cannot hold
the browser's WebSocket. Supabase Realtime holds it instead. The API sends
by calling ``realtime.send()`` in its own database transaction, and the
browser subscribes with the publishable key.

Sending through the database rather than Realtime's REST endpoint means:

- no secret API key on the server — the database connection is the
  credential;
- the message is a row in ``realtime.messages``, written in the same
  transaction as the change it announces. Realtime picks it up from
  replication, so it goes out only once that transaction commits and never
  if it rolls back.

Two rules keep the channels from leaking anything:

- Channels are public in Realtime terms (anyone with the publishable key can
  join one by name), so the names are unguessable: an HMAC of the user or
  station id under REALTIME_CHANNEL_SECRET. A user only learns their own and
  their station's, from /api/realtime/config, after authenticating.
- Messages carry no data, only which kind of thing changed. The browser then
  asks the API, which checks who is asking as it does for any other request.
  A leaked channel name tells someone when a user got a notification, never
  what it said.
"""

from __future__ import annotations

import hashlib
import hmac

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.utils.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()

_QUEUE_KEY = "realtime_signals"

_SEND = text("SELECT realtime.send('{}'::jsonb, :event, :topic, false)")


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
    """Send ``event`` on ``topic`` as part of the session's transaction."""
    if not settings.realtime_enabled:
        return
    pending: set = db.info.setdefault(_QUEUE_KEY, set())
    pending.add((topic, event))


def discard(db: AsyncSession) -> None:
    """Drop queued signals — the transaction they described rolled back."""
    db.info.pop(_QUEUE_KEY, None)


async def flush(db: AsyncSession) -> None:
    """
    Write the queued signals into the open transaction. Call before commit.

    Inside a savepoint, so that a broken realtime schema costs the signals
    and never the transaction they ride on: a shift must not fail to publish
    because a notification could not be announced. (realtime.send already
    swallows its own errors as warnings; the savepoint covers the call
    itself failing, e.g. the function missing or not executable.)
    """
    pending = db.info.pop(_QUEUE_KEY, None)
    if not pending:
        return
    try:
        async with db.begin_nested():
            for topic, event in sorted(pending):
                await db.execute(_SEND, {"event": event, "topic": topic})
    except Exception:
        # The change still commits; the browser sees it on its next refetch.
        logger.warning("Realtime signals not written (%d)", len(pending), exc_info=True)
