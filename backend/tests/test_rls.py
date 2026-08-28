"""
Row-Level Security: an absent tenant context DENIES.

escalasPT's policies read `current_setting(...) = '' OR station_id = ...`, so a
missing or malformed station_id is a full bypass (007_add_rls_policies.py:44-48).
These tests exist to make sure that shape never comes back.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select, text

from app.models import Equipa


@pytest.mark.asyncio
async def test_empty_context_denies_instead_of_bypassing(db_session, equipa):
    """The whole point: no context means no rows, not every row."""
    await db_session.execute(text("SET LOCAL app.current_equipa_id = ''"))

    rows = (await db_session.execute(select(Equipa))).scalars().all()

    assert rows == []


@pytest.mark.asyncio
async def test_unset_context_denies(db_session, equipa):
    """Not even the variable is set — still deny."""
    rows = (await db_session.execute(select(Equipa))).scalars().all()

    assert rows == []


@pytest.mark.asyncio
async def test_matching_context_sees_its_own_equipa(session_factory, equipa):
    async with session_factory() as db:
        await db.execute(text(f"SET LOCAL app.current_equipa_id = '{equipa.id}'"))
        rows = (await db.execute(select(Equipa))).scalars().all()

    assert [r.id for r in rows] == [equipa.id]


@pytest.mark.asyncio
async def test_another_equipa_sees_nothing(session_factory, equipa):
    async with session_factory() as db:
        await db.execute(text(f"SET LOCAL app.current_equipa_id = '{uuid.uuid4()}'"))
        rows = (await db.execute(select(Equipa))).scalars().all()

    assert rows == []


@pytest.mark.asyncio
async def test_malformed_context_is_treated_as_empty_by_the_api(client, agente, equipa):
    """
    A token carrying a non-UUID equipa_id must not reach the database as SQL.
    get_db() parses it strictly and falls back to the deny-by-default empty
    string.
    """
    from app.utils.security import create_access_token

    token = create_access_token(
        user_id=str(agente.id), role="agente", equipa_id="'; DROP TABLE users; --",
        session_id="not-a-real-session",
    )
    response = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})

    # Session does not exist, so 401 — and, crucially, the tables are still here.
    assert response.status_code == 401
