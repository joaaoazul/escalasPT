"""
Swaps router — shift swap requests between military personnel.

Endpoints:
  POST   /swaps/               create swap request
  GET    /swaps/               list swaps (own or station-wide for commanders)
  GET    /swaps/{id}           get single swap
  POST   /swaps/{id}/respond   target accepts or rejects
  POST   /swaps/{id}/decide    comandante approves or rejects
  POST   /swaps/{id}/cancel    requester cancels pending request
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_user, get_db, require_role
from app.models.shift import Shift, SwapStatus
from app.models.user import User, UserRole
from app.schemas.shift import SwapCreateRequest
from app.services import swap_service

router = APIRouter(prefix="/swaps", tags=["Swaps"])


# ── Serialization helper ─────────────────────────────────

def _shift_summary(shift: Optional[Shift]) -> Optional[Dict[str, Any]]:
    if shift is None:
        return None
    return {
        "id": str(shift.id),
        "date": str(shift.date),
        "start_datetime": shift.start_datetime.isoformat() if shift.start_datetime else None,
        "end_datetime": shift.end_datetime.isoformat() if shift.end_datetime else None,
        "shift_type_code": shift.shift_type.code if shift.shift_type else None,
        "shift_type_color": shift.shift_type.color if shift.shift_type else None,
        "shift_type_name": shift.shift_type.name if shift.shift_type else None,
        "user_id": str(shift.user_id),
        "user_name": shift.user.full_name if shift.user else None,
    }


def _swap_out(swap) -> Dict[str, Any]:
    return {
        "id": str(swap.id),
        "requester_shift_id": str(swap.requester_shift_id),
        "target_shift_id": str(swap.target_shift_id),
        "requester_id": str(swap.requester_id),
        "target_id": str(swap.target_id),
        "status": swap.status.value,
        "reason": swap.reason,
        "responded_at": swap.responded_at.isoformat() if swap.responded_at else None,
        "approved_by": str(swap.approved_by) if swap.approved_by else None,
        "approved_at": swap.approved_at.isoformat() if swap.approved_at else None,
        "created_at": swap.created_at.isoformat() if swap.created_at else None,
        "requester_shift": _shift_summary(swap.requester_shift),
        "target_shift": _shift_summary(swap.target_shift),
    }


# ── Endpoints ────────────────────────────────────────────

@router.post("/", status_code=201)
async def create_swap(
    data: SwapCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Military creates a swap request targeting another person's shift."""
    swap = await swap_service.create_swap(
        db,
        requester_id=current_user.id,
        requester_shift_id=data.requester_shift_id,
        target_shift_id=data.target_shift_id,
        reason=data.reason,
    )
    await db.commit()
    return _swap_out(swap)


