"""
Seed script — replaces fake VNG data with real Castro Marim personnel
and marks 2026 vacation plan (férias).

Run via Docker:
  docker compose exec api python -m scripts.seed_castromarim
"""

from __future__ import annotations

import asyncio
import os
import uuid
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import delete, select, update, text

from app.database import async_session_factory
from app.models import Base, Station, ShiftType, User, UserRole
from app.models.shift import Shift, ShiftStatus
from app.utils.security import hash_password
from app.utils.logging import setup_logging, get_logger

setup_logging()
logger = get_logger(__name__)

SEED_PASSWORD = os.environ.get("SEED_DEFAULT_PASSWORD", "")
if not SEED_PASSWORD:
    raise SystemExit("Set SEED_DEFAULT_PASSWORD env var before running.")

# ── Personnel from RELAÇÃO DO EFECTIVO — PT/C. Marim ─────

# (posto, n_ordem, nip, full_name, username, role)
PERSONNEL = [
    # SAJ — Comandante do Posto
    ("SAJ", "53", "2020879", "Nelson Filipe das Neves Póvoa", "saj.povoa", UserRole.COMANDANTE),
    # CCH — Cabos-Chefe
    ("CCH", "431", "1950374", "Paulo Jorge dos Reis M. Martins", "cch.martins", UserRole.MILITAR),
    ("CCH", "187", "2100888", "Fernando Pedro Parreira Paixão", "cch.paixao", UserRole.MILITAR),
    # CABO
    ("CABO", "233", "1990256", "José António Segura Valentim", "cabo.valentim", UserRole.MILITAR),
    ("CABO", "403", "2010648", "Luís Alberto Fernandes Vicente", "cabo.vicente", UserRole.MILITAR),
    ("CABO", "510", "2030669", "Nuno Filipe Vicente Norberto", "cabo.norberto", UserRole.MILITAR),
    ("CABO", "364", "2030049", "Valter Filipe Martins Lourenço", "cabo.lourenco", UserRole.MILITAR),
    ("CABO", "1113", "2060668", "Márcio F. Gonçalves Andorinha", "cabo.andorinha", UserRole.MILITAR),
    # G. PRINC. — Guarda Principal
    ("G.PRINC", "1000", "2040262", "João António Saloio Valentim", "gp.valentim", UserRole.MILITAR),
    ("G.PRINC", "1008", "2070389", "Tiago Emanuel Pena Evangelista", "gp.evangelista", UserRole.MILITAR),
    ("G.PRINC", "1391", "2090211", "Cristiano André Cordeiro Pais", "gp.pais", UserRole.MILITAR),
    ("G.PRINC", "1348", "2100137", "Jorge Miguel Martins Pires", "gp.pires", UserRole.MILITAR),
    ("G.PRINC", "1548", "2120919", "Ângelo Miguel Carmo Bonança", "gp.bonanca", UserRole.MILITAR),
    ("G.PRINC", "717", "2160071", "João Paulo Rosa Simão", "gp.simao", UserRole.MILITAR),
    # GUARDA
    ("GUARDA", "765", "2210477", "Gonçalo Ant. Araújo Botequilha", "guarda.botequilha", UserRole.MILITAR),
    ("GUARDA", "815", "2210298", "Jorge Nelson Nunes Gonçalves", "guarda.goncalves", UserRole.MILITAR),
    ("GUARDA", "686", "2211299", "Vitor Hugo Estevão Santos", "guarda.santos", UserRole.MILITAR),
    ("GUARDA", "920", "2210578", "Diogo Miguel de Almeida Pereira", "guarda.pereira", UserRole.MILITAR),
    ("GUARDA", "909", "2220379", "João Paulo Viegas Azul", "guarda.azul", UserRole.MILITAR),
    ("GUARDA", "1069", "2221015", "José Carlos da Silva Rosa", "guarda.rosa", UserRole.MILITAR),
    ("GUARDA", "1219", "2221068", "Mariana Sofia F. Rodrigues", "guarda.rodrigues", UserRole.MILITAR),
    ("GUARDA", "1058", "2230338", "Miguel Revez Justo", "guarda.mjusto", UserRole.MILITAR),
    ("GUARDA", "954", "2240489", "Daniel Revez Justo", "guarda.djusto", UserRole.MILITAR),
]

