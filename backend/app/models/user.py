"""
User, RefreshToken, and ActiveSession models.
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
    from app.models.notification import Notification
    from app.models.push_subscription import PushSubscription
    from app.models.shift import Shift
    from app.models.station import Station


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    COMANDANTE = "comandante"
    ADJUNTO = "adjunto"
    SECRETARIA = "secretaria"
    MILITAR = "militar"


class User(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "users"

    username: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, index=True
    )
    email: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    nip: Mapped[str] = mapped_column(
        String(20), unique=True, nullable=False, index=True,
        comment="Número de Identificação Pessoal"
    )
    numero_ordem: Mapped[str | None] = mapped_column(
        String(10), unique=True, nullable=True, index=True,
        comment="Número de ordem do militar (3-4 dígitos)"
    )
    role: Mapped[str] = mapped_column(
        Enum(UserRole, name="user_role", create_constraint=True, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        default=UserRole.MILITAR,
    )
    station_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("stations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Fixed shift type assignment (e.g. secretaria → SEC, inquéritos → INQ)
    default_shift_type_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("shift_types.id", ondelete="SET NULL"),
        nullable=True,
        comment="If set, user is always assigned this shift type (fixed role)",
    )

    # TOTP / 2FA
    totp_secret_encrypted: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="Fernet-encrypted TOTP secret"
    )
    totp_enabled: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )

    # Account status
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )

    # Account lockout
    failed_login_attempts: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False, server_default="0"
    )
    locked_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    station: Mapped[Optional["Station"]] = relationship(
        "Station", back_populates="users", lazy="selectin"
    )
    shifts: Mapped[List["Shift"]] = relationship(
        "Shift",
        back_populates="user",
        foreign_keys="Shift.user_id",
        lazy="noload",
    )
    notifications: Mapped[List["Notification"]] = relationship(
        "Notification", back_populates="user", lazy="noload"
    )
    refresh_tokens: Mapped[List["RefreshToken"]] = relationship(
        "RefreshToken", back_populates="user", lazy="noload",
        cascade="all, delete-orphan",
    )
    sessions: Mapped[List["ActiveSession"]] = relationship(
        "ActiveSession", back_populates="user", lazy="noload",
        cascade="all, delete-orphan",
    )
    push_subscriptions: Mapped[List["PushSubscription"]] = relationship(
        "PushSubscription", back_populates="user", lazy="noload",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<User {self.username} ({self.role.value})>"


class RefreshToken(UUIDMixin, Base):
    __tablename__ = "refresh_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token_hash: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    family_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="Token family for rotation — all tokens in a family share this ID",
    )
    is_revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="refresh_tokens")

    def __repr__(self) -> str:
        return f"<RefreshToken user={self.user_id} revoked={self.is_revoked}>"


class ActiveSession(UUIDMixin, Base):
    """Tracks active user sessions for Zero Trust verification."""
    __tablename__ = "active_sessions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    session_id: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
        unique=True,
        index=True,
        comment="Embedded in JWT — verified on every request",
    )
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="sessions")

    def __repr__(self) -> str:
        return f"<ActiveSession user={self.user_id} revoked={self.is_revoked}>"
