"""
Tests for shift swap requests: create, respond, decide, cancel.
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


async def _make_shift(
    db_session: AsyncSession, user: User, station, shift_type, day: int,
    start_hour: int = 8, end_hour: int = 16, status=ShiftStatus.PUBLISHED,
) -> Shift:
    shift = Shift(
        id=uuid.uuid4(),
        user_id=user.id,
        station_id=station.id,
        shift_type_id=shift_type.id,
        date=date(2026, 6, day),
        start_datetime=datetime(2026, 6, day, start_hour, 0, tzinfo=timezone.utc),
        end_datetime=datetime(2026, 6, day, end_hour, 0, tzinfo=timezone.utc),
        status=status,
        published_at=datetime.now(timezone.utc) if status == ShiftStatus.PUBLISHED else None,
        created_by=user.id,
    )
    db_session.add(shift)
    await db_session.flush()
    return shift


class TestSwapFlow:
    """End-to-end swap lifecycle: create -> respond -> decide."""

    async def test_create_respond_approve_swaps_shifts(
        self, client: AsyncClient, db_session: AsyncSession,
        militar_user: User, militar_user_2: User, comandante_user: User,
        test_station, test_shift_types,
    ):
        req_shift = await _make_shift(db_session, militar_user, test_station, test_shift_types[0], 1)
        tgt_shift = await _make_shift(db_session, militar_user_2, test_station, test_shift_types[1], 2)

        headers1 = make_auth_header(militar_user)
        headers2 = make_auth_header(militar_user_2)
        headers_cmd = make_auth_header(comandante_user)

        resp = await client.post("/api/swaps/", headers=headers1, json={
            "requester_shift_id": str(req_shift.id),
            "target_shift_id": str(tgt_shift.id),
        })
        assert resp.status_code == 201
        swap_id = resp.json()["id"]

        resp = await client.post(
            f"/api/swaps/{swap_id}/respond", headers=headers2, params={"accept": "true"}
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "pending_approval"

        resp = await client.post(
            f"/api/swaps/{swap_id}/decide", headers=headers_cmd, params={"approve": "true"}
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "approved"

        await db_session.refresh(req_shift)
        await db_session.refresh(tgt_shift)
        assert req_shift.user_id == militar_user_2.id
        assert tgt_shift.user_id == militar_user.id

    async def test_decide_rejects_when_shift_no_longer_published(
        self, client: AsyncClient, db_session: AsyncSession,
        militar_user: User, militar_user_2: User, comandante_user: User,
        test_station, test_shift_types,
    ):
        """Regression: a shift cancelled while a swap was pending approval
        must block the physical swap instead of silently going through."""
        req_shift = await _make_shift(db_session, militar_user, test_station, test_shift_types[0], 3)
        tgt_shift = await _make_shift(db_session, militar_user_2, test_station, test_shift_types[1], 4)

        headers1 = make_auth_header(militar_user)
        headers2 = make_auth_header(militar_user_2)
        headers_cmd = make_auth_header(comandante_user)

        resp = await client.post("/api/swaps/", headers=headers1, json={
            "requester_shift_id": str(req_shift.id),
            "target_shift_id": str(tgt_shift.id),
        })
        swap_id = resp.json()["id"]

        resp = await client.post(
            f"/api/swaps/{swap_id}/respond", headers=headers2, params={"accept": "true"}
        )
        assert resp.status_code == 200

        # Simulate an admin cancelling the requester's shift while the swap
        # was awaiting command approval.
        req_shift.status = ShiftStatus.CANCELLED
        db_session.add(req_shift)
        await db_session.flush()

        resp = await client.post(
            f"/api/swaps/{swap_id}/decide", headers=headers_cmd, params={"approve": "true"}
        )
        assert resp.status_code == 422

        await db_session.refresh(tgt_shift)
        assert tgt_shift.user_id == militar_user_2.id  # unchanged

    async def test_respond_reject(
        self, client: AsyncClient, db_session: AsyncSession,
        militar_user: User, militar_user_2: User,
        test_station, test_shift_types,
    ):
        req_shift = await _make_shift(db_session, militar_user, test_station, test_shift_types[0], 5)
        tgt_shift = await _make_shift(db_session, militar_user_2, test_station, test_shift_types[1], 6)

        headers1 = make_auth_header(militar_user)
        headers2 = make_auth_header(militar_user_2)

        resp = await client.post("/api/swaps/", headers=headers1, json={
            "requester_shift_id": str(req_shift.id),
            "target_shift_id": str(tgt_shift.id),
        })
        swap_id = resp.json()["id"]

        resp = await client.post(
            f"/api/swaps/{swap_id}/respond", headers=headers2, params={"accept": "false"}
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "rejected"

    async def test_non_target_cannot_respond(
        self, client: AsyncClient, db_session: AsyncSession,
        militar_user: User, militar_user_2: User, comandante_user: User,
        test_station, test_shift_types,
    ):
        req_shift = await _make_shift(db_session, militar_user, test_station, test_shift_types[0], 7)
        tgt_shift = await _make_shift(db_session, militar_user_2, test_station, test_shift_types[1], 8)

        headers1 = make_auth_header(militar_user)
        headers_cmd = make_auth_header(comandante_user)

        resp = await client.post("/api/swaps/", headers=headers1, json={
            "requester_shift_id": str(req_shift.id),
            "target_shift_id": str(tgt_shift.id),
        })
        swap_id = resp.json()["id"]

        # Comandante is not the target of the swap and shouldn't be able to respond.
        resp = await client.post(
            f"/api/swaps/{swap_id}/respond", headers=headers_cmd, params={"accept": "true"}
        )
        assert resp.status_code == 403

    async def test_cancel_own_pending_swap(
        self, client: AsyncClient, db_session: AsyncSession,
        militar_user: User, militar_user_2: User,
        test_station, test_shift_types,
    ):
        req_shift = await _make_shift(db_session, militar_user, test_station, test_shift_types[0], 9)
        tgt_shift = await _make_shift(db_session, militar_user_2, test_station, test_shift_types[1], 10)

        headers1 = make_auth_header(militar_user)

        resp = await client.post("/api/swaps/", headers=headers1, json={
            "requester_shift_id": str(req_shift.id),
            "target_shift_id": str(tgt_shift.id),
        })
        swap_id = resp.json()["id"]

        resp = await client.post(f"/api/swaps/{swap_id}/cancel", headers=headers1)
        assert resp.status_code == 200
        assert resp.json()["status"] == "cancelled"