# ── Vacation plan 2026 (PLANO DE FÉRIAS) ─────────────────
# Format: username → list of (start_date, end_date) inclusive
# Totals match the TOTAL DE DIAS column from the vacation plan.
# Dates are best-effort readings from the rotated plan document.
# Verify against the physical document and adjust as needed.

VACATION_2026 = {
    # SAJ Póvoa — 28 dias
    "saj.povoa": [
        (date(2026, 7, 1), date(2026, 7, 14)),    # 14d
        (date(2026, 9, 8), date(2026, 9, 14)),     # 7d
        (date(2026, 12, 22), date(2026, 12, 28)),   # 7d
    ],
    # CCH Martins — 26 dias
    "cch.martins": [
        (date(2026, 8, 1), date(2026, 8, 14)),     # 14d
        (date(2026, 2, 3), date(2026, 2, 8)),       # 6d
        (date(2026, 10, 13), date(2026, 10, 18)),   # 6d
    ],
    # CCH Paixão — 25 dias
    "cch.paixao": [
        (date(2026, 8, 14), date(2026, 8, 27)),    # 14d
        (date(2026, 3, 17), date(2026, 3, 22)),     # 6d
        (date(2026, 11, 17), date(2026, 11, 21)),   # 5d
    ],
    # CABO Valentim — 27 dias
    "cabo.valentim": [
        (date(2026, 7, 7), date(2026, 7, 20)),     # 14d
        (date(2026, 3, 3), date(2026, 3, 9)),       # 7d
        (date(2026, 10, 6), date(2026, 10, 11)),    # 6d
    ],
    # CABO Vicente — 27 dias
    "cabo.vicente": [
        (date(2026, 8, 1), date(2026, 8, 14)),     # 14d
        (date(2026, 4, 7), date(2026, 4, 13)),      # 7d
        (date(2026, 11, 3), date(2026, 11, 8)),     # 6d
    ],
    # CABO Norberto — 27 dias
    "cabo.norberto": [
        (date(2026, 7, 14), date(2026, 7, 27)),    # 14d
        (date(2026, 5, 5), date(2026, 5, 11)),      # 7d
        (date(2026, 9, 22), date(2026, 9, 27)),     # 6d
    ],
    # CABO Lourenço — 25 dias
    "cabo.lourenco": [
        (date(2026, 8, 4), date(2026, 8, 17)),     # 14d
        (date(2026, 6, 2), date(2026, 6, 7)),       # 6d
        (date(2026, 12, 8), date(2026, 12, 12)),    # 5d
    ],
    # CABO Andorinha — 25 dias
    "cabo.andorinha": [
        (date(2026, 8, 18), date(2026, 8, 31)),    # 14d
        (date(2026, 5, 19), date(2026, 5, 24)),     # 6d
        (date(2026, 10, 20), date(2026, 10, 24)),   # 5d
    ],
    # G.PRINC Valentim — 27 dias
    "gp.valentim": [
        (date(2026, 7, 1), date(2026, 7, 14)),     # 14d
        (date(2026, 2, 10), date(2026, 2, 16)),     # 7d
        (date(2026, 11, 10), date(2026, 11, 15)),   # 6d
    ],
    # G.PRINC Evangelista — 27 dias
    "gp.evangelista": [
        (date(2026, 7, 14), date(2026, 7, 27)),    # 14d
        (date(2026, 3, 9), date(2026, 3, 15)),      # 7d
        (date(2026, 9, 1), date(2026, 9, 6)),       # 6d
    ],
    # G.PRINC Pais — 27 dias
    "gp.pais": [
        (date(2026, 8, 1), date(2026, 8, 14)),     # 14d
        (date(2026, 4, 14), date(2026, 4, 20)),     # 7d
        (date(2026, 12, 1), date(2026, 12, 6)),     # 6d
    ],
    # G.PRINC Pires — 27 dias
    "gp.pires": [
        (date(2026, 8, 14), date(2026, 8, 27)),    # 14d
        (date(2026, 2, 17), date(2026, 2, 23)),     # 7d
        (date(2026, 10, 20), date(2026, 10, 25)),   # 6d
    ],
    # G.PRINC Bonança — 26 dias
    "gp.bonanca": [
        (date(2026, 7, 7), date(2026, 7, 20)),     # 14d
        (date(2026, 5, 12), date(2026, 5, 17)),     # 6d
        (date(2026, 11, 17), date(2026, 11, 22)),   # 6d
    ],
    # G.PRINC Simão — 25 dias
    "gp.simao": [
        (date(2026, 8, 4), date(2026, 8, 17)),     # 14d
        (date(2026, 6, 9), date(2026, 6, 14)),      # 6d
        (date(2026, 12, 15), date(2026, 12, 19)),   # 5d
    ],
    # GUARDA Botequilha — 27 dias
    "guarda.botequilha": [
        (date(2026, 7, 1), date(2026, 7, 14)),     # 14d
        (date(2026, 3, 23), date(2026, 3, 29)),     # 7d
        (date(2026, 9, 15), date(2026, 9, 20)),     # 6d
    ],
    # GUARDA Gonçalves — 27 dias
    "guarda.goncalves": [
        (date(2026, 7, 14), date(2026, 7, 27)),    # 14d
        (date(2026, 4, 21), date(2026, 4, 27)),     # 7d
        (date(2026, 11, 24), date(2026, 11, 29)),   # 6d
    ],
    # GUARDA Santos — 25 dias
    "guarda.santos": [
        (date(2026, 8, 1), date(2026, 8, 14)),     # 14d
        (date(2026, 5, 26), date(2026, 5, 31)),     # 6d
        (date(2026, 10, 6), date(2026, 10, 10)),    # 5d
    ],
    # GUARDA Pereira — 27 dias
    "guarda.pereira": [
        (date(2026, 8, 18), date(2026, 8, 31)),    # 14d
        (date(2026, 2, 23), date(2026, 2, 28)),     # 6d
        (date(2026, 9, 8), date(2026, 9, 14)),      # 7d
    ],
    # GUARDA Azul — 22 dias
    "guarda.azul": [
        (date(2026, 7, 21), date(2026, 7, 31)),    # 11d
        (date(2026, 8, 1), date(2026, 8, 11)),      # 11d
    ],
    # GUARDA Rosa — 22 dias
    "guarda.rosa": [
        (date(2026, 7, 14), date(2026, 7, 24)),    # 11d
        (date(2026, 9, 1), date(2026, 9, 11)),      # 11d
    ],
    # GUARDA Rodrigues — 22 dias
    "guarda.rodrigues": [
        (date(2026, 8, 18), date(2026, 8, 28)),    # 11d
        (date(2026, 6, 16), date(2026, 6, 26)),     # 11d
    ],
    # GUARDA M. Justo — 22 dias
    "guarda.mjusto": [
        (date(2026, 7, 21), date(2026, 7, 31)),    # 11d
        (date(2026, 10, 13), date(2026, 10, 23)),   # 11d
    ],
    # GUARDA D. Justo — 22 dias
    "guarda.djusto": [
        (date(2026, 8, 11), date(2026, 8, 21)),    # 11d
        (date(2026, 11, 3), date(2026, 11, 13)),    # 11d
    ],
}


