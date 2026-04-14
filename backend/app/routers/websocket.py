"""
WebSocket endpoint for real-time notifications.
Auth via JWT token as query parameter.
"""

from __future__ import annotations

import asyncio

import jwt
from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import async_session_factory
from app.models.user import ActiveSession, User
from app.services.notification_service import ws_manager
from app.utils.logging import get_logger
from app.utils.security import decode_token

logger = get_logger(__name__)
settings = get_settings()

router = APIRouter()


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(...),
):
    """
    WebSocket connection for real-time notifications.
    Client connects with: ws://host/ws?token=<access_token>
    """
    # Authenticate
    try:
        payload = decode_token(token)
    except jwt.ExpiredSignatureError:
        await websocket.close(code=4001, reason="Token expired")
        return
    except jwt.InvalidTokenError:
        await websocket.close(code=4002, reason="Invalid token")
        return

    if payload.get("type") != "access":
        await websocket.close(code=4003, reason="Invalid token type")
        return

    user_id = payload.get("sub")
    station_id = payload.get("station_id")
    session_id = payload.get("sid")

    if not user_id or not station_id:
        await websocket.close(code=4004, reason="Missing user or station info")
        return

    # Verify user exists, is active, and session is valid
    async with async_session_factory() as db:
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if user is None or not user.is_active:
            await websocket.close(code=4005, reason="User not found or inactive")
            return

        if session_id:
            sess_result = await db.execute(
                select(ActiveSession).where(
                    ActiveSession.session_id == session_id,
                    ActiveSession.is_revoked == False,  # noqa: E712
                )
            )
            if sess_result.scalar_one_or_none() is None:
                await websocket.close(code=4006, reason="Session revoked")
                return

    # Connect
    await ws_manager.connect(websocket, user_id, station_id)

    idle_timeout = 30 * 60  # 30 minutes
    msg_window: list[float] = []
    max_msgs_per_minute = 30

    try:
        while True:
            try:
                data = await asyncio.wait_for(
                    websocket.receive_json(), timeout=idle_timeout
                )
            except asyncio.TimeoutError:
                logger.info("WebSocket idle timeout for user=%s", user_id)
                await websocket.close(code=4008, reason="Idle timeout")
                break

            # Rate limit: max N messages per minute
            now = asyncio.get_event_loop().time()
            msg_window = [t for t in msg_window if now - t < 60]
            msg_window.append(now)
            if len(msg_window) > max_msgs_per_minute:
                logger.warning("WebSocket rate limit exceeded for user=%s", user_id)
                await websocket.close(code=4009, reason="Rate limit exceeded")
                break

            if data.get("type") == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        ws_manager.disconnect(user_id, station_id)
    except Exception as e:
        logger.error("WebSocket error for user=%s: %s", user_id, e)
        try:
            ws_manager.disconnect(user_id, station_id)
        except Exception:
            pass
