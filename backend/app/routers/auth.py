"""
Auth router — login, TOTP, refresh, logout, me.

The refresh token lives in an HttpOnly cookie scoped to /api/auth; the access
token is returned in the body and kept in memory by the SPA only.
"""

# No `from __future__ import annotations` here on purpose: FastAPI resolves
# Body/Query models from the real annotations, and PEP 563 strings break it.
from fastapi import APIRouter, Body, Cookie, Depends, Request, Response
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.dependencies import get_client_ip, get_current_user, get_db
from app.exceptions import AuthenticationError
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    MeResponse,
    MessageResponse,
    RefreshResponse,
    TOTPLoginRequest,
    TOTPSetupResponse,
    TOTPVerifyRequest,
    TOTPVerifyResponse,
)
from app.services import auth_service

settings = get_settings()

router = APIRouter(prefix="/auth", tags=["Autenticação"])
limiter = Limiter(key_func=get_remote_address)

REFRESH_COOKIE = "refresh_token"
REFRESH_COOKIE_PATH = "/api/auth"


def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=REFRESH_COOKIE,
        value=token,
        httponly=True,
        secure=True,  # tailscale serve terminates TLS — always a secure context
        samesite="strict",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600,
        path=REFRESH_COOKIE_PATH,
    )


@router.post("/login", response_model=LoginResponse)
@limiter.limit(settings.RATE_LIMIT_LOGIN)
async def login(
    request: Request,
    response: Response,
    data: LoginRequest = Body(...),
    db: AsyncSession = Depends(get_db),
):
    """Password login. Returns requires_totp=true when 2FA is enabled."""
    result = await auth_service.authenticate_user(
        db, data.username, data.password, get_client_ip(request),
        request.headers.get("User-Agent", ""),
    )

    if result.get("requires_totp"):
        return LoginResponse(access_token="", requires_totp=True)  # nosec B106 — no token is issued until TOTP passes

    _set_refresh_cookie(response, result["refresh_token"])
    return LoginResponse(access_token=result["access_token"])


@router.post("/login/totp", response_model=LoginResponse)
@limiter.limit(settings.RATE_LIMIT_LOGIN)
async def login_with_totp(
    request: Request,
    response: Response,
    data: TOTPLoginRequest = Body(...),
    db: AsyncSession = Depends(get_db),
):
    """Password + TOTP login."""
    result = await auth_service.authenticate_with_totp(
        db, data.username, data.password, data.totp_code, get_client_ip(request),
        request.headers.get("User-Agent", ""),
    )
    _set_refresh_cookie(response, result["refresh_token"])
    return LoginResponse(access_token=result["access_token"])


@router.post("/refresh", response_model=RefreshResponse)
@limiter.limit("30/minute")
async def refresh(
    request: Request,
    response: Response,
    refresh_token: str | None = Cookie(None),
    db: AsyncSession = Depends(get_db),
):
    """Rotate the refresh cookie and issue a new access token."""
    if not refresh_token:
        raise AuthenticationError("Sem refresh token")

    result = await auth_service.refresh_access_token(
        db, refresh_token, get_client_ip(request)
    )
    _set_refresh_cookie(response, result["refresh_token"])
    return RefreshResponse(access_token=result["access_token"])


@router.post("/logout", response_model=MessageResponse)
async def logout(
    request: Request,
    response: Response,
    refresh_token: str | None = Cookie(None),
    db: AsyncSession = Depends(get_db),
):
    """Revoke the token family and the session, and clear the cookie."""
    if refresh_token:
        await auth_service.logout_user(db, refresh_token, get_client_ip(request))
    response.delete_cookie(REFRESH_COOKIE, path=REFRESH_COOKIE_PATH)
    return MessageResponse(message="Sessão terminada")


@router.get("/me", response_model=MeResponse)
async def me(current_user: User = Depends(get_current_user)):
    """The signed-in user, for the SPA to render its shell."""
    return current_user


@router.post("/totp/setup", response_model=TOTPSetupResponse)
async def totp_setup(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Start 2FA enrolment — the secret is stored encrypted but not yet enabled."""
    return await auth_service.setup_totp(db, current_user)


@router.post("/totp/verify", response_model=TOTPVerifyResponse)
async def totp_verify(
    data: TOTPVerifyRequest = Body(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Confirm a code and switch 2FA on."""
    ok = await auth_service.verify_and_enable_totp(db, current_user, data.code)
    return TOTPVerifyResponse(
        verified=ok,
        message="2FA activada" if ok else "Código inválido",
    )
