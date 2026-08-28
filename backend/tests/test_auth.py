"""
Authentication: login, lockout, refresh rotation, theft detection, logout.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select, text

from app.config import get_settings
from app.models import ActiveSession, RefreshToken
from tests.conftest import TEST_PASSWORD

settings = get_settings()


async def _login(client, username="agente", password=TEST_PASSWORD):
    return await client.post("/api/auth/login", json={"username": username, "password": password})


@pytest.mark.asyncio
async def test_login_returns_access_token_and_refresh_cookie(client, agente):
    response = await _login(client)

    assert response.status_code == 200
    body = response.json()
    assert body["access_token"]
    assert body["requires_totp"] is False
    assert "refresh_token" in response.cookies


@pytest.mark.asyncio
async def test_login_with_wrong_password_is_rejected(client, agente):
    response = await _login(client, password="errada-mas-comprida-1!")

    assert response.status_code == 401
    assert "access_token" not in response.json()


@pytest.mark.asyncio
async def test_unknown_user_and_wrong_password_look_identical(client, agente):
    """No user enumeration: same status, same body."""
    unknown = await _login(client, username="ninguem", password="Qualquer-Coisa-1!")
    wrong = await _login(client, password="Qualquer-Coisa-1!")

    assert unknown.status_code == wrong.status_code == 401
    assert unknown.json()["detail"] == wrong.json()["detail"]


@pytest.mark.asyncio
async def test_account_locks_after_repeated_failures(client, agente):
    for _ in range(settings.ACCOUNT_LOCKOUT_ATTEMPTS):
        await _login(client, password="errada-mas-comprida-1!")

    # Correct password, but the account is now locked.
    response = await _login(client)
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_me_requires_a_valid_token(client, agente):
    assert (await client.get("/api/auth/me")).status_code == 401

    token = (await _login(client)).json()["access_token"]
    response = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    body = response.json()
    assert body["username"] == "agente"
    assert body["role"] == "agente"
    assert "password_hash" not in body
    assert "totp_secret_encrypted" not in body


@pytest.mark.asyncio
async def test_me_carries_the_equipa_once_rls_context_exists(client, agente, equipa):
    token = (await _login(client)).json()["access_token"]
    body = (
        await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    ).json()

    assert body["equipa_id"] == str(equipa.id)
    assert body["equipa"]["codigo"] == "TST"


@pytest.mark.asyncio
async def test_refresh_rotates_the_token(client, agente):
    login = await _login(client)
    first_cookie = login.cookies["refresh_token"]

    refreshed = await client.post("/api/auth/refresh", cookies={"refresh_token": first_cookie})

    assert refreshed.status_code == 200
    assert refreshed.json()["access_token"]
    assert refreshed.cookies["refresh_token"] != first_cookie


@pytest.mark.asyncio
async def test_reusing_a_spent_refresh_token_kills_the_family(client, agente, session_factory):
    login = await _login(client)
    spent = login.cookies["refresh_token"]

    await client.post("/api/auth/refresh", cookies={"refresh_token": spent})

    # Replaying the spent token is the signature of a stolen cookie.
    replay = await client.post("/api/auth/refresh", cookies={"refresh_token": spent})
    assert replay.status_code == 401

    async with session_factory() as db:
        tokens = (await db.execute(select(RefreshToken))).scalars().all()
        assert tokens, "expected refresh tokens to exist"
        assert all(t.is_revoked for t in tokens), "whole family should be revoked"

        # And the sessions with them — a revoked family that leaves a live
        # access token behind buys the thief 15 more minutes.
        sessions = (await db.execute(select(ActiveSession))).scalars().all()
        assert all(s.is_revoked for s in sessions)


@pytest.mark.asyncio
async def test_theft_detection_is_audited(client, agente, session_factory):
    login = await _login(client)
    spent = login.cookies["refresh_token"]
    await client.post("/api/auth/refresh", cookies={"refresh_token": spent})
    await client.post("/api/auth/refresh", cookies={"refresh_token": spent})

    async with session_factory() as db:
        actions = (
            await db.execute(text("SELECT action FROM audit_logs ORDER BY created_at"))
        ).scalars().all()

    assert "token_theft_reuse" in actions


@pytest.mark.asyncio
async def test_logout_revokes_the_session(client, agente, session_factory):
    login = await _login(client)
    token = login.json()["access_token"]
    cookie = login.cookies["refresh_token"]

    await client.post("/api/auth/logout", cookies={"refresh_token": cookie})

    # The access token is still cryptographically valid, but its session is gone.
    response = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401

    async with session_factory() as db:
        sessions = (await db.execute(select(ActiveSession))).scalars().all()
        assert all(s.is_revoked for s in sessions)


@pytest.mark.asyncio
async def test_login_is_rate_limited(client, agente):
    """Brute force is capped per IP — the limiter is on in production."""
    from app.routers import auth as auth_router

    auth_router.limiter.enabled = True
    try:
        statuses = []
        for _ in range(int(settings.RATE_LIMIT_LOGIN.split("/")[0]) + 1):
            statuses.append((await _login(client, password="errada-mas-comprida-1!")).status_code)
    finally:
        auth_router.limiter.enabled = False
        auth_router.limiter.reset()

    assert statuses[-1] == 429
