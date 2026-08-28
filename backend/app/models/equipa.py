"""
Equipa — the isolation unit (posto, secção, patrulha).
Every RLS policy in this application keys off equipa_id.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, List

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.user import User


class Equipa(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "equipas"

    nome: Mapped[str] = mapped_column(String(120), nullable=False)
    codigo: Mapped[str] = mapped_column(
        String(20), unique=True, nullable=False, index=True,
        comment="Short code used in listings and PDF headers",
    )
    unidade: Mapped[str | None] = mapped_column(
        String(120), nullable=True, comment="Destacamento / Comando Territorial"
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    users: Mapped[List["User"]] = relationship("User", back_populates="equipa", lazy="noload")

    def __repr__(self) -> str:
        return f"<Equipa {self.codigo}>"
