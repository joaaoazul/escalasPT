"""
Smoke tests for PDF report generation — confirm they don't 500 and
respect role gating, without asserting on PDF internals.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.models.user import User
from tests.conftest import make_auth_header

pytestmark = pytest.mark.asyncio


class TestScheduleReport:
    async def test_militar_cannot_export_schedule(
        self, client: AsyncClient, militar_user: User,
    ):
        headers = make_auth_header(militar_user)
        resp = await client.get(
            "/api/reports/schedule", headers=headers,
            params={"year": 2026, "month": 6},
        )
        assert resp.status_code == 403

    async def test_comandante_exports_schedule_pdf(
        self, client: AsyncClient, comandante_user: User,
    ):
        headers = make_auth_header(comandante_user)
        resp = await client.get(
            "/api/reports/schedule", headers=headers,
            params={"year": 2026, "month": 6},
        )
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/pdf"
        assert len(resp.content) > 0


class TestSwapsReport:
    async def test_militar_cannot_export_swaps_report(
        self, client: AsyncClient, militar_user: User,
    ):
        headers = make_auth_header(militar_user)
        resp = await client.get("/api/reports/swaps", headers=headers)
        assert resp.status_code == 403

    async def test_comandante_exports_swaps_report_empty_range(
        self, client: AsyncClient, comandante_user: User,
    ):
        """No approved swaps yet — should still return a valid empty-table PDF, not 500."""
        headers = make_auth_header(comandante_user)
        resp = await client.get("/api/reports/swaps", headers=headers)
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/pdf"
