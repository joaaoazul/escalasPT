"""
Smoke tests for the notifications router: listing, mark-read, push endpoints.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.models.user import User
from tests.conftest import make_auth_header

pytestmark = pytest.mark.asyncio


class TestNotifications:
    async def test_list_notifications_empty(
        self, client: AsyncClient, militar_user: User,
    ):
        headers = make_auth_header(militar_user)
        resp = await client.get("/api/notifications/", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["notifications"] == []
        assert data["unread_count"] == 0

    async def test_mark_read_empty_list(
        self, client: AsyncClient, militar_user: User,
    ):
        headers = make_auth_header(militar_user)
        resp = await client.post(
            "/api/notifications/read", headers=headers, json={"notification_ids": []},
        )
        assert resp.status_code == 200
        assert resp.json()["updated"] == 0

    async def test_requires_auth(self, client: AsyncClient):
        resp = await client.get("/api/notifications/")
        assert resp.status_code == 401

    async def test_vapid_key_requires_auth(self, client: AsyncClient):
        resp = await client.get("/api/notifications/push/vapid-key")
        assert resp.status_code == 401

    async def test_vapid_key_authenticated(
        self, client: AsyncClient, militar_user: User,
    ):
        headers = make_auth_header(militar_user)
        resp = await client.get("/api/notifications/push/vapid-key", headers=headers)
        assert resp.status_code == 200
        assert "vapid_public_key" in resp.json()
