"""
Station schemas.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class StationBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=200)
    code: str = Field(..., min_length=2, max_length=20)
    comando_territorial: str = Field(
        ..., min_length=2, max_length=200,
        description="Comando Territorial (e.g. CT Porto)",
    )
    destacamento: str = Field(
        ..., min_length=2, max_length=200,
        description="Destacamento Territorial (e.g. DT Vila Nova de Gaia)",
    )
    address: Optional[str] = Field(None, max_length=500)
    phone: Optional[str] = Field(None, max_length=20)


class StationCreate(StationBase):
    pass


class StationUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=200)
    code: Optional[str] = Field(None, min_length=2, max_length=20)
    comando_territorial: Optional[str] = Field(None, min_length=2, max_length=200)
    destacamento: Optional[str] = Field(None, min_length=2, max_length=200)
    address: Optional[str] = Field(None, max_length=500)
    phone: Optional[str] = Field(None, max_length=20)
    is_active: Optional[bool] = None


class StationResponse(BaseModel):
    id: uuid.UUID
    name: str
    code: str
    comando_territorial: str
    destacamento: str
    address: Optional[str]
    phone: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class StationListResponse(BaseModel):
    stations: list[StationResponse]
    total: int
