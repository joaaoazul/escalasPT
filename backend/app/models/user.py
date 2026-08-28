"""
User, RefreshToken and ActiveSession.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.equipa import Equipa


class UserRole(str, enum.Enum):
    AGENTE = "agente"
    CHEFE_EQUIPA = "chefe_equipa"
    ADMIN = "admin"


class User(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "users"

    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    nome: Mapped[str] = mapped_column(String(200), nullable=False)
    nip: Mapped[str] = mapped_column(
        String(7), unique=True, nullable=False, index=True,
        comment="NIM — Número de Identificação Militar",
    )
    role: Mapped[str] = mapped_column(
        Enum(UserRole, name="user_role", create_constraint=True,
             values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        default=UserRole.AGENTE,
    )
    equipa_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("equipas.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # TOTP / 2FA
    totp_secret_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    totp_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Lockout
    failed_login_attempts: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False, server_default="0"
    )
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    equipa: Mapped[Optional["Equipa"]] = relationship(
        "Equipa", back_populates="users", lazy="selectin"
    )
    refresh_tokens: Mapped[List["RefreshToken"]] = relationship(
        "RefreshToken", back_populates="user", lazy="noload", cascade="all, delete-orphan"
    )
    sessions: Mapped[List["ActiveSession"]] = relationship(
        "ActiveSession", back_populates="user", lazy="noload", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<User {self.username} ({self.role})>"


class RefreshToken(UUIDMixin, Base):
    __tablename__ = "refresh_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    family_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True,
        comment="Rotation family — reuse of any member revokes the whole family",
    )
    is_revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped["User"] = relationship("User", back_populates="refresh_tokens")


class ActiveSession(UUIDMixin, Base):
    """Session registry — the JWT's `sid` is checked against this on every request."""

    __tablename__ = "active_sessions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    session_id: Mapped[str] = mapped_column(String(36), nullable=False, unique=True, index=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped["User"] = relationship("User", back_populates="sessions")
