"""
AuditLog model — append-only, immutable audit trail.
Protected by SQL policy: no DELETE or UPDATE for app user.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDMixin


class AuditLog(UUIDMixin, Base):
    __tablename__ = "audit_logs"

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="User who performed the action (null for system actions)",
    )
    action: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True,
        comment="Action verb: create, update, delete, login, publish, etc.",
    )
    resource_type: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True,
        comment="Model name: shift, user, station, etc.",
    )
    resource_id: Mapped[str | None] = mapped_column(
        String(36), nullable=True,
        comment="UUID of the affected resource",
    )
    old_data: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True,
        comment="Previous state (for updates)",
    )
    new_data: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True,
        comment="New state after change",
    )
    ip_address: Mapped[str | None] = mapped_column(
        String(45), nullable=True,
        comment="Client IP address",
    )
    user_agent: Mapped[str | None] = mapped_column(
        String(500), nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    def __repr__(self) -> str:
        return f"<AuditLog {self.action} {self.resource_type} by={self.user_id}>"
