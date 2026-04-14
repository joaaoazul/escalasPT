"""
User schemas — input/output models.
Sensitive fields (password_hash, totp_secret) are NEVER included in responses.
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.models.user import UserRole

# OWASP ASVS V5 — strip HTML tags from user-submitted text fields.
_HTML_TAG_RE = re.compile(r"<[^>]+>")


def _sanitize_text(v: str | None) -> str | None:
    if v is None:
        return None
    return _HTML_TAG_RE.sub("", v).strip()


class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    full_name: str = Field(..., min_length=2, max_length=200)
    nip: str = Field(..., min_length=3, max_length=20)
    numero_ordem: Optional[str] = Field(None, min_length=3, max_length=10)
    phone: Optional[str] = Field(None, max_length=20)

    _sanitize_full_name = field_validator("full_name", mode="before")(_sanitize_text)


class UserCreate(UserBase):
    password: str = Field(..., min_length=12, max_length=128)
    role: UserRole = UserRole.MILITAR
    station_id: Optional[uuid.UUID] = None


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = Field(None, min_length=2, max_length=200)
    numero_ordem: Optional[str] = Field(None, min_length=3, max_length=10)
    phone: Optional[str] = Field(None, max_length=20)
    role: Optional[UserRole] = None
    station_id: Optional[uuid.UUID] = None
    default_shift_type_id: Optional[uuid.UUID] = None
    is_active: Optional[bool] = None


class UserResponse(BaseModel):
    id: uuid.UUID
    username: str
    email: str
    full_name: str
    nip: str
    numero_ordem: Optional[str] = None
    role: UserRole
    station_id: Optional[uuid.UUID]
    phone: Optional[str]
    default_shift_type_id: Optional[uuid.UUID] = None
    totp_enabled: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class UserListResponse(BaseModel):
    users: list[UserResponse]
    total: int
