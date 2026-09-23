"""
Where the browser listens for live updates — see app/services/realtime.py.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.config import get_settings
from app.dependencies import get_current_user
from app.models.user import User
from app.services import realtime

settings = get_settings()

router = APIRouter(prefix="/realtime", tags=["Realtime"])


@router.get("/config")
async def realtime_config(current_user: User = Depends(get_current_user)):
    """
    Supabase Realtime settings and this user's channels.

    ``enabled: false`` tells the frontend to fall back to /ws, which is what
    the self-hosted deployment still uses.
    """
    if not settings.realtime_enabled:
        return {"enabled": False}

    channels = [realtime.user_channel(str(current_user.id))]
    if current_user.station_id:
        channels.append(realtime.station_channel(str(current_user.station_id)))

    return {
        "enabled": True,
        "url": settings.SUPABASE_URL.rstrip("/"),
        "key": settings.SUPABASE_PUBLISHABLE_KEY,
        "channels": channels,
    }
