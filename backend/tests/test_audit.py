"""
Audit log: written on the paths that matter, sanitised, and append-only.

The append-only guarantee only holds because the application connects as a
limited role. escalasPT revokes UPDATE/DELETE from `gnr_app` but connects as the
table owner, so the revoke never applies. That test runs here whenever
TEST_APP_ROLE_URL points at the limited role (CI always sets it).
"""

from __future__ import annotations

import pytest
from sqlalchemy import text

from tests.conftest import RUNS_AS_LIMITED_ROLE, TEST_PASSWORD


@pytest.mark.asyncio
async def test_successful_login_is_audited(client, agente, session_factory):
    await client.post(
        "/api/auth/login", json={"username": "agente", "password": TEST_PASSWORD}
    )

    async with session_factory() as db:
        rows = (
            await db.execute(text("SELECT action, resource_type FROM audit_logs"))
        ).all()

    assert ("login_success", "user") in [(r[0], r[1]) for r in rows]


@pytest.mark.asyncio
async def test_audit_entries_never_carry_credentials(client, agente, session_factory):
    await client.post(
        "/api/auth/login", json={"username": "agente", "password": TEST_PASSWORD}
    )

    async with session_factory() as db:
        payloads = (
            await db.execute(
                text("SELECT coalesce(old_data::text, '') || coalesce(new_data::text, '') FROM audit_logs")
            )
        ).scalars().all()

    blob = " ".join(payloads)
    assert TEST_PASSWORD not in blob
    assert "password_hash" not in blob


@pytest.mark.skipif(
    not RUNS_AS_LIMITED_ROLE,
    reason="needs MIGRATION_DATABASE_URL (owner) separate from TEST_DATABASE_URL (app role)",
)
@pytest.mark.asyncio
async def test_audit_log_is_append_only_for_the_app_role(client, agente, test_engine):
    """
    UPDATE and DELETE must fail for the role the application actually uses.

    escalasPT revokes them from `gnr_app` (001_initial.py:220) but connects as
    the table owner, so the revoke never applies and the audit trail is editable
    in production. This test is the difference.
    """
    await client.post(
        "/api/auth/login", json={"username": "agente", "password": TEST_PASSWORD}
    )

    async with test_engine.begin() as conn:
        assert (
            await conn.execute(text("SELECT count(*) FROM audit_logs"))
        ).scalar(), "expected the login above to have written an audit row"

    with pytest.raises(Exception) as update_error:
        async with test_engine.begin() as conn:
            await conn.execute(text("UPDATE audit_logs SET action = 'tampered'"))
    assert "permission denied" in str(update_error.value).lower()

    with pytest.raises(Exception) as delete_error:
        async with test_engine.begin() as conn:
            await conn.execute(text("DELETE FROM audit_logs"))
    assert "permission denied" in str(delete_error.value).lower()
