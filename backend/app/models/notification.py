"""
Notification model.
"""

from __future__ import annotations

import enum
import uuid

from sqlalchemy import Boolean, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from app.models.station import Station
    from app.models.user import User


class NotificationType(str, enum.Enum):
    SHIFT_PUBLISHED = "shift_published"
    SHIFT_UPDATED = "shift_updated"
    SHIFT_CANCELLED = "shift_cancelled"
    SWAP_REQUESTED = "swap_requested"
    SWAP_ACCEPTED = "swap_accepted"
    SWAP_APPROVED = "swap_approved"
    SWAP_REJECTED = "swap_rejected"
    GENERAL = "general"


class Notification(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "notifications"

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
    type: Mapped[str] = mapped_column(
        Enum(NotificationType, name="notification_type", create_constraint=True, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="notifications")
    station: Mapped["Station"] = relationship("Station", back_populates="notifications")

    def __repr__(self) -> str:
        return f"<Notification {self.type.value} user={self.user_id} read={self.is_read}>"
