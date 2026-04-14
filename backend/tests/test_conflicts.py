"""
Tests for the conflict detector.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.shift import Shift, ShiftStatus
from app.models.user import User
from app.services.conflict_detector import (
    check_minimum_rest,
    check_overlap,
    validate_single_shift,
)

pytestmark = pytest.mark.asyncio


class TestOverlapDetection:
    """Test overlap detection between shifts."""

    async def test_no_overlap(
        self, db_session: AsyncSession, militar_user: User,
        test_station, comandante_user: User,
    ):
        """Non-overlapping shifts should return no conflicts."""
        # Existing: 08:00-16:00
        existing = Shift(
            id=uuid.uuid4(),
            user_id=militar_user.id,
            station_id=test_station.id,
            date=date(2026, 6, 1),
            start_datetime=datetime(2026, 6, 1, 8, 0, tzinfo=timezone.utc),
            end_datetime=datetime(2026, 6, 1, 16, 0, tzinfo=timezone.utc),
            status=ShiftStatus.DRAFT,
            created_by=comandante_user.id,
        )
        db_session.add(existing)
        await db_session.flush()

        # New: 16:00-24:00 (no overlap)
        conflicts = await check_overlap(
            db_session, militar_user.id,
            start_dt=datetime(2026, 6, 1, 16, 0, tzinfo=timezone.utc),
            end_dt=datetime(2026, 6, 2, 0, 0, tzinfo=timezone.utc),
        )
        assert len(conflicts) == 0

    async def test_full_overlap(
        self, db_session: AsyncSession, militar_user: User,
        test_station, comandante_user: User,
    ):
        """Identical time ranges should detect overlap."""
        existing = Shift(
            id=uuid.uuid4(),
            user_id=militar_user.id,
            station_id=test_station.id,
            date=date(2026, 6, 2),
            start_datetime=datetime(2026, 6, 2, 8, 0, tzinfo=timezone.utc),
            end_datetime=datetime(2026, 6, 2, 16, 0, tzinfo=timezone.utc),
            status=ShiftStatus.DRAFT,
            created_by=comandante_user.id,
        )
        db_session.add(existing)
        await db_session.flush()

        # Same time range
        conflicts = await check_overlap(
            db_session, militar_user.id,
            start_dt=datetime(2026, 6, 2, 8, 0, tzinfo=timezone.utc),
            end_dt=datetime(2026, 6, 2, 16, 0, tzinfo=timezone.utc),
        )
        assert len(conflicts) == 1
        assert conflicts[0].conflict_type == "overlap"
        assert conflicts[0].severity == "error"

    async def test_partial_overlap(
        self, db_session: AsyncSession, militar_user: User,
        test_station, comandante_user: User,
    ):
        """Partially overlapping shifts should detect conflict."""
        existing = Shift(
            id=uuid.uuid4(),
            user_id=militar_user.id,
            station_id=test_station.id,
            date=date(2026, 6, 3),
            start_datetime=datetime(2026, 6, 3, 8, 0, tzinfo=timezone.utc),
            end_datetime=datetime(2026, 6, 3, 16, 0, tzinfo=timezone.utc),
            status=ShiftStatus.DRAFT,
            created_by=comandante_user.id,
        )
        db_session.add(existing)
        await db_session.flush()

        # 12:00-20:00 overlaps with 08:00-16:00
        conflicts = await check_overlap(
            db_session, militar_user.id,
            start_dt=datetime(2026, 6, 3, 12, 0, tzinfo=timezone.utc),
            end_dt=datetime(2026, 6, 3, 20, 0, tzinfo=timezone.utc),
        )
        assert len(conflicts) == 1

    async def test_cancelled_shifts_ignored(
        self, db_session: AsyncSession, militar_user: User,
        test_station, comandante_user: User,
    ):
        """Cancelled shifts should not trigger overlap."""
        existing = Shift(
            id=uuid.uuid4(),
            user_id=militar_user.id,
            station_id=test_station.id,
            date=date(2026, 6, 4),
            start_datetime=datetime(2026, 6, 4, 8, 0, tzinfo=timezone.utc),
            end_datetime=datetime(2026, 6, 4, 16, 0, tzinfo=timezone.utc),
            status=ShiftStatus.CANCELLED,
            created_by=comandante_user.id,
        )
        db_session.add(existing)
        await db_session.flush()

        conflicts = await check_overlap(
            db_session, militar_user.id,
            start_dt=datetime(2026, 6, 4, 8, 0, tzinfo=timezone.utc),
            end_dt=datetime(2026, 6, 4, 16, 0, tzinfo=timezone.utc),
        )
        assert len(conflicts) == 0

    async def test_different_user_no_overlap(
        self, db_session: AsyncSession, militar_user: User,
        militar_user_2: User, test_station, comandante_user: User,
    ):
        """Shifts for different users should not conflict."""
        existing = Shift(
            id=uuid.uuid4(),
            user_id=militar_user.id,
            station_id=test_station.id,
            date=date(2026, 6, 5),
            start_datetime=datetime(2026, 6, 5, 8, 0, tzinfo=timezone.utc),
            end_datetime=datetime(2026, 6, 5, 16, 0, tzinfo=timezone.utc),
            status=ShiftStatus.DRAFT,
            created_by=comandante_user.id,
        )
        db_session.add(existing)
        await db_session.flush()

        # Check for user 2 — should not find user 1's shift
        conflicts = await check_overlap(
            db_session, militar_user_2.id,
            start_dt=datetime(2026, 6, 5, 8, 0, tzinfo=timezone.utc),
            end_dt=datetime(2026, 6, 5, 16, 0, tzinfo=timezone.utc),
        )
        assert len(conflicts) == 0


class TestMinimumRest:
    """Test minimum rest period detection (8h for GNR)."""

    async def test_sufficient_rest(
        self, db_session: AsyncSession, militar_user: User,
        test_station, comandante_user: User,
    ):
        """10 hours between shifts — no warning."""
        existing = Shift(
            id=uuid.uuid4(),
            user_id=militar_user.id,
            station_id=test_station.id,
            date=date(2026, 6, 10),
            start_datetime=datetime(2026, 6, 10, 0, 0, tzinfo=timezone.utc),
            end_datetime=datetime(2026, 6, 10, 8, 0, tzinfo=timezone.utc),
            status=ShiftStatus.DRAFT,
            created_by=comandante_user.id,
        )
        db_session.add(existing)
        await db_session.flush()

        # New shift 10h later: 18:00-02:00
        conflicts = await check_minimum_rest(
            db_session, militar_user.id,
            start_dt=datetime(2026, 6, 10, 18, 0, tzinfo=timezone.utc),
            end_dt=datetime(2026, 6, 11, 2, 0, tzinfo=timezone.utc),
        )
        assert len(conflicts) == 0

    async def test_insufficient_rest_warning(
        self, db_session: AsyncSession, militar_user: User,
        test_station, comandante_user: User,
    ):
        """Only 4 hours between shifts — warning (not error)."""
        existing = Shift(
            id=uuid.uuid4(),
            user_id=militar_user.id,
            station_id=test_station.id,
            date=date(2026, 6, 11),
            start_datetime=datetime(2026, 6, 11, 0, 0, tzinfo=timezone.utc),
            end_datetime=datetime(2026, 6, 11, 8, 0, tzinfo=timezone.utc),
            status=ShiftStatus.DRAFT,
            created_by=comandante_user.id,
        )
        db_session.add(existing)
        await db_session.flush()

        # New shift 4h later: 12:00-20:00
        conflicts = await check_minimum_rest(
            db_session, militar_user.id,
            start_dt=datetime(2026, 6, 11, 12, 0, tzinfo=timezone.utc),
            end_dt=datetime(2026, 6, 11, 20, 0, tzinfo=timezone.utc),
        )
        assert len(conflicts) >= 1
        # Must be a warning, NOT an error (GNR allows voluntary short rest)
        assert all(c.severity == "warning" for c in conflicts)
        assert all(c.conflict_type == "min_rest" for c in conflicts)

    async def test_consecutive_shifts_zero_rest(
        self, db_session: AsyncSession, militar_user: User,
        test_station, comandante_user: User,
    ):
        """
        GNR scenario: 16:00-00:00 day 7, then 00:00-08:00 day 8.
        Zero rest but should only warn, not block.
        """
        existing = Shift(
            id=uuid.uuid4(),
            user_id=militar_user.id,
            station_id=test_station.id,
            date=date(2026, 6, 7),
            start_datetime=datetime(2026, 6, 7, 16, 0, tzinfo=timezone.utc),
            end_datetime=datetime(2026, 6, 8, 0, 0, tzinfo=timezone.utc),
            status=ShiftStatus.DRAFT,
            created_by=comandante_user.id,
        )
        db_session.add(existing)
        await db_session.flush()

        # Immediately after: 00:00-08:00
        conflicts = await check_minimum_rest(
            db_session, militar_user.id,
            start_dt=datetime(2026, 6, 8, 0, 0, tzinfo=timezone.utc),
            end_dt=datetime(2026, 6, 8, 8, 0, tzinfo=timezone.utc),
        )
        # Should warn but NOT error
        for c in conflicts:
            assert c.severity == "warning"


class TestValidateSingleShift:
    """Test combined validation (overlap + rest)."""

    async def test_valid_shift_no_conflicts(
        self, db_session: AsyncSession, militar_user: User,
        test_station, comandante_user: User,
    ):
        """A valid shift with no nearby shifts returns empty conflicts."""
        conflicts = await validate_single_shift(
            db_session, militar_user.id,
            start_dt=datetime(2026, 7, 1, 8, 0, tzinfo=timezone.utc),
            end_dt=datetime(2026, 7, 1, 16, 0, tzinfo=timezone.utc),
        )
        assert len(conflicts) == 0

    async def test_overlap_blocks_creation(
        self, db_session: AsyncSession, militar_user: User,
        test_station, comandante_user: User,
    ):
        """Overlapping shift returns error-severity conflict."""
        existing = Shift(
            id=uuid.uuid4(),
            user_id=militar_user.id,
            station_id=test_station.id,
            date=date(2026, 7, 2),
            start_datetime=datetime(2026, 7, 2, 8, 0, tzinfo=timezone.utc),
            end_datetime=datetime(2026, 7, 2, 16, 0, tzinfo=timezone.utc),
            status=ShiftStatus.DRAFT,
            created_by=comandante_user.id,
        )
        db_session.add(existing)
        await db_session.flush()

        conflicts = await validate_single_shift(
            db_session, militar_user.id,
            start_dt=datetime(2026, 7, 2, 10, 0, tzinfo=timezone.utc),
            end_dt=datetime(2026, 7, 2, 18, 0, tzinfo=timezone.utc),
        )
        errors = [c for c in conflicts if c.severity == "error"]
        assert len(errors) >= 1
