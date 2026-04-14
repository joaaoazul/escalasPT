"""
Seed script — creates initial data for development/testing.
Run with: python -m scripts.seed
Or via Docker: docker compose exec api python -m scripts.seed
"""

from __future__ import annotations

import asyncio
import os
import uuid
from datetime import time

from app.config import get_settings
from app.database import async_session_factory, engine
from app.models import Base, Station, ShiftType, User, UserRole
from app.utils.security import hash_password
from app.utils.logging import setup_logging, get_logger

setup_logging()
logger = get_logger(__name__)

# Seed passwords from env vars — ALL THREE must be set, no insecure defaults
SEED_ADMIN_PASSWORD = os.environ.get("SEED_ADMIN_PASSWORD", "")
SEED_CMDT_PASSWORD = os.environ.get("SEED_CMDT_PASSWORD", "")
SEED_DEFAULT_PASSWORD = os.environ.get("SEED_DEFAULT_PASSWORD", "")

_REQUIRED_SEED_VARS = {
    "SEED_ADMIN_PASSWORD": SEED_ADMIN_PASSWORD,
    "SEED_CMDT_PASSWORD": SEED_CMDT_PASSWORD,
    "SEED_DEFAULT_PASSWORD": SEED_DEFAULT_PASSWORD,
}
_missing = [k for k, v in _REQUIRED_SEED_VARS.items() if not v]
if _missing:
    raise SystemExit(
        f"Seed aborted: set environment variables {', '.join(_missing)} before running."
    )


