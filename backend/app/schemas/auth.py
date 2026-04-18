"""
Auth schemas — request/response models for authentication endpoints.
Never expose password_hash, totp_secret in responses.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=1, max_length=128)


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    requires_totp: bool = False


class TOTPLoginRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=1, max_length=128)
    totp_code: str = Field(..., min_length=6, max_length=6)


class RefreshResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TOTPSetupResponse(BaseModel):
    secret: str
    uri: str
    message: str = "Scan the QR code with your authenticator app, then verify with a code"


class TOTPVerifyRequest(BaseModel):
    code: str = Field(..., min_length=6, max_length=6)


class TOTPVerifyResponse(BaseModel):
    verified: bool
    message: str


class LogoutResponse(BaseModel):
    message: str = "Successfully logged out"


class MessageResponse(BaseModel):
    message: str
