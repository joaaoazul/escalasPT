"""
Shift and ShiftSwapRequest schemas.
"""

from __future__ import annotations

import re
import uuid
from datetime import date, datetime, time
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.shift import ShiftStatus, SwapStatus

# OWASP ASVS V5 — strip HTML tags from user-submitted text fields.
_HTML_TAG_RE = re.compile(r"<[^>]+>")


def _sanitize_text(v: str | None) -> str | None:
    if v is None:
        return None
    return _HTML_TAG_RE.sub("", v).strip()


class ShiftCreate(BaseModel):
    user_id: uuid.UUID
    shift_type_id: Optional[uuid.UUID] = None
    date: date
    start_datetime: datetime
    end_datetime: datetime
    notes: Optional[str] = Field(None, max_length=2000)
    location: Optional[str] = Field(None, max_length=300)
    grat_type: Optional[str] = Field(None, max_length=100)

    _sanitize_notes = field_validator("notes", mode="before")(_sanitize_text)
    _sanitize_location = field_validator("location", mode="before")(_sanitize_text)
    _sanitize_grat_type = field_validator("grat_type", mode="before")(_sanitize_text)

    @model_validator(mode="after")
    def validate_times(self):
        if self.start_datetime and self.end_datetime:
            if self.end_datetime <= self.start_datetime:
                # Allow overnight shifts only when end is on the next calendar day
                if self.end_datetime.date() <= self.start_datetime.date():
                    raise ValueError(
                        "end_datetime must be after start_datetime "
                        "(for overnight shifts end must be on the following day)"
                    )
        return self


class ShiftUpdate(BaseModel):
    shift_type_id: Optional[uuid.UUID] = None
    date: Optional[date] = None
    start_datetime: Optional[datetime] = None
    end_datetime: Optional[datetime] = None
    notes: Optional[str] = Field(None, max_length=2000)
    location: Optional[str] = Field(None, max_length=300)
    grat_type: Optional[str] = Field(None, max_length=100)

    _sanitize_notes = field_validator("notes", mode="before")(_sanitize_text)
    _sanitize_location = field_validator("location", mode="before")(_sanitize_text)
    _sanitize_grat_type = field_validator("grat_type", mode="before")(_sanitize_text)


class ShiftResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    station_id: uuid.UUID
    shift_type_id: Optional[uuid.UUID]
    date: date
    start_datetime: datetime
    end_datetime: datetime
    status: ShiftStatus
    notes: Optional[str]
    created_by: Optional[uuid.UUID]
    published_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    location: Optional[str] = None
    grat_type: Optional[str] = None

    # Nested info
    user_name: Optional[str] = None
    user_numero_ordem: Optional[str] = None
    shift_type_name: Optional[str] = None
    shift_type_code: Optional[str] = None
    shift_type_color: Optional[str] = None

    model_config = {"from_attributes": True}


class ShiftListResponse(BaseModel):
    shifts: list[ShiftResponse]
    total: int


class ShiftPublishRequest(BaseModel):
    shift_ids: list[uuid.UUID] = Field(..., min_length=1)


class ShiftPublishResponse(BaseModel):
    published_count: int
    conflicts: list["ConflictDetail"]
    message: str


class ConflictDetail(BaseModel):
    shift_id: uuid.UUID
    user_id: uuid.UUID
    user_name: str
    conflict_type: str  # "overlap", "min_rest", "warning"
    description: str
    severity: str = "error"  # "error" or "warning"


class ShiftValidateRequest(BaseModel):
    """Dry-run validation of a batch of shift IDs."""
    shift_ids: list[uuid.UUID] = Field(..., min_length=1)


class ShiftValidateResponse(BaseModel):
    valid: bool
    conflicts: list[ConflictDetail]


class ShiftBulkCreate(BaseModel):
    """Create multiple shifts at once (from template)."""
    shifts: list[ShiftCreate] = Field(..., min_length=1)


# ── Swap ──────────────────────────────────────────────────


class SwapCreateRequest(BaseModel):
    requester_shift_id: uuid.UUID
    target_shift_id: uuid.UUID
    target_id: Optional[uuid.UUID] = None  # unused by backend; target derived from shift
    reason: Optional[str] = Field(None, max_length=500)

    _sanitize_reason = field_validator("reason", mode="before")(_sanitize_text)


class SwapResponse(BaseModel):
    id: uuid.UUID
    requester_shift_id: uuid.UUID
    target_shift_id: uuid.UUID
    requester_id: uuid.UUID
    target_id: uuid.UUID
    status: SwapStatus
    reason: Optional[str]
    responded_at: Optional[datetime]
    approved_by: Optional[uuid.UUID]
    approved_at: Optional[datetime]
    created_at: datetime

    model_config = {"from_attributes": True}


class SwapActionRequest(BaseModel):
    action: str = Field(..., pattern="^(accept|reject|approve|cancel)$")
