"""
Station model — represents a GNR post/station.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, List

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.notification import Notification
    from app.models.shift import Shift
    from app.models.shift_type import ShiftType
    from app.models.user import User


class Station(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "stations"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    # Relationships
    users: Mapped[List["User"]] = relationship(
        "User", back_populates="station", lazy="noload"
    )
    shift_types: Mapped[List["ShiftType"]] = relationship(
        "ShiftType", back_populates="station", lazy="noload"
    )
    shifts: Mapped[List["Shift"]] = relationship(
        "Shift", back_populates="station", lazy="noload"
    )
    notifications: Mapped[List["Notification"]] = relationship(
        "Notification", back_populates="station", lazy="noload"
    )

    def __repr__(self) -> str:
        return f"<Station {self.code}: {self.name}>"
