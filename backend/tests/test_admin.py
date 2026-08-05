"""
Tests for admin router: role boundaries and cross-station isolation.
"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.station import Station
from app.models.user import User, UserRole
from app.utils.security import hash_password
from tests.conftest import make_auth_header

pytestmark = pytest.mark.asyncio


class TestAdminRoleBoundaries:
    async def test_stats_requires_admin(
        self, client: AsyncClient, comandante_user: User,
    ):
        """Non-admin roles cannot access system-wide stats."""
        headers = make_auth_header(comandante_user)
        resp = await client.get("/api/admin/stats", headers=headers)
        assert resp.status_code == 403

    async def test_stats_as_admin(
        self, client: AsyncClient, admin_user: User,
    ):
        headers = make_auth_header(admin_user)
        resp = await client.get("/api/admin/stats", headers=headers)
        assert resp.status_code == 200
        assert "total_users" in resp.json()

    async def test_militar_cannot_reset_password(
        self, client: AsyncClient, militar_user: User, militar_user_2: User,
    ):
        headers = make_auth_header(militar_user)
        resp = await client.post(
            f"/api/admin/users/{militar_user_2.id}/reset-password",
            headers=headers,
            json={"new_password": "NewPassword123!"},
        )
        assert resp.status_code == 403

    async def test_sessions_list_requires_admin(
        self, client: AsyncClient, comandante_user: User,
    ):
        headers = make_auth_header(comandante_user)
        resp = await client.get("/api/admin/sessions", headers=headers)
        assert resp.status_code == 403

    async def test_onboard_station_requires_admin(
        self, client: AsyncClient, comandante_user: User,
    ):
        headers = make_auth_header(comandante_user)
        resp = await client.post("/api/admin/onboard-station", headers=headers, json={
            "station_name": "Posto Novo",
            "station_code": "PT-NEW",
            "comandante_username": "novo_cmd",
            "comandante_email": "novo_cmd@gnr.pt",
            "comandante_password": "NewCmdPass123!",
            "comandante_full_name": "Novo Comandante",
            "comandante_nip": "CMD001",
        })
        assert resp.status_code == 403


class TestAdminCrossStationIsolation:
    """Comandante/Adjunto must not be able to manage users from another station."""

    async def test_comandante_cannot_reset_password_other_station(
        self, client: AsyncClient, db_session: AsyncSession,
        comandante_user: User, test_station,
    ):
        other_station = Station(
            id=uuid.uuid4(), name="Outro Posto", code="PT-OTHER",
            comando_territorial="Comando de Teste", destacamento="Destacamento de Teste",
        )
        db_session.add(other_station)
        await db_session.flush()

        other_user = User(
            id=uuid.uuid4(),
            username="other_station_militar",
            email="other@gnr.pt",
            password_hash=hash_password("SomePass123!"),
            full_name="Militar de Outro Posto",
            nip="OTH999",
            role=UserRole.MILITAR,
            station_id=other_station.id,
        )
        db_session.add(other_user)
        await db_session.flush()

        headers = make_auth_header(comandante_user)
        resp = await client.post(
            f"/api/admin/users/{other_user.id}/reset-password",
            headers=headers,
            json={"new_password": "NewPassword123!"},
        )
        assert resp.status_code == 403

    async def test_comandante_cannot_unlock_other_station_user(
        self, client: AsyncClient, db_session: AsyncSession,
        comandante_user: User,
    ):
        other_station = Station(
            id=uuid.uuid4(), name="Outro Posto B", code="PT-OTHERB",
            comando_territorial="Comando de Teste", destacamento="Destacamento de Teste",
        )
        db_session.add(other_station)
        await db_session.flush()

        other_user = User(
            id=uuid.uuid4(),
            username="other_station_militar_b",
            email="otherb@gnr.pt",
            password_hash=hash_password("SomePass123!"),
            full_name="Militar de Outro Posto B",
            nip="OTHB999",
            role=UserRole.MILITAR,
            station_id=other_station.id,
        )
        db_session.add(other_user)
        await db_session.flush()

        headers = make_auth_header(comandante_user)
        resp = await client.post(
            f"/api/admin/users/{other_user.id}/unlock", headers=headers,
        )
        assert resp.status_code == 403

    async def test_comandante_can_reset_password_own_station(
        self, client: AsyncClient, comandante_user: User, militar_user: User,
    ):
        """Sanity check: same-station reset still works (not over-broadened by the fix)."""
        headers = make_auth_header(comandante_user)
        resp = await client.post(
            f"/api/admin/users/{militar_user.id}/reset-password",
            headers=headers,
            json={"new_password": "NewPassword123!"},
        )
        assert resp.status_code == 200
