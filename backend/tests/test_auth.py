"""
Tests for authentication endpoints.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.models.user import User
from tests.conftest import make_auth_header

pytestmark = pytest.mark.asyncio


class TestLogin:
    """Test login flows."""

    async def test_login_success(self, client: AsyncClient, comandante_user: User):
        """Successful login returns an access token."""
        response = await client.post("/api/auth/login", json={
            "username": "test_comandante",
            "password": "TestCmd123!",
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        # Check refresh cookie
        assert "refresh_token" in response.cookies

    async def test_login_wrong_password(self, client: AsyncClient, comandante_user: User):
        """Wrong password returns 401."""
        response = await client.post("/api/auth/login", json={
            "username": "test_comandante",
            "password": "WrongPassword!",
        })
        assert response.status_code == 401
        assert response.json()["error"] == "AUTH_ERROR"

    async def test_login_nonexistent_user(self, client: AsyncClient):
        """Non-existent user returns 401."""
        response = await client.post("/api/auth/login", json={
            "username": "nobody",
            "password": "whatever",
        })
        assert response.status_code == 401

    async def test_login_inactive_user(self, client: AsyncClient, db_session, militar_user: User):
        """Inactive user cannot login."""
        militar_user.is_active = False
        db_session.add(militar_user)
        await db_session.flush()

        response = await client.post("/api/auth/login", json={
            "username": "test_militar",
            "password": "TestMil123!",
        })
        assert response.status_code == 401
        assert "deactivated" in response.json()["detail"].lower()


class TestRefreshToken:
    """Test refresh token rotation."""

    async def test_refresh_success(self, client: AsyncClient, militar_user: User):
        """Refresh returns a new access token."""
        # First login
        login_resp = await client.post("/api/auth/login", json={
            "username": "test_militar",
            "password": "TestMil123!",
        })
        assert login_resp.status_code == 200

        # Then refresh (cookie should be set automatically by httpx)
        refresh_resp = await client.post("/api/auth/refresh")
        assert refresh_resp.status_code == 200
        assert "access_token" in refresh_resp.json()

    async def test_refresh_without_cookie(self, client: AsyncClient):
        """Refresh without cookie returns 401."""
        response = await client.post("/api/auth/refresh")
        assert response.status_code == 401


class TestLogout:
    """Test logout."""

    async def test_logout_success(self, client: AsyncClient, militar_user: User):
        """Logout clears the refresh cookie."""
        # Login first
        await client.post("/api/auth/login", json={
            "username": "test_militar",
            "password": "TestMil123!",
        })

        response = await client.post("/api/auth/logout")
        assert response.status_code == 200
        assert response.json()["message"] == "Successfully logged out"

    async def test_logout_without_session(self, client: AsyncClient):
        """Logout without active session still succeeds."""
        response = await client.post("/api/auth/logout")
        assert response.status_code == 200


class TestCurrentUser:
    """Test /auth/me endpoint."""

    async def test_get_current_user(self, client: AsyncClient, militar_user: User):
        """Authenticated user can access their info."""
        headers = make_auth_header(militar_user)
        response = await client.get("/api/auth/me", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "test_militar"
        assert data["role"] == "militar"
        # Sensitive fields should not be present
        assert "password_hash" not in data
        assert "totp_secret" not in data

    async def test_current_user_no_auth(self, client: AsyncClient):
        """Unauthenticated request returns 401."""
        response = await client.get("/api/auth/me")
        assert response.status_code == 401


class TestRBAC:
    """Test role-based access control."""

    async def test_militar_cannot_create_user(self, client: AsyncClient, militar_user: User):
        """Militar cannot access admin endpoints."""
        headers = make_auth_header(militar_user)
        response = await client.post("/api/users/", headers=headers, json={
            "username": "new_user",
            "email": "new@gnr.pt",
            "password": "NewPass123!",
            "full_name": "New User",
            "nip": "NEW001",
        })
        assert response.status_code == 403

    async def test_admin_can_create_user(self, client: AsyncClient, admin_user: User):
        """Admin can create users."""
        headers = make_auth_header(admin_user)
        response = await client.post("/api/users/", headers=headers, json={
            "username": "created_by_admin",
            "email": "created@gnr.pt",
            "password": "Created123!",
            "full_name": "Created User",
            "nip": "CRT001",
        })
        assert response.status_code == 201
        assert response.json()["username"] == "created_by_admin"

    async def test_militar_cannot_create_shift(self, client: AsyncClient, militar_user: User):
        """Militar cannot create shifts (read-only)."""
        headers = make_auth_header(militar_user)
        response = await client.post("/api/shifts/", headers=headers, json={
            "user_id": str(militar_user.id),
            "date": "2026-04-15",
            "start_datetime": "2026-04-15T08:00:00Z",
            "end_datetime": "2026-04-15T16:00:00Z",
        })
        assert response.status_code == 403

    async def test_admin_cannot_access_shifts(self, client: AsyncClient, admin_user: User):
        """Admin role cannot view shifts."""
        headers = make_auth_header(admin_user)
        response = await client.get("/api/shifts/", headers=headers)
        assert response.status_code == 403


class TestTOTP:
    """Test TOTP setup and verification."""

    async def test_totp_setup_comandante(self, client: AsyncClient, comandante_user: User):
        """Comandante can setup TOTP."""
        headers = make_auth_header(comandante_user)
        response = await client.post("/api/auth/totp/setup", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "secret" in data
        assert "uri" in data
        assert "otpauth://" in data["uri"]

    async def test_totp_setup_militar_denied(self, client: AsyncClient, militar_user: User):
        """Militar cannot setup TOTP."""
        headers = make_auth_header(militar_user)
        response = await client.post("/api/auth/totp/setup", headers=headers)
        assert response.status_code == 403
