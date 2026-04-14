"""
ShiftType schemas.
"""

from __future__ import annotations

import uuid
from datetime import datetime, time
from typing import Optional

from pydantic import BaseModel, Field


class ShiftTypeBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    code: str = Field(..., min_length=2, max_length=20)
    description: Optional[str] = Field(None, max_length=500)
    start_time: time
    end_time: time
    color: str = Field(default="#3B82F6", pattern=r"^#[0-9A-Fa-f]{6}$")
    min_staff: int = Field(default=1, ge=0, le=20)
    is_absence: bool = False
    fixed_slots: bool = False


class ShiftTypeCreate(ShiftTypeBase):
    pass


class ShiftTypeUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    code: Optional[str] = Field(None, min_length=2, max_length=20)
    description: Optional[str] = Field(None, max_length=500)
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    color: Optional[str] = Field(None, pattern=r"^#[0-9A-Fa-f]{6}$")
    min_staff: Optional[int] = Field(None, ge=0, le=20)
    is_absence: Optional[bool] = None
    fixed_slots: Optional[bool] = None
    is_active: Optional[bool] = None


class ShiftTypeResponse(BaseModel):
    id: uuid.UUID
    station_id: uuid.UUID
    name: str
    code: str
    description: Optional[str]
    start_time: time
    end_time: time
    color: str
    min_staff: int
    is_absence: bool
    fixed_slots: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ShiftTypeListResponse(BaseModel):
    shift_types: list[ShiftTypeResponse]
    total: int
