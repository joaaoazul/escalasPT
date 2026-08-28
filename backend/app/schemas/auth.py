"""
Auth schemas. Never expose password_hash or TOTP secrets.
"""

from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.models.user import UserRole


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=1, max_length=128)


class TOTPLoginRequest(LoginRequest):
    totp_code: str = Field(..., min_length=6, max_length=6)


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    requires_totp: bool = False


class RefreshResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class EquipaSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    nome: str
    codigo: str


class MeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    username: str
    nome: str
    nip: str
    email: str
    role: UserRole
    equipa_id: uuid.UUID | None = None
    equipa: EquipaSummary | None = None
    totp_enabled: bool


class TOTPSetupResponse(BaseModel):
    secret: str
    uri: str


class TOTPVerifyRequest(BaseModel):
    code: str = Field(..., min_length=6, max_length=6)


class TOTPVerifyResponse(BaseModel):
    verified: bool
    message: str


class MessageResponse(BaseModel):
    message: str
