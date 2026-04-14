"""
Swap service — business logic for shift swap requests.

Flow:
  1. Militar A requests swap (PENDING_TARGET)       → target notified
  2. Target accepts (PENDING_APPROVAL)              → comandante notified
     or rejects (REJECTED)                          → requester notified
  3. Comandante approves (APPROVED, shifts swapped) → both parties notified
     or rejects (REJECTED)                          → both parties notified
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.exceptions import AuthorizationError, NotFoundError, ValidationError
from app.models.notification import NotificationType
from app.models.shift import Shift, ShiftStatus, ShiftSwapRequest, SwapStatus
from app.models.user import User
from app.services import notification_service
from app.services.conflict_detector import validate_swap
from app.services.notification_service import ws_manager
from app.utils.logging import get_logger

logger = get_logger(__name__)

# ── Helpers ──────────────────────────────────────────────


async def _load_swap(db: AsyncSession, swap_id: uuid.UUID) -> ShiftSwapRequest:
    swap = await db.get(
        ShiftSwapRequest,
        swap_id,
        options=[
            selectinload(ShiftSwapRequest.requester_shift).selectinload(Shift.shift_type),
            selectinload(ShiftSwapRequest.requester_shift).selectinload(Shift.user),
            selectinload(ShiftSwapRequest.target_shift).selectinload(Shift.shift_type),
            selectinload(ShiftSwapRequest.target_shift).selectinload(Shift.user),
        ],
    )
    if swap is None:
        raise NotFoundError("Swap request")
    return swap


# ── Service functions ────────────────────────────────────


async def create_swap(
    db: AsyncSession,
    requester_id: uuid.UUID,
    requester_shift_id: uuid.UUID,
    target_shift_id: uuid.UUID,
    reason: Optional[str] = None,
) -> ShiftSwapRequest:
    """Create a swap request from requester toward the target shift owner."""

    # Load requester shift
    req_shift = await db.get(
        Shift,
        requester_shift_id,
        options=[selectinload(Shift.user), selectinload(Shift.shift_type)],
    )
    if req_shift is None or req_shift.user_id != requester_id:
        raise AuthorizationError("This shift does not belong to you")
    if req_shift.status != ShiftStatus.PUBLISHED:
        raise ValidationError("Only published shifts can be swapped")

    # Load target shift
    tgt_shift = await db.get(
        Shift,
        target_shift_id,
        options=[selectinload(Shift.user), selectinload(Shift.shift_type)],
    )
    if tgt_shift is None:
        raise NotFoundError("Target shift")
    if tgt_shift.station_id != req_shift.station_id:
        raise ValidationError("Cannot swap shifts from different stations")
    if tgt_shift.status != ShiftStatus.PUBLISHED:
        raise ValidationError("Target shift is not published")
    if tgt_shift.user_id == requester_id:
        raise ValidationError("Cannot swap a shift with yourself")

    # ── Shift-type restrictions ──────────────────────────
    # Only normal services (AT/OC), gratificados, and folgas can be swapped.
    # Absences (FER, CONV, MF, DIL, LIC, etc.) cannot be swapped.
    NON_SWAPPABLE_ABSENCE = True  # is_absence=True blocks swap, EXCEPT folga & gratificado
    SWAPPABLE_ABSENCE_CODES = {"F", "GRAT"}

    req_type = req_shift.shift_type
    tgt_type = tgt_shift.shift_type

    if req_type and req_type.is_absence and req_type.code not in SWAPPABLE_ABSENCE_CODES:
        raise ValidationError(
            f"Não é possível trocar turnos do tipo '{req_type.name}' (ausência)"
        )
    if tgt_type and tgt_type.is_absence and tgt_type.code not in SWAPPABLE_ABSENCE_CODES:
        raise ValidationError(
            f"Não é possível trocar turnos do tipo '{tgt_type.name}' (ausência)"
        )

    # Block swap between users on the same shift type on the same day
    if (
        req_shift.date == tgt_shift.date
        and req_type
        and tgt_type
        and req_type.id == tgt_type.id
    ):
        raise ValidationError(
            "Não pode trocar com um militar que está no mesmo serviço, no mesmo dia"
        )

    # No duplicate pending swap for the requester shift
    dup = await db.execute(
        select(ShiftSwapRequest).where(
            and_(
                ShiftSwapRequest.requester_shift_id == requester_shift_id,
                ShiftSwapRequest.status.in_(
                    [SwapStatus.PENDING_TARGET, SwapStatus.PENDING_APPROVAL]
                ),
            )
        )
    )
    if dup.scalar_one_or_none():
        raise ValidationError("A pending swap request already exists for this shift")

    # No duplicate pending swap targeting the same target shift
    dup_tgt = await db.execute(
        select(ShiftSwapRequest).where(
            and_(
                ShiftSwapRequest.target_shift_id == target_shift_id,
                ShiftSwapRequest.status.in_(
                    [SwapStatus.PENDING_TARGET, SwapStatus.PENDING_APPROVAL]
                ),
            )
        )
    )
    if dup_tgt.scalar_one_or_none():
        raise ValidationError("That shift already has a pending swap request")

    # ── Conflict validation: check if the swap would create conflicts ──
    swap_conflicts = await validate_swap(db, req_shift, tgt_shift)
    errors = [c for c in swap_conflicts if c.severity == "error"]
    if errors:
        descriptions = "; ".join(e.description for e in errors)
        raise ValidationError(f"Troca criaria conflitos: {descriptions}")

    swap = ShiftSwapRequest(
        id=uuid.uuid4(),
        requester_shift_id=requester_shift_id,
        target_shift_id=target_shift_id,
        requester_id=requester_id,
        target_id=tgt_shift.user_id,
        reason=reason,
        status=SwapStatus.PENDING_TARGET,
    )
    db.add(swap)
    await db.flush()

    # Attach already-loaded relationships so the router can serialise without lazy-loading
    swap.requester_shift = req_shift
    swap.target_shift = tgt_shift

    # Notify target
    requester_name = req_shift.user.full_name if req_shift.user else "Colega"
    req_code = req_shift.shift_type.code if req_shift.shift_type else "?"
    tgt_code = tgt_shift.shift_type.code if tgt_shift.shift_type else "?"
    await notification_service.create_notification(
        db,
        user_id=tgt_shift.user_id,
        station_id=req_shift.station_id,
        notification_type=NotificationType.SWAP_REQUESTED,
        title="Pedido de Troca de Turno",
        message=(
            f"{requester_name} quer trocar o seu turno {req_code} "
            f"({req_shift.date}) pelo seu {tgt_code} ({tgt_shift.date})."
        ),
        data={"swap_id": str(swap.id)},
    )

    logger.info("Swap created %s: %s <-> %s", swap.id, requester_id, tgt_shift.user_id)
    return swap


async def respond_to_swap(
    db: AsyncSession,
    swap_id: uuid.UUID,
    responder_id: uuid.UUID,
    accept: bool,
) -> ShiftSwapRequest:
    """Target militar accepts or rejects the swap request."""
    swap = await _load_swap(db, swap_id)

    if swap.target_id != responder_id:
        raise AuthorizationError("You are not the target of this swap request")
    if swap.status != SwapStatus.PENDING_TARGET:
        raise ValidationError(
            f"Swap is not awaiting your response (status: {swap.status.value})"
        )

    swap.responded_at = datetime.now(timezone.utc)

    if not accept:
        swap.status = SwapStatus.REJECTED
        await db.flush()
        await notification_service.create_notification(
            db,
            user_id=swap.requester_id,
            station_id=swap.requester_shift.station_id,
            notification_type=NotificationType.SWAP_REJECTED,
            title="Troca Recusada",
            message="O colega recusou o pedido de troca de turno.",
            data={"swap_id": str(swap.id)},
        )
        logger.info("Swap %s rejected by target %s", swap_id, responder_id)
        return swap

    # Accept → pending approval from comandante
    swap.status = SwapStatus.PENDING_APPROVAL
    await db.flush()

    req_code = swap.requester_shift.shift_type.code if swap.requester_shift.shift_type else "?"
    tgt_code = swap.target_shift.shift_type.code if swap.target_shift.shift_type else "?"
    req_name = swap.requester_shift.user.full_name if swap.requester_shift.user else "?"
    tgt_name = swap.target_shift.user.full_name if swap.target_shift.user else "?"

    # Notify requester that target accepted
    await notification_service.create_notification(
        db,
        user_id=swap.requester_id,
        station_id=swap.requester_shift.station_id,
        notification_type=NotificationType.SWAP_ACCEPTED,
        title="Troca Aceite — Aguarda Aprovação",
        message=(
            f"{tgt_name} aceitou a troca. "
            "Aguarda aprovação do comandante."
        ),
        data={"swap_id": str(swap.id)},
    )

    # Notify commanders (broadcast to station excluding both parties)
    await notification_service.notify_station(
        db,
        station_id=swap.requester_shift.station_id,
        notification_type=NotificationType.SWAP_REQUESTED,
        title="Troca Pendente de Aprovação",
        message=(
            f"Pedido de troca {req_name} ({req_code}) ↔ {tgt_name} ({tgt_code}) "
            "aguarda aprovação."
        ),
        data={"swap_id": str(swap.id)},
        exclude_user_ids={swap.requester_id, swap.target_id},
    )

    logger.info("Swap %s accepted by target %s, pending approval", swap_id, responder_id)
    return swap


async def decide_swap(
    db: AsyncSession,
    swap_id: uuid.UUID,
    approver_id: uuid.UUID,
    approve: bool,
) -> ShiftSwapRequest:
    """Comandante/Adjunto approves or rejects a swap that both parties agreed to."""
    swap = await _load_swap(db, swap_id)

    if swap.status != SwapStatus.PENDING_APPROVAL:
        raise ValidationError(
            f"Swap is not awaiting command approval (status: {swap.status.value})"
        )

    swap.approved_by = approver_id
    swap.approved_at = datetime.now(timezone.utc)
    station_id = swap.requester_shift.station_id

    if not approve:
        swap.status = SwapStatus.REJECTED
        await db.flush()
        notif_type = NotificationType.SWAP_REJECTED
        title = "Troca Rejeitada pelo Comando"
        message = "O comandante rejeitou o pedido de troca de turno."
    else:
        swap.status = SwapStatus.APPROVED
        # Physically swap the user_ids on the two shifts
        req_shift = await db.get(Shift, swap.requester_shift_id)
        tgt_shift = await db.get(Shift, swap.target_shift_id)
        if req_shift and tgt_shift:
            # Final conflict check before approving
            swap_conflicts = await validate_swap(db, req_shift, tgt_shift)
            errors = [c for c in swap_conflicts if c.severity == "error"]
            if errors:
                descriptions = "; ".join(e.description for e in errors)
                raise ValidationError(
                    f"Não é possível aprovar — conflitos detectados: {descriptions}"
                )
            req_shift.user_id, tgt_shift.user_id = tgt_shift.user_id, req_shift.user_id
            db.add(req_shift)
            db.add(tgt_shift)
        await db.flush()
        notif_type = NotificationType.SWAP_APPROVED
        title = "Troca Aprovada"
        message = "O comandante aprovou a troca de turno. O horário foi actualizado."

    # Notify both parties
    for uid in (swap.requester_id, swap.target_id):
        await notification_service.create_notification(
            db,
            user_id=uid,
            station_id=station_id,
            notification_type=notif_type,
            title=title,
            message=message,
            data={"swap_id": str(swap.id)},
        )

    # Broadcast calendar sync to ALL station members
    await ws_manager.broadcast_to_station(
        str(station_id),
        {
            "type": "calendar_sync",
            "reason": "swap_approved" if approve else "swap_rejected",
        },
    )

    logger.info(
        "Swap %s %s by approver %s",
        swap_id,
        "approved" if approve else "rejected",
        approver_id,
    )
    return swap


async def cancel_swap(
    db: AsyncSession,
    swap_id: uuid.UUID,
    user_id: uuid.UUID,
) -> ShiftSwapRequest:
    """Requester cancels their own pending swap request."""
    swap = await _load_swap(db, swap_id)

    if swap.requester_id != user_id:
        raise AuthorizationError("Only the requester can cancel this swap")
    if swap.status not in (SwapStatus.PENDING_TARGET, SwapStatus.PENDING_APPROVAL):
        raise ValidationError(
            f"Cannot cancel a swap in status: {swap.status.value}"
        )

    swap.status = SwapStatus.CANCELLED
    await db.flush()
    logger.info("Swap %s cancelled by requester %s", swap_id, user_id)
    return swap


async def list_swaps(
    db: AsyncSession,
    user_id: Optional[uuid.UUID] = None,
    station_id: Optional[uuid.UUID] = None,
    status: Optional[SwapStatus] = None,
) -> List[ShiftSwapRequest]:
    """List swap requests filtered by user, station, and/or status."""
    query = (
        select(ShiftSwapRequest)
        .options(
            selectinload(ShiftSwapRequest.requester_shift).selectinload(Shift.shift_type),
            selectinload(ShiftSwapRequest.requester_shift).selectinload(Shift.user),
            selectinload(ShiftSwapRequest.target_shift).selectinload(Shift.shift_type),
            selectinload(ShiftSwapRequest.target_shift).selectinload(Shift.user),
        )
        .order_by(ShiftSwapRequest.created_at.desc())
    )

    if user_id is not None:
        query = query.where(
            or_(
                ShiftSwapRequest.requester_id == user_id,
                ShiftSwapRequest.target_id == user_id,
            )
        )

    if station_id is not None:
        # Filter via the requester's shift station
        query = query.join(
            Shift,
            Shift.id == ShiftSwapRequest.requester_shift_id,
        ).where(Shift.station_id == station_id)

    if status is not None:
        query = query.where(ShiftSwapRequest.status == status)

    result = await db.execute(query)
    return list(result.scalars().unique().all())


async def get_swap(db: AsyncSession, swap_id: uuid.UUID) -> ShiftSwapRequest:
    """Load a single swap with full relationships."""
    return await _load_swap(db, swap_id)
