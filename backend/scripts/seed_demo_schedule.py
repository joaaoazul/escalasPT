"""
Demo schedule for a station created by scripts/seed.py (PT-VNG).

Run after the seed, against the same database:
  python -m scripts.seed_demo_schedule [--start 2026-09-21] [--published-weeks 4] [--draft-weeks 2]

What it builds, from --start (a Monday):
- Atendimento and Patrulha covered every day, every slot: AT1-3 with one
  militar each, OC1-3 with two. The 16 guardas follow a 16-day cycle,
  offset by one day each, so each cycle position is held by exactly one
  guarda on any given day — full coverage by construction. Within a cycle
  the order is 00-08 → 08-16 → 16-24 → folga, so no one ever gets under
  24h between shifts (the app's minimum is 8h).
- Secretaria and Inquéritos Mon-Fri 09-17 for the militares whose default
  shift type says so.
- A few Gratificados on the evening after a 00-08 patrol.
- Days off are left empty, as the UI leaves them. No Folga/Férias rows:
  the minimum-rest check counts full-day types as shifts, so two of them
  back to back (or one after a 16-24) read as "0h de descanso" warnings.
- The first --published-weeks as published, the rest as drafts for the
  comandante to review and publish in the demo.

Times follow the app's convention: the Portuguese wall-clock time, stored
with a +00 offset and shown as is (see frontend/src/utils/helpers.ts).
"""

from __future__ import annotations

import argparse
import asyncio
import uuid
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import and_, func, select

from app.database import async_session_factory
from app.models import ShiftType, Station, User, UserRole
from app.models.shift import Shift, ShiftStatus
from app.services.conflict_detector import validate_shifts
from app.utils.logging import get_logger, setup_logging

setup_logging()
logger = get_logger(__name__)

# One 16-day cycle. (slot, service) or None for a day off.
# Blocks of 00-08 → 08-16 → 16-24, then rest; the first block of each cycle
# is Atendimento, the other two Patrulha, so each day has 1 AT and 2 OC per slot.
CYCLE: list[tuple[int, str] | None] = [
    (1, "AT"), (2, "AT"), (3, "AT"), None,
    (1, "OC"), (2, "OC"), (3, "OC"), None,
    (1, "OC"), (2, "OC"), (3, "OC"), None,
    None, None, None, None,
]

# Gratificados: (day offset from start, index of the guarda on that day's
# 00-08 AT slot is not used — we pick whoever has 00-08 OC), location, type
GRATIFICADOS = [
    (3, "Estádio Municipal", "Evento desportivo"),
    (10, "Centro Comercial Arrábida", "Segurança privada"),
    (17, "Feira de Outono — Cais de Gaia", "Evento cultural"),
    (24, "Estádio Municipal", "Evento desportivo"),
]

SLOT_HOURS = {1: (0, 8), 2: (8, 16), 3: (16, 24)}


def _at(day: date, hour: int) -> datetime:
    return datetime.combine(day, time(0), tzinfo=timezone.utc) + timedelta(hours=hour)


