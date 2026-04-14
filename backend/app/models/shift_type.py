"""
ShiftType model — reusable shift templates per station.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, List

from sqlalchemy import Boolean, ForeignKey, Integer, String, Time
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.shift import Shift
    from app.models.station import Station

import datetime as dt


class ShiftType(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "shift_types"

    station_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("stations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(
        String(100), nullable=False,
        comment="e.g. Patrulha, Atendimento, Ocorrências"
    )
    code: Mapped[str] = mapped_column(
        String(20), nullable=False,
        comment="Short code e.g. PAT, ATE, OCO"
    )
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    start_time: Mapped[dt.time] = mapped_column(Time, nullable=False)
    end_time: Mapped[dt.time] = mapped_column(Time, nullable=False)
    color: Mapped[str] = mapped_column(
        String(7), nullable=False, default="#3B82F6",
        comment="Hex color for calendar display"
    )
    min_staff: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1,
        comment="Minimum staff required for this shift type (e.g. 2 for patrol)"
    )
    is_absence: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False,
        comment="True for absence types: FER, CONV, MF, DIL, LIC"
    )
    fixed_slots: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False,
        comment="True for types with fixed 8h daily slots: AT, OC"
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    station: Mapped["Station"] = relationship("Station", back_populates="shift_types")
    shifts: Mapped[List["Shift"]] = relationship("Shift", back_populates="shift_type", lazy="noload")

    def __repr__(self) -> str:
        return f"<ShiftType {self.code}: {self.name} ({self.start_time}-{self.end_time})>"
