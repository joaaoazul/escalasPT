"""
Auth router — login, refresh, logout, TOTP.
"""

from __future__ import annotations

from fastapi import APIRouter, Cookie, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_user, get_db, require_role
from app.models.user import User, UserRole
from app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    LogoutResponse,
    MessageResponse,
    RefreshResponse,
    TOTPLoginRequest,
    TOTPSetupResponse,
    TOTPVerifyRequest,
    TOTPVerifyResponse,
)
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["Authentication"])


def _get_client_ip(request: Request) -> str:
    """Extract client IP, respecting X-Forwarded-For from Nginx."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@router.post("/login", response_model=LoginResponse)
async def login(
    data: LoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """
    Authenticate with username + password.
    If TOTP is enabled, returns requires_totp=true and no tokens.
    Otherwise, returns access_token and sets refresh_token as HttpOnly cookie.
    """
    ip = _get_client_ip(request)
    ua = request.headers.get("User-Agent", "")
    result = await auth_service.authenticate_user(db, data.username, data.password, ip, ua)

    if result.get("requires_totp"):
        return LoginResponse(
            access_token="",
            requires_totp=True,
        )

    # Set refresh token as HttpOnly Secure cookie
    response.set_cookie(
        key="refresh_token",
        value=result["refresh_token"],
        httponly=True,
        secure=True,
        samesite="strict",
        max_age=7 * 24 * 3600,  # 7 days
        path="/api/auth",
    )

    return LoginResponse(
        access_token=result["access_token"],
        requires_totp=False,
    )


@router.post("/login/totp", response_model=LoginResponse)
async def login_with_totp(
    data: TOTPLoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """Authenticate with username + password + TOTP code."""
    ip = _get_client_ip(request)
    ua = request.headers.get("User-Agent", "")
    result = await auth_service.authenticate_with_totp(
        db, data.username, data.password, data.totp_code, ip, ua,
    )

    response.set_cookie(
        key="refresh_token",
        value=result["refresh_token"],
        httponly=True,
        secure=True,
        samesite="strict",
        max_age=7 * 24 * 3600,
        path="/api/auth",
    )

    return LoginResponse(
        access_token=result["access_token"],
        requires_totp=False,
    )


@router.post("/refresh", response_model=RefreshResponse)
async def refresh_token(
    request: Request,
    response: Response,
    refresh_token: str | None = Cookie(None),
    db: AsyncSession = Depends(get_db),
):
    """
    Refresh the access token using the HttpOnly refresh cookie.
    Implements token rotation — old refresh token is invalidated.
    """
    if not refresh_token:
        from app.exceptions import AuthenticationError
        raise AuthenticationError("No refresh token provided")

    ip = _get_client_ip(request)
    result = await auth_service.refresh_access_token(db, refresh_token, ip)

    # Set new refresh token cookie
    response.set_cookie(
        key="refresh_token",
        value=result["refresh_token"],
        httponly=True,
        secure=True,
        samesite="strict",
        max_age=7 * 24 * 3600,
        path="/api/auth",
    )

    return RefreshResponse(access_token=result["access_token"])


@router.post("/logout", response_model=LogoutResponse)
async def logout(
    request: Request,
    response: Response,
    refresh_token: str | None = Cookie(None),
    db: AsyncSession = Depends(get_db),
):
    """Logout — revoke refresh token family and clear cookie."""
    if refresh_token:
        ip = _get_client_ip(request)
        await auth_service.logout_user(db, refresh_token, ip)

    response.delete_cookie(
        key="refresh_token",
        path="/api/auth",
    )

    return LogoutResponse()


@router.post("/totp/setup", response_model=TOTPSetupResponse)
async def setup_totp(
    current_user: User = Depends(require_role(UserRole.COMANDANTE)),
    db: AsyncSession = Depends(get_db),
):
    """
    Generate TOTP secret and provisioning URI.
    Only available for comandante role.
    """
    result = await auth_service.setup_totp(db, current_user)
    return TOTPSetupResponse(
        secret=result["secret"],
        uri=result["uri"],
    )


@router.post("/totp/verify", response_model=TOTPVerifyResponse)
async def verify_totp(
    data: TOTPVerifyRequest,
    current_user: User = Depends(require_role(UserRole.COMANDANTE)),
    db: AsyncSession = Depends(get_db),
):
    """
    Verify TOTP code and enable 2FA.
    Called after setup to confirm the user has configured their authenticator.
    """
    verified = await auth_service.verify_and_enable_totp(db, current_user, data.code)
    if verified:
        return TOTPVerifyResponse(
            verified=True,
            message="TOTP enabled successfully. You will need to provide a code on future logins.",
        )
    return TOTPVerifyResponse(
        verified=False,
        message="Invalid code. Please try again.",
    )


@router.get("/me", response_model=dict)
async def get_current_user_info(
    current_user: User = Depends(get_current_user),
):
    """Get current authenticated user info."""
    return {
        "id": str(current_user.id),
        "username": current_user.username,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "nip": current_user.nip,
        "role": current_user.role.value,
        "station_id": str(current_user.station_id) if current_user.station_id else None,
        "totp_enabled": current_user.totp_enabled,
        "is_active": current_user.is_active,
    }