async def seed():
    """Create seed data: realistic GNR station with full personnel roster."""

    async with async_session_factory() as session:
        # ── Station ───────────────────────────────────────
        station_id = uuid.uuid4()
        station = Station(
            id=station_id,
            name="Posto Territorial de Vila Nova de Gaia",
            code="PT-VNG",
            address="Rua Exemplo, 123 - Vila Nova de Gaia",
            phone="+351 220 000 000",
        )
        session.add(station)
        logger.info("Created station: %s (%s)", station.name, station.code)

        # ── Admin User (sem posto) ────────────────────────
        admin = User(
            id=uuid.uuid4(),
            username="admin",
            email="admin@escalaspt.pt",
            password_hash=hash_password(SEED_ADMIN_PASSWORD),
            full_name="Administrador do Sistema",
            nip="ADM001",
            role=UserRole.ADMIN,
            station_id=None,
        )
        session.add(admin)
        logger.info("Created admin user: %s", admin.username)

        # ── Comandante de Posto (Sargento-Ajudante) ──────
        comandante = User(
            id=uuid.uuid4(),
            username="cmdt.silva",
            email="silva@escalaspt.pt",
            password_hash=hash_password(SEED_CMDT_PASSWORD),
            full_name="Sargento-Ajudante António Silva",
            nip="GNR10001",
            role=UserRole.COMANDANTE,
            station_id=station_id,
        )
        session.add(comandante)
        logger.info("Created comandante: %s", comandante.username)

        # ── Secretaria ────────────────────────────────────
        secretaria = User(
            id=uuid.uuid4(),
            username="guarda.lima",
            email="lima@escalaspt.pt",
            password_hash=hash_password(SEED_DEFAULT_PASSWORD),
            full_name="Guarda Ana Lima",
            nip="GNR20001",
            role=UserRole.SECRETARIA,
            station_id=station_id,
            # default_shift_type_id set after shift types are created
        )
        session.add(secretaria)
        logger.info("Created secretaria: %s", secretaria.username)

        # ── 2 Cabos — NIC (Inquéritos) ───────────────────
        cabos_inq_users = []
        cabos_inq = [
            ("cabo.ferreira", "ferreira@escalaspt.pt", "Cabo Manuel Ferreira",  "GNR30001"),
            ("cabo.oliveira", "oliveira@escalaspt.pt", "Cabo Ricardo Oliveira", "GNR30002"),
        ]
        for username, email, full_name, nip in cabos_inq:
            user = User(
                id=uuid.uuid4(),
                username=username,
                email=email,
                password_hash=hash_password(SEED_DEFAULT_PASSWORD),
                full_name=full_name,
                nip=nip,
                role=UserRole.MILITAR,
                station_id=station_id,
            )
            session.add(user)
            cabos_inq_users.append(user)
            logger.info("Created cabo (inquéritos): %s", username)

        # ── 16 Guardas — Patrulha + Atendimento ──────────
        guardas = [
            ("guarda.costa",      "costa@escalaspt.pt",      "Guarda João Costa",         "GNR40001"),
            ("guarda.santos",     "santos@escalaspt.pt",     "Guarda Pedro Santos",       "GNR40002"),
            ("guarda.pereira",    "pereira@escalaspt.pt",    "Guarda Carlos Pereira",     "GNR40003"),
            ("guarda.rodrigues",  "rodrigues@escalaspt.pt",  "Guarda Tiago Rodrigues",    "GNR40004"),
            ("guarda.almeida",    "almeida@escalaspt.pt",    "Guarda Bruno Almeida",      "GNR40005"),
            ("guarda.nunes",      "nunes@escalaspt.pt",      "Guarda Rui Nunes",          "GNR40006"),
            ("guarda.marques",    "marques@escalaspt.pt",    "Guarda André Marques",      "GNR40007"),
            ("guarda.sousa",      "sousa@escalaspt.pt",      "Guarda Hugo Sousa",         "GNR40008"),
            ("guarda.mendes",     "mendes@escalaspt.pt",     "Guarda Diogo Mendes",       "GNR40009"),
            ("guarda.lopes",      "lopes@escalaspt.pt",      "Guarda Marco Lopes",        "GNR40010"),
            ("guarda.ribeiro",    "ribeiro@escalaspt.pt",    "Guarda Sérgio Ribeiro",     "GNR40011"),
            ("guarda.fernandes",  "fernandes@escalaspt.pt",  "Guarda Paulo Fernandes",    "GNR40012"),
            ("guarda.carvalho",   "carvalho@escalaspt.pt",   "Guarda Daniel Carvalho",    "GNR40013"),
            ("guarda.gomes",      "gomes@escalaspt.pt",      "Guarda Francisco Gomes",    "GNR40014"),
            ("guarda.martins",    "martins@escalaspt.pt",    "Guarda Luís Martins",       "GNR40015"),
            ("guarda.dias",       "dias@escalaspt.pt",       "Guarda Miguel Dias",        "GNR40016"),
        ]
        for username, email, full_name, nip in guardas:
            user = User(
                id=uuid.uuid4(),
                username=username,
                email=email,
                password_hash=hash_password(SEED_DEFAULT_PASSWORD),
                full_name=full_name,
                nip=nip,
                role=UserRole.MILITAR,
                station_id=station_id,
            )
            session.add(user)
            logger.info("Created guarda (patrulha): %s", username)

        # ── Shift Types (GNR standard) ────────────────────
        # fixed_slots=True: AT/OC have fixed 8h daily slots
        # is_absence=True: FER/CONV/MF/DIL/LIC are absences
        shift_types = [
            ShiftType(
                id=uuid.uuid4(),
                station_id=station_id,
                name="Atendimento (00h-08h)",
                code="AT1",
                description="Atendimento ao público — turno 1 (madrugada)",
                start_time=time(0, 0),
                end_time=time(8, 0),
                color="#059669",  # Green
                min_staff=1,
                fixed_slots=True,
            ),
            ShiftType(
                id=uuid.uuid4(),
                station_id=station_id,
                name="Atendimento (08h-16h)",
                code="AT2",
                description="Atendimento ao público — turno 2 (manhã/tarde)",
                start_time=time(8, 0),
                end_time=time(16, 0),
                color="#10B981",  # Emerald
                min_staff=1,
                fixed_slots=True,
            ),
            ShiftType(
                id=uuid.uuid4(),
                station_id=station_id,
                name="Atendimento (16h-00h)",
                code="AT3",
                description="Atendimento ao público — turno 3 (noite)",
                start_time=time(16, 0),
                end_time=time(0, 0),
                color="#047857",  # Dark green
                min_staff=1,
                fixed_slots=True,
            ),
            ShiftType(
                id=uuid.uuid4(),
                station_id=station_id,
                name="Patrulha (00h-08h)",
                code="OC1",
                description="Patrulha às ocorrências — turno 1 (madrugada)",
                start_time=time(0, 0),
                end_time=time(8, 0),
                color="#1E40AF",  # Dark blue
                min_staff=2,
                fixed_slots=True,
            ),
            ShiftType(
                id=uuid.uuid4(),
                station_id=station_id,
                name="Patrulha (08h-16h)",
                code="OC2",
                description="Patrulha às ocorrências — turno 2 (manhã/tarde)",
                start_time=time(8, 0),
                end_time=time(16, 0),
                color="#2563EB",  # Blue
                min_staff=2,
                fixed_slots=True,
            ),
            ShiftType(
                id=uuid.uuid4(),
                station_id=station_id,
                name="Patrulha (16h-00h)",
                code="OC3",
                description="Patrulha às ocorrências — turno 3 (noite)",
                start_time=time(16, 0),
                end_time=time(0, 0),
                color="#1E3A8A",  # Navy
                min_staff=2,
                fixed_slots=True,
            ),
            ShiftType(
                id=uuid.uuid4(),
                station_id=station_id,
                name="Gratificado",
                code="GRAT",
                description="Serviço gratificado (voluntário) — hora definida pelo comandante",
                start_time=time(0, 0),
                end_time=time(0, 0),
                color="#D97706",  # Amber
                min_staff=1,
            ),
            ShiftType(
                id=uuid.uuid4(),
                station_id=station_id,
                name="Tiro",
                code="T",
                description="Serviço de tiro — prática de tiro regulamentar",
                start_time=time(0, 0),
                end_time=time(0, 0),
                color="#DC2626",  # Red
                min_staff=1,
            ),
            ShiftType(
                id=uuid.uuid4(),
                station_id=station_id,
                name="Instrução",
                code="INST",
                description="Instrução / formação — sessão de instrução regulamentar",
                start_time=time(0, 0),
                end_time=time(0, 0),
                color="#9333EA",  # Purple
                min_staff=1,
            ),
            ShiftType(
                id=uuid.uuid4(),
                station_id=station_id,
                name="Inquéritos",
                code="INQ",
                description="Núcleo de Investigação Criminal — inquéritos e diligências",
                start_time=time(9, 0),
                end_time=time(17, 0),
                color="#B45309",  # Amber-dark
                min_staff=1,
                fixed_slots=True,
            ),
            ShiftType(
                id=uuid.uuid4(),
                station_id=station_id,
                name="Secretaria",
                code="SEC",
                description="Serviço de secretaria — expediente administrativo",
                start_time=time(9, 0),
                end_time=time(17, 0),
                color="#F472B6",  # Pink
                min_staff=1,
                fixed_slots=True,
            ),
            ShiftType(
                id=uuid.uuid4(),
                station_id=station_id,
                name="Folga",
                code="F",
                description="Dia de folga",
                start_time=time(0, 0),
                end_time=time(0, 0),
                color="#6B7280",  # Gray
                min_staff=0,
            ),
            # ── Ausências ─────────────────────────────────
            ShiftType(
                id=uuid.uuid4(),
                station_id=station_id,
                name="Férias",
                code="FER",
                description="Férias anuais",
                start_time=time(0, 0),
                end_time=time(0, 0),
                color="#7C3AED",  # Violet
                min_staff=0,
                is_absence=True,
            ),
            ShiftType(
                id=uuid.uuid4(),
                station_id=station_id,
                name="Convalescença",
                code="CONV",
                description="Baixa médica / convalescença",
                start_time=time(0, 0),
                end_time=time(0, 0),
                color="#BE185D",  # Pink
                min_staff=0,
                is_absence=True,
            ),
            ShiftType(
                id=uuid.uuid4(),
                station_id=station_id,
                name="Morte de Familiar",
                code="MF",
                description="Licença por morte de familiar",
                start_time=time(0, 0),
                end_time=time(0, 0),
                color="#78350F",  # Brown
                min_staff=0,
                is_absence=True,
            ),
            ShiftType(
                id=uuid.uuid4(),
                station_id=station_id,
                name="Diligência",
                code="DIL",
                description="Diligência / missão externa",
                start_time=time(0, 0),
                end_time=time(0, 0),
                color="#0369A1",  # Sky
                min_staff=0,
                is_absence=True,
            ),
            ShiftType(
                id=uuid.uuid4(),
                station_id=station_id,
                name="Licença de Estudos",
                code="LIC",
                description="Licença para frequência de cursos / estudos",
                start_time=time(0, 0),
                end_time=time(0, 0),
                color="#0F766E",  # Teal
                min_staff=0,
                is_absence=True,
            ),
        ]

        for st in shift_types:
            session.add(st)
            logger.info("Created shift type: %s (%s)", st.name, st.code)

        # ── Fixed assignments ─────────────────────────────
        # Link secretaria and inquéritos users to their default shift types
        st_by_code = {st.code: st for st in shift_types}
        secretaria.default_shift_type_id = st_by_code["SEC"].id
        for cabo in cabos_inq_users:
            cabo.default_shift_type_id = st_by_code["INQ"].id

        await session.commit()
        logger.info("Seed data created successfully!")

        print("\n" + "=" * 60)
        print("  SEED DATA CREATED SUCCESSFULLY")
        print("=" * 60)
        print(f"\n  Station: {station.name} ({station.code})")
        print(f"\n  Personnel ({1 + 1 + 2 + 16} = 20):")
        print(f"    Admin:       admin              / {SEED_ADMIN_PASSWORD}")
        print(f"    Comandante:  cmdt.silva         / {SEED_CMDT_PASSWORD}  (Sargento-Ajudante)")
        print(f"    Secretaria:  guarda.lima        / {SEED_DEFAULT_PASSWORD}")
        print(f"    Inquéritos:  cabo.ferreira      / {SEED_DEFAULT_PASSWORD}")
        print(f"                 cabo.oliveira      / {SEED_DEFAULT_PASSWORD}")
        print(f"    Patrulha:    guarda.costa … guarda.dias (16 guardas) / {SEED_DEFAULT_PASSWORD}")
        print(f"\n  Shift Types: {len(shift_types)} created")
        print(f"    Serviço:   AT1-3, OC1-3, GRAT, ALOJ, T, INST, INQ, SEC")
        print(f"    Folga:     F")
        print(f"    Ausências: FER, CONV, MF, DIL, LIC")
        print("=" * 60 + "\n")


if __name__ == "__main__":
    asyncio.run(seed())
