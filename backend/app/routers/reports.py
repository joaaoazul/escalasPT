"""
Reports router — PDF exports for schedule and swaps.

Endpoints:
  GET  /reports/swaps     weekly/range summary of approved swaps (PDF)
  GET  /reports/schedule  monthly station schedule grid (PDF)
"""

from __future__ import annotations

import calendar
from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.dependencies import get_current_user, get_db, require_role
from app.models.shift import Shift, ShiftStatus, ShiftSwapRequest, SwapStatus
from app.models.station import Station
from app.models.user import User, UserRole

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.get("/swaps")
async def swaps_report_pdf(
    date_from: date = Query(
        None, description="Start date (defaults to Monday of current week)"
    ),
    date_to: date = Query(
        None, description="End date (defaults to Sunday of current week)"
    ),
    current_user: User = Depends(
        require_role(UserRole.COMANDANTE, UserRole.ADJUNTO, UserRole.SECRETARIA)
    ),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Export approved swaps in a date range as PDF.

    Available to Comandante, Adjunto, and Secretaria.
    Defaults to the current week (Monday–Sunday).
    """
    from app.services.report_pdf_service import generate_swaps_report_pdf

    # Default to current week
    today = date.today()
    if date_from is None:
        date_from = today - timedelta(days=today.weekday())  # Monday
    if date_to is None:
        date_to = date_from + timedelta(days=6)  # Sunday

    station = await db.get(Station, current_user.station_id)
    station_name = station.name if station else "—"

    # Query approved swaps where at least one shift falls in the range
    query = (
        select(ShiftSwapRequest)
        .where(
            ShiftSwapRequest.status == SwapStatus.APPROVED,
        )
        .options(
            selectinload(ShiftSwapRequest.requester_shift)
            .selectinload(Shift.shift_type),
            selectinload(ShiftSwapRequest.requester_shift)
            .selectinload(Shift.user),
            selectinload(ShiftSwapRequest.target_shift)
            .selectinload(Shift.shift_type),
            selectinload(ShiftSwapRequest.target_shift)
            .selectinload(Shift.user),
        )
        .order_by(ShiftSwapRequest.approved_at)
    )
    result = await db.execute(query)
    all_swaps = result.scalars().all()

    # Filter by station + date range on the shift dates
    swap_dicts = []
    for sw in all_swaps:
        rs = sw.requester_shift
        ts = sw.target_shift
        if not rs or not ts:
            continue
        # Station filter
        if rs.station_id != current_user.station_id:
            continue
        # Date range filter: either shift date in range
        if not (
            (date_from <= rs.date <= date_to) or
            (date_from <= ts.date <= date_to)
        ):
            continue

        def _fmt_dt(dt):
            return dt.strftime("%d/%m/%Y %H:%M") if dt else "—"

        swap_dicts.append({
            "requester_name": rs.user.full_name if rs.user else "—",
            "requester_shift_type": rs.shift_type.code if rs.shift_type else "—",
            "requester_date": rs.date.strftime("%d/%m/%Y"),
            "requester_time": f"{rs.start_datetime.strftime('%H:%M')}–{rs.end_datetime.strftime('%H:%M')}" if rs.start_datetime else "—",
            "target_name": ts.user.full_name if ts.user else "—",
            "target_shift_type": ts.shift_type.code if ts.shift_type else "—",
            "target_date": ts.date.strftime("%d/%m/%Y"),
            "target_time": f"{ts.start_datetime.strftime('%H:%M')}–{ts.end_datetime.strftime('%H:%M')}" if ts.start_datetime else "—",
            "requested_at": _fmt_dt(sw.created_at),
            "accepted_at": _fmt_dt(sw.responded_at),
            "approved_at": _fmt_dt(sw.approved_at),
        })

    pdf_bytes = generate_swaps_report_pdf(
        station_name=station_name,
        date_from=date_from,
        date_to=date_to,
        swaps=swap_dicts,
    )

    filename = f"trocas_{date_from.strftime('%Y%m%d')}_{date_to.strftime('%Y%m%d')}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/schedule")
async def schedule_pdf(
    year: int = Query(..., ge=2020, le=2100),
    month: int = Query(..., ge=1, le=12),
    current_user: User = Depends(
        require_role(UserRole.COMANDANTE, UserRole.ADJUNTO, UserRole.SECRETARIA)
    ),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Export the monthly station schedule as a landscape PDF grid.

    Available to Comandante, Adjunto, and Secretaria.
    """
    from app.services.report_pdf_service import generate_schedule_pdf

    station = await db.get(Station, current_user.station_id)
    station_name = station.name if station else "—"

    num_days = calendar.monthrange(year, month)[1]
    start_date = date(year, month, 1)
    end_date = date(year, month, num_days)

    # Get station users (active, not admin)
    users_q = (
        select(User)
        .where(
            User.station_id == current_user.station_id,
            User.is_active == True,
            User.role != UserRole.ADMIN,
        )
        .order_by(User.full_name)
    )
    users_result = await db.execute(users_q)
    users = users_result.scalars().all()

    user_dicts = [
        {"id": str(u.id), "full_name": u.full_name, "nip": u.nip}
        for u in users
    ]

    # Get published shifts for the month
    shifts_q = (
        select(Shift)
        .where(
            Shift.station_id == current_user.station_id,
            Shift.status == ShiftStatus.PUBLISHED,
            Shift.date >= start_date,
            Shift.date <= end_date,
        )
        .options(selectinload(Shift.shift_type))
    )
    shifts_result = await db.execute(shifts_q)
    shifts = shifts_result.scalars().all()

    shift_dicts = [
        {
            "user_id": str(s.user_id),
            "date": str(s.date),
            "shift_type_code": s.shift_type.code if s.shift_type else "",
            "shift_type_color": s.shift_type.color if s.shift_type else "",
        }
        for s in shifts
    ]

    pdf_bytes = generate_schedule_pdf(
        station_name=station_name,
        year=year,
        month=month,
        users=user_dicts,
        shifts=shift_dicts,
    )

    month_str = f"{year}{month:02d}"
    filename = f"escala_{month_str}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