def _date_range(start: date, end: date):
    """Yield each date from start to end (inclusive)."""
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


async def seed_castromarim():
    """Replace fake VNG data with real Castro Marim personnel + vacations."""

    async with async_session_factory() as session:
        # ── 1. Find existing station ──────────────────────
        result = await session.execute(select(Station).limit(1))
        station = result.scalar_one_or_none()
        if not station:
            raise SystemExit("No station found. Run the base seed first.")

        station_id = station.id
        logger.info("Updating station %s → Castro Marim", station.code)

        # Update station details
        station.name = "Posto Territorial de Castro Marim"
        station.code = "PT-CMARIM"
        station.comando_territorial = "CT Faro"
        station.destacamento = "DT Tavira"
        station.address = "Castro Marim, Faro"
        station.phone = ""

        # ── 2. Delete existing non-admin users & their shifts ─
        # Get admin user to preserve
        admin_result = await session.execute(
            select(User).where(User.role == UserRole.ADMIN)
        )
        admin = admin_result.scalar_one_or_none()
        admin_id = admin.id if admin else None

        # Delete all shifts
        await session.execute(delete(Shift))
        logger.info("Deleted all existing shifts")

        # Delete all non-admin users
        if admin_id:
            await session.execute(
                delete(User).where(User.id != admin_id)
            )
        else:
            await session.execute(delete(User))
        logger.info("Deleted all non-admin users")

        # ── 3. Find FER shift type ───────────────────────
        fer_result = await session.execute(
            select(ShiftType).where(
                ShiftType.station_id == station_id,
                ShiftType.code == "FER"
            )
        )
        fer_type = fer_result.scalar_one_or_none()
        if not fer_type:
            raise SystemExit("FER shift type not found. Run the base seed first.")

        logger.info("Using FER shift type: %s", fer_type.id)

        # ── 4. Create personnel ──────────────────────────
        user_map = {}  # username → User
        pwd_hash = hash_password(SEED_PASSWORD)

        for posto, n_ordem, nip, full_name, username, role in PERSONNEL:
            user = User(
                id=uuid.uuid4(),
                username=username,
                email=f"{username}@escalaspt.pt",
                password_hash=pwd_hash,
                full_name=full_name,
                nip=nip,
                numero_ordem=n_ordem,
                role=role,
                station_id=station_id,
            )
            session.add(user)
            user_map[username] = user
            logger.info("Created %s: %s (%s)", posto, full_name, username)

        # ── 5. Create vacation shifts (FER) ──────────────
        shift_count = 0
        # Use the comandante as the creator of vacation shifts
        cmdt = user_map.get("saj.povoa")
        cmdt_id = cmdt.id if cmdt else None

        for username, periods in VACATION_2026.items():
            user = user_map.get(username)
            if not user:
                logger.warning("User %s not found, skipping vacations", username)
                continue

            for start_dt, end_dt in periods:
                for day in _date_range(start_dt, end_dt):
                    shift = Shift(
                        id=uuid.uuid4(),
                        user_id=user.id,
                        station_id=station_id,
                        shift_type_id=fer_type.id,
                        date=day,
                        start_datetime=datetime(day.year, day.month, day.day, 0, 0, tzinfo=timezone.utc),
                        end_datetime=datetime(day.year, day.month, day.day, 23, 59, tzinfo=timezone.utc),
                        status=ShiftStatus.PUBLISHED,
                        notes="Férias 2026",
                        created_by=cmdt_id,
                        published_at=datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc),
                    )
                    session.add(shift)
                    shift_count += 1

            total_days = sum(
                (end - start).days + 1 for start, end in periods
            )
            logger.info("  %s: %d dias de férias (%d períodos)",
                        username, total_days, len(periods))

        await session.commit()

        # ── Summary ──────────────────────────────────────
        print("\n" + "=" * 60)
        print("  CASTRO MARIM — SEED COMPLETO")
        print("=" * 60)
        print(f"\n  Posto: {station.name} ({station.code})")
        print(f"  Comando: {station.comando_territorial}")
        print(f"  Destacamento: {station.destacamento}")
        print(f"\n  Efetivo: {len(PERSONNEL)} militares")
        print(f"  Password para todos: {SEED_PASSWORD}")
        print(f"\n  Férias 2026: {shift_count} dias marcados")
        print(f"\n  Utilizadores:")
        for posto, n_ordem, nip, full_name, username, role in PERSONNEL:
            print(f"    {posto:<8} {n_ordem:>4}  {username:<22} {role.value}")
        print("=" * 60 + "\n")


if __name__ == "__main__":
    asyncio.run(seed_castromarim())