@router.get("/")
async def list_swaps(
    status: Optional[SwapStatus] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[Dict[str, Any]]:
    """
    List swap requests.
    - Commanders/Adjuntos see all swaps for their station.
    - Others see only their own (as requester or target).
    """
    if current_user.role in (UserRole.COMANDANTE, UserRole.ADJUNTO):
        swaps = await swap_service.list_swaps(
            db, station_id=current_user.station_id, status=status
        )
    else:
        swaps = await swap_service.list_swaps(
            db, user_id=current_user.id, status=status
        )
    return [_swap_out(s) for s in swaps]


@router.get("/{swap_id}")
async def get_swap(
    swap_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    swap = await swap_service.get_swap(db, swap_id)
    # Only parties and commanders can see the swap
    is_party = swap.requester_id == current_user.id or swap.target_id == current_user.id
    is_command = current_user.role in (UserRole.COMANDANTE, UserRole.ADJUNTO, UserRole.ADMIN)
    if not (is_party or is_command):
        from app.exceptions import AuthorizationError
        raise AuthorizationError("Not authorised to view this swap")
    return _swap_out(swap)


@router.post("/{swap_id}/respond")
async def respond_to_swap(
    swap_id: uuid.UUID,
    accept: bool = Query(..., description="true to accept, false to reject"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Target militar responds to a swap request directed at them."""
    swap = await swap_service.respond_to_swap(db, swap_id, current_user.id, accept)
    await db.commit()
    return _swap_out(swap)


@router.post("/{swap_id}/decide")
async def decide_swap(
    swap_id: uuid.UUID,
    approve: bool = Query(..., description="true to approve, false to reject"),
    current_user: User = Depends(
        require_role(UserRole.COMANDANTE, UserRole.ADJUNTO, UserRole.ADMIN)
    ),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Comandante approves or rejects a mutually-agreed swap."""
    swap = await swap_service.decide_swap(db, swap_id, current_user.id, approve)
    await db.commit()
    return _swap_out(swap)


@router.post("/{swap_id}/cancel")
async def cancel_swap(
    swap_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Requester cancels their own pending swap request."""
    swap = await swap_service.cancel_swap(db, swap_id, current_user.id)
    await db.commit()
    return _swap_out(swap)


@router.get("/{swap_id}/pdf")
async def download_swap_pdf(
    swap_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Download a PDF receipt for an approved swap.

    Only the requester, target, approver, and commanders can download.
    """
    from app.exceptions import AuthorizationError, ValidationError
    from app.models.station import Station
    from app.services.swap_pdf_service import generate_swap_pdf

    swap = await swap_service.get_swap(db, swap_id)

    # Only approved swaps can be exported
    if swap.status != SwapStatus.APPROVED:
        raise ValidationError("Só é possível exportar trocas aprovadas")

    # Authorization: parties + approver + commanders
    is_party = swap.requester_id == current_user.id or swap.target_id == current_user.id
    is_approver = swap.approved_by == current_user.id
    is_command = current_user.role in (UserRole.COMANDANTE, UserRole.ADJUNTO, UserRole.ADMIN)
    if not (is_party or is_approver or is_command):
        raise AuthorizationError("Não tem permissão para exportar esta troca")

    # Load approver user
    approver = await db.get(User, swap.approved_by) if swap.approved_by else None
    # Load station
    req_shift = swap.requester_shift
    station = await db.get(Station, req_shift.station_id) if req_shift else None

    def _time(dt) -> str:
        if dt is None:
            return "—"
        return dt.strftime("%H:%M")

    def _fmt_dt(dt) -> str:
        if dt is None:
            return "—"
        return dt.strftime("%d/%m/%Y às %H:%M")

    def _shift_date(shift: Shift | None) -> str:
        if not shift:
            return "—"
        return shift.date.strftime("%d/%m/%Y") if shift.date else "—"

    pdf_bytes = generate_swap_pdf(
        swap_id=str(swap.id),
        station_name=station.name if station else "—",
        requester_name=req_shift.user.full_name if req_shift and req_shift.user else "—",
        requester_shift_type=req_shift.shift_type.name if req_shift and req_shift.shift_type else "—",
        requester_shift_date=_shift_date(req_shift),
        requester_start_time=_time(req_shift.start_datetime if req_shift else None),
        requester_end_time=_time(req_shift.end_datetime if req_shift else None),
        target_name=swap.target_shift.user.full_name if swap.target_shift and swap.target_shift.user else "—",
        target_shift_type=swap.target_shift.shift_type.name if swap.target_shift and swap.target_shift.shift_type else "—",
        target_shift_date=_shift_date(swap.target_shift),
        target_start_time=_time(swap.target_shift.start_datetime if swap.target_shift else None),
        target_end_time=_time(swap.target_shift.end_datetime if swap.target_shift else None),
        requested_at=_fmt_dt(swap.created_at),
        accepted_at=_fmt_dt(swap.responded_at),
        approved_at=_fmt_dt(swap.approved_at),
    )

    filename = f"troca_{str(swap.id)[:8]}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