async def build(start: date, published_weeks: int, draft_weeks: int) -> None:
    if start.weekday() != 0:
        raise SystemExit(f"--start must be a Monday, got {start:%A}")
    days = 7 * (published_weeks + draft_weeks)
    end = start + timedelta(days=days - 1)
    publish_until = start + timedelta(days=7 * published_weeks - 1)

    async with async_session_factory() as db:
        station = (await db.execute(select(Station).where(Station.code == "PT-VNG"))).scalar_one_or_none()
        if station is None:
            raise SystemExit("Station PT-VNG not found — run scripts.seed first.")

        existing = await db.scalar(
            select(func.count(Shift.id)).where(and_(
                Shift.station_id == station.id, Shift.date >= start, Shift.date <= end,
            ))
        )
        if existing:
            raise SystemExit(f"{existing} shifts already exist between {start} and {end}; not touching them.")

        types = {
            st.code: st
            for st in (await db.execute(select(ShiftType).where(ShiftType.station_id == station.id))).scalars()
        }
        users = list((await db.execute(
            select(User).where(User.station_id == station.id, User.is_active == True)  # noqa: E712
        )).scalars())
        comandante = next(u for u in users if u.role == UserRole.COMANDANTE)
        fixed = [u for u in users if u.default_shift_type_id is not None]
        guardas = sorted(
            (u for u in users if u.role == UserRole.MILITAR and u.default_shift_type_id is None),
            key=lambda u: int(u.numero_ordem or 0),
        )
        if len(guardas) != len(CYCLE):
            raise SystemExit(f"Expected {len(CYCLE)} guardas in rotation, found {len(guardas)}.")

        shifts: list[Shift] = []
        now = datetime.now(timezone.utc)

        def add(user: User, code: str, day: date, start_h: int, end_h: int, **extra) -> Shift:
            published = day <= publish_until
            shift = Shift(
                id=uuid.uuid4(),
                user_id=user.id,
                station_id=station.id,
                shift_type_id=types[code].id,
                date=day,
                start_datetime=_at(day, start_h),
                end_datetime=_at(day, end_h),
                status=ShiftStatus.PUBLISHED if published else ShiftStatus.DRAFT,
                published_at=now if published else None,
                created_by=comandante.id,
                **extra,
            )
            shifts.append(shift)
            return shift

        # Rotation: guarda i on day d holds CYCLE[(d + i) % 16].
        night_oc: dict[int, list[User]] = {}
        for d in range(days):
            day = start + timedelta(days=d)
            for i, guarda in enumerate(guardas):
                entry = CYCLE[(d + i) % len(CYCLE)]
                if entry is None:
                    continue
                slot, service = entry
                h0, h1 = SLOT_HOURS[slot]
                add(guarda, f"{service}{slot}", day, h0, h1)
                if slot == 1 and service == "OC":
                    night_oc.setdefault(d, []).append(guarda)

        # Secretaria / Inquéritos: Mon-Fri 09-17.
        for d in range(days):
            day = start + timedelta(days=d)
            if day.weekday() >= 5:
                continue
            for user in fixed:
                code = next(c for c, st in types.items() if st.id == user.default_shift_type_id)
                add(user, code, day, 9, 17)

        # Gratificados: the evening after a 00-08 patrol, 18-23 (10h rest before,
        # 9h before the 08-16 that follows in the cycle).
        for d, location, grat_type in GRATIFICADOS:
            if d >= days or not night_oc.get(d):
                continue
            add(night_oc[d][0], "GRAT", start + timedelta(days=d), 18, 23,
                location=location, grat_type=grat_type)

        db.add_all(shifts)
        await db.flush()

        conflicts = await validate_shifts(db, [s.id for s in shifts])
        if conflicts:
            for c in conflicts[:20]:
                logger.error("Conflict: %s", c)
            raise SystemExit(f"{len(conflicts)} conflicts in the generated schedule; nothing saved.")

        await db.commit()

    by_status: dict[str, int] = {}
    for s in shifts:
        by_status[s.status.value] = by_status.get(s.status.value, 0) + 1
    print(f"\n  Demo schedule {start} → {end}: {len(shifts)} shifts {by_status}, 0 conflicts")
    print(f"  Published up to {publish_until}; drafts after.\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    parser.add_argument("--start", type=date.fromisoformat, default=None,
                        help="Monday the schedule starts on (default: this week's Monday)")
    parser.add_argument("--published-weeks", type=int, default=4)
    parser.add_argument("--draft-weeks", type=int, default=2)
    args = parser.parse_args()
    today = date.today()
    start = args.start or today - timedelta(days=today.weekday())
    asyncio.run(build(start, args.published_weeks, args.draft_weeks))


if __name__ == "__main__":
    main()
