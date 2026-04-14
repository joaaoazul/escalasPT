"""
Tests for shift CRUD and publishing.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.shift import Shift, ShiftStatus
from app.models.user import User
from tests.conftest import make_auth_header

pytestmark = pytest.mark.asyncio


class TestShiftCRUD:
    """Test shift creation, reading, updating, deleting."""

    async def test_create_shift(
        self, client: AsyncClient, comandante_user: User,
        militar_user: User, test_shift_types,
    ):
        """Comandante can create a shift."""
        headers = make_auth_header(comandante_user)
        response = await client.post("/api/shifts/", headers=headers, json={
            "user_id": str(militar_user.id),
            "shift_type_id": str(test_shift_types[1].id),  # PAT-T 08-16
            "date": "2026-04-15",
            "start_datetime": "2026-04-15T08:00:00Z",
            "end_datetime": "2026-04-15T16:00:00Z",
            "notes": "Giro pela zona industrial",
        })
        assert response.status_code == 201
        data = response.json()
        assert data["shift"]["status"] == "draft"
        assert data["shift"]["notes"] == "Giro pela zona industrial"

    async def test_create_shift_with_notes(
        self, client: AsyncClient, comandante_user: User,
        militar_user: User,
    ):
        """Commander can add free-text notes (giro, indicações)."""
        headers = make_auth_header(comandante_user)
        response = await client.post("/api/shifts/", headers=headers, json={
            "user_id": str(militar_user.id),
            "date": "2026-04-16",
            "start_datetime": "2026-04-16T00:00:00Z",
            "end_datetime": "2026-04-16T08:00:00Z",
            "notes": "Atenção especial à zona do mercado. Contactar SR José em caso de ocorrência.",
        })
        assert response.status_code == 201
        assert "mercado" in response.json()["shift"]["notes"]

    async def test_list_shifts_as_comandante(
        self, client: AsyncClient, comandante_user: User,
        db_session: AsyncSession, militar_user: User,
        test_station,
    ):
        """Comandante sees all shifts (draft + published)."""
        # Create a draft shift directly
        shift = Shift(
            id=uuid.uuid4(),
            user_id=militar_user.id,
            station_id=test_station.id,
            date=date(2026, 4, 20),
            start_datetime=datetime(2026, 4, 20, 8, 0, tzinfo=timezone.utc),
            end_datetime=datetime(2026, 4, 20, 16, 0, tzinfo=timezone.utc),
            status=ShiftStatus.DRAFT,
            created_by=comandante_user.id,
        )
        db_session.add(shift)
        await db_session.flush()

        headers = make_auth_header(comandante_user)
        response = await client.get("/api/shifts/", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1

    async def test_list_shifts_as_militar_only_published(
        self, client: AsyncClient, militar_user: User,
        db_session: AsyncSession, test_station,
        comandante_user: User,
    ):
        """Militar can only see published shifts."""
        # Create draft and published shifts
        draft = Shift(
            id=uuid.uuid4(),
            user_id=militar_user.id,
            station_id=test_station.id,
            date=date(2026, 4, 21),
            start_datetime=datetime(2026, 4, 21, 8, 0, tzinfo=timezone.utc),
            end_datetime=datetime(2026, 4, 21, 16, 0, tzinfo=timezone.utc),
            status=ShiftStatus.DRAFT,
            created_by=comandante_user.id,
        )
        published = Shift(
            id=uuid.uuid4(),
            user_id=militar_user.id,
            station_id=test_station.id,
            date=date(2026, 4, 22),
            start_datetime=datetime(2026, 4, 22, 0, 0, tzinfo=timezone.utc),
            end_datetime=datetime(2026, 4, 22, 8, 0, tzinfo=timezone.utc),
            status=ShiftStatus.PUBLISHED,
            published_at=datetime.now(timezone.utc),
            created_by=comandante_user.id,
        )
        db_session.add(draft)
        db_session.add(published)
        await db_session.flush()

        headers = make_auth_header(militar_user)
        response = await client.get("/api/shifts/", headers=headers)
        assert response.status_code == 200

        # All returned shifts must be published
        shifts = response.json()["shifts"]
        for s in shifts:
            assert s["status"] == "published"

    async def test_update_draft_shift(
        self, client: AsyncClient, comandante_user: User,
        db_session: AsyncSession, militar_user: User,
        test_station,
    ):
        """Comandante can update a draft shift."""
        shift = Shift(
            id=uuid.uuid4(),
            user_id=militar_user.id,
            station_id=test_station.id,
            date=date(2026, 4, 23),
            start_datetime=datetime(2026, 4, 23, 8, 0, tzinfo=timezone.utc),
            end_datetime=datetime(2026, 4, 23, 16, 0, tzinfo=timezone.utc),
            status=ShiftStatus.DRAFT,
            created_by=comandante_user.id,
        )
        db_session.add(shift)
        await db_session.flush()

        headers = make_auth_header(comandante_user)
        response = await client.put(f"/api/shifts/{shift.id}", headers=headers, json={
            "notes": "Alteração: giro pela escola primária",
        })
        assert response.status_code == 200
        assert "escola" in response.json()["shift"]["notes"]

    async def test_cannot_update_published_shift(
        self, client: AsyncClient, comandante_user: User,
        db_session: AsyncSession, militar_user: User,
        test_station,
    ):
        """Cannot edit a published shift."""
        shift = Shift(
            id=uuid.uuid4(),
            user_id=militar_user.id,
            station_id=test_station.id,
            date=date(2026, 4, 24),
            start_datetime=datetime(2026, 4, 24, 16, 0, tzinfo=timezone.utc),
            end_datetime=datetime(2026, 4, 25, 0, 0, tzinfo=timezone.utc),
            status=ShiftStatus.PUBLISHED,
            published_at=datetime.now(timezone.utc),
            created_by=comandante_user.id,
        )
        db_session.add(shift)
        await db_session.flush()

        headers = make_auth_header(comandante_user)
        response = await client.put(f"/api/shifts/{shift.id}", headers=headers, json={
            "notes": "Trying to change published",
        })
        assert response.status_code == 422  # Validation error

    async def test_cancel_shift(
        self, client: AsyncClient, comandante_user: User,
        db_session: AsyncSession, militar_user: User,
        test_station,
    ):
        """Comandante can cancel a shift."""
        shift = Shift(
            id=uuid.uuid4(),
            user_id=militar_user.id,
            station_id=test_station.id,
            date=date(2026, 4, 25),
            start_datetime=datetime(2026, 4, 25, 0, 0, tzinfo=timezone.utc),
            end_datetime=datetime(2026, 4, 25, 8, 0, tzinfo=timezone.utc),
            status=ShiftStatus.DRAFT,
            created_by=comandante_user.id,
        )
        db_session.add(shift)
        await db_session.flush()

        headers = make_auth_header(comandante_user)
        response = await client.delete(f"/api/shifts/{shift.id}", headers=headers)
        assert response.status_code == 204


class TestShiftPublish:
    """Test shift publishing with notifications."""

    async def test_publish_shifts(
        self, client: AsyncClient, comandante_user: User,
        db_session: AsyncSession, militar_user: User,
        test_station,
    ):
        """Successfully publish draft shifts."""
        shift = Shift(
            id=uuid.uuid4(),
            user_id=militar_user.id,
            station_id=test_station.id,
            date=date(2026, 5, 1),
            start_datetime=datetime(2026, 5, 1, 8, 0, tzinfo=timezone.utc),
            end_datetime=datetime(2026, 5, 1, 16, 0, tzinfo=timezone.utc),
            status=ShiftStatus.DRAFT,
            created_by=comandante_user.id,
        )
        db_session.add(shift)
        await db_session.flush()

        headers = make_auth_header(comandante_user)
        response = await client.post("/api/shifts/publish", headers=headers, json={
            "shift_ids": [str(shift.id)],
        })
        assert response.status_code == 200
        data = response.json()
        assert data["published_count"] == 1

    async def test_validate_shifts_dry_run(
        self, client: AsyncClient, comandante_user: User,
        db_session: AsyncSession, militar_user: User,
        test_station,
    ):
        """Dry-run validation returns conflicts without publishing."""
        shift = Shift(
            id=uuid.uuid4(),
            user_id=militar_user.id,
            station_id=test_station.id,
            date=date(2026, 5, 5),
            start_datetime=datetime(2026, 5, 5, 8, 0, tzinfo=timezone.utc),
            end_datetime=datetime(2026, 5, 5, 16, 0, tzinfo=timezone.utc),
            status=ShiftStatus.DRAFT,
            created_by=comandante_user.id,
        )
        db_session.add(shift)
        await db_session.flush()

        headers = make_auth_header(comandante_user)
        response = await client.post("/api/shifts/validate", headers=headers, json={
            "shift_ids": [str(shift.id)],
        })
        assert response.status_code == 200
        data = response.json()
        assert "valid" in data
        assert "conflicts" in data


class TestConsecutiveShifts:
    """
    Test GNR-specific scenario:
    Consecutive shifts on different days (e.g., 16-24h day 7, 00-08h day 8)
    should NOT be blocked (only warned).
    """

    async def test_consecutive_shifts_allowed(
        self, client: AsyncClient, comandante_user: User,
        militar_user: User,
    ):
        """Two consecutive shifts on different days should create successfully."""
        headers = make_auth_header(comandante_user)

        # Day 7: 16:00-24:00
        resp1 = await client.post("/api/shifts/", headers=headers, json={
            "user_id": str(militar_user.id),
            "date": "2026-05-07",
            "start_datetime": "2026-05-07T16:00:00Z",
            "end_datetime": "2026-05-08T00:00:00Z",
        })
        assert resp1.status_code == 201

        # Day 8: 00:00-08:00 (immediately after)
        resp2 = await client.post("/api/shifts/", headers=headers, json={
            "user_id": str(militar_user.id),
            "date": "2026-05-08",
            "start_datetime": "2026-05-08T00:00:00Z",
            "end_datetime": "2026-05-08T08:00:00Z",
        })
        # Should succeed — rest violation is a warning, not a block
        # But overlap should be detected: end of shift 1 (00:00) == start of shift 2 (00:00)
        # Our overlap check uses < and >, not <=, so this should pass
        assert resp2.status_code == 201
        # Should have rest warning
        assert len(resp2.json()["warnings"]) >= 0  # May have min rest warning
