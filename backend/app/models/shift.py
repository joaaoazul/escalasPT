"""
Shift and ShiftSwapRequest models.
"""

from __future__ import annotations

import enum
import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    Date,
    DateTime,
    Enum,
    ForeignKey,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.shift_type import ShiftType
    from app.models.station import Station
    from app.models.user import User


class ShiftStatus(str, enum.Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    CANCELLED = "cancelled"


class Shift(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "shifts"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    station_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("stations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    shift_type_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("shift_types.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    start_datetime: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    end_datetime: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    status: Mapped[str] = mapped_column(
        Enum(ShiftStatus, name="shift_status", create_constraint=True, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        default=ShiftStatus.DRAFT,
        index=True,
    )
    notes: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="Notas do comandante: giro, indicações, tarefas específicas"
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Commander who created this shift",
    )
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    user: Mapped["User"] = relationship(
        "User", back_populates="shifts", foreign_keys=[user_id], lazy="selectin"
    )
    station: Mapped["Station"] = relationship(
        "Station", back_populates="shifts", lazy="selectin"
    )
    shift_type: Mapped[Optional["ShiftType"]] = relationship(
        "ShiftType", back_populates="shifts", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<Shift {self.date} {self.start_datetime}-{self.end_datetime} user={self.user_id} status={self.status.value}>"


class SwapStatus(str, enum.Enum):
    PENDING_TARGET = "pending_target"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class ShiftSwapRequest(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "shift_swap_requests"

    requester_shift_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("shifts.id", ondelete="CASCADE"),
        nullable=False,
    )
    target_shift_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("shifts.id", ondelete="CASCADE"),
        nullable=False,
    )
    requester_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    target_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        Enum(SwapStatus, name="swap_status", create_constraint=True, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        default=SwapStatus.PENDING_TARGET,
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    responded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    requester_shift: Mapped["Shift"] = relationship(
        "Shift", foreign_keys=[requester_shift_id], lazy="selectin"
    )
    target_shift: Mapped["Shift"] = relationship(
        "Shift", foreign_keys=[target_shift_id], lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<ShiftSwap {self.requester_id} <-> {self.target_id} status={self.status.value}>"
