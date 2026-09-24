"""
Ponte para o Caderno de Serviço: GET /api/integracao/caderno/turnos.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ShiftType, Station, User, UserRole
from app.models.shift import Shift
from app.routers import integracao
from app.utils.security import hash_password

CHAVE = "chave-de-teste-da-integracao"
HOJE = date(2026, 4, 15)
URL = "/api/integracao/caderno/turnos"


@pytest.fixture(autouse=True)
def _chave(monkeypatch):
    monkeypatch.setattr(integracao.settings, "CADERNO_INTEGRATION_KEY", CHAVE)


def _auth(chave: str = CHAVE) -> dict:
    return {"Authorization": f"Bearer {chave}"}


def _dt(d: date, h: int) -> datetime:
    return datetime(d.year, d.month, d.day, h, tzinfo=timezone.utc)


async def _turno(db: AsyncSession, user: User, tipo: ShiftType | None, d: date, h0: int, h1: int,
                 criador: User, estado: str = "published", fim: datetime | None = None) -> Shift:
    turno = Shift(
        id=uuid.uuid4(), user_id=user.id, station_id=user.station_id,
        shift_type_id=tipo.id if tipo else None, date=d,
        start_datetime=_dt(d, h0), end_datetime=fim or _dt(d, h1),
        status=estado, created_by=criador.id, location="Zona industrial",
    )
    db.add(turno)
    await db.flush()
    return turno


async def _militar(db: AsyncSession, station: Station, nip: str, nome: str, activo: bool = True) -> User:
    user = User(
        id=uuid.uuid4(), username=f"u{nip}", email=f"{nip}@gnr.pt",
        password_hash=hash_password("TestMil123!"), full_name=nome, nip=nip,
        role=UserRole.MILITAR, station_id=station.id, is_active=activo,
    )
    db.add(user)
    await db.flush()
    return user


async def test_sem_chave_configurada_nao_existe(client: AsyncClient, monkeypatch):
    monkeypatch.setattr(integracao.settings, "CADERNO_INTEGRATION_KEY", "")
    r = await client.get(URL, params={"nip": "MIL999", "data": HOJE.isoformat()}, headers=_auth(""))
    assert r.status_code == 404


async def test_chave_errada_ou_token_de_utilizador_recusados(client: AsyncClient, militar_user: User):
    from tests.conftest import make_auth_header

    params = {"nip": militar_user.nip, "data": HOJE.isoformat()}
    assert (await client.get(URL, params=params)).status_code == 404
    assert (await client.get(URL, params=params, headers=_auth("outra"))).status_code == 404
    # Um JWT de utilizador válido não abre a ponte.
    assert (await client.get(URL, params=params, headers=make_auth_header(militar_user))).status_code == 404


async def test_turno_de_hoje_com_os_colegas_do_mesmo_tipo(
    client: AsyncClient, db_session: AsyncSession, test_station: Station,
    test_shift_types: list[ShiftType], comandante_user: User, militar_user: User, militar_user_2: User,
):
    tarde = test_shift_types[1]  # PAT-T 08–16
    await _turno(db_session, militar_user, tarde, HOJE, 8, 16, comandante_user)
    await _turno(db_session, militar_user_2, tarde, HOJE, 8, 16, comandante_user)
    # Outro tipo à mesma hora (atendimento), um rascunho e um inactivo: nenhum é colega.
    outro_tipo = ShiftType(
        id=uuid.uuid4(), station_id=test_station.id, name="Atendimento", code="ATD",
        start_time=tarde.start_time, end_time=tarde.end_time, color="#000000",
    )
    db_session.add(outro_tipo)
    await db_session.flush()
    atd = await _militar(db_session, test_station, "MIL100", "No Atendimento")
    await _turno(db_session, atd, outro_tipo, HOJE, 8, 16, comandante_user)
    rasc = await _militar(db_session, test_station, "MIL101", "Em Rascunho")
    await _turno(db_session, rasc, tarde, HOJE, 8, 16, comandante_user, estado="draft")
    saiu = await _militar(db_session, test_station, "MIL102", "Inactivo", activo=False)
    await _turno(db_session, saiu, tarde, HOJE, 8, 16, comandante_user)

    r = await client.get(URL, params={"nip": militar_user.nip, "data": HOJE.isoformat()}, headers=_auth())
    assert r.status_code == 200, r.text
    turnos = r.json()["turnos"]
    assert len(turnos) == 1
    t = turnos[0]
    assert (t["codigo"], t["inicio"], t["fim"]) == ("PAT-T", "2026-04-15T08:00", "2026-04-15T16:00")
    assert t["local"] == "Zona industrial"
    assert t["colegas"] == [{"nip": militar_user_2.nip, "nome": militar_user_2.full_name}]


async def test_so_publicados_sem_ausencias_e_a_noite_de_ontem_conta(
    client: AsyncClient, db_session: AsyncSession, test_station: Station,
    test_shift_types: list[ShiftType], comandante_user: User, militar_user: User,
):
    noite = test_shift_types[2]  # PAT-N 16–00
    ontem = date(2026, 4, 14)
    # Noite de ontem que acaba hoje às 02:00 → conta; a que acabou à meia-noite, não.
    await _turno(db_session, militar_user, noite, ontem, 22, 0, comandante_user, fim=_dt(HOJE, 2))
    await _turno(db_session, militar_user, noite, ontem, 16, 0, comandante_user, fim=_dt(HOJE, 0))
    # Rascunho de hoje: ainda não é compromisso.
    await _turno(db_session, militar_user, test_shift_types[1], HOJE, 8, 16, comandante_user, estado="draft")
    # Férias: não é serviço.
    ferias = ShiftType(
        id=uuid.uuid4(), station_id=test_station.id, name="Férias", code="FER",
        start_time=test_shift_types[0].start_time, end_time=test_shift_types[0].start_time,
        color="#999999", is_absence=True,
    )
    db_session.add(ferias)
    await db_session.flush()
    await _turno(db_session, militar_user, ferias, HOJE, 0, 23, comandante_user)

    r = await client.get(URL, params={"nip": militar_user.nip, "data": HOJE.isoformat()}, headers=_auth())
    assert r.status_code == 200
    turnos = r.json()["turnos"]
    assert [(t["inicio"], t["fim"]) for t in turnos] == [("2026-04-14T22:00", "2026-04-15T02:00")]


async def test_nip_desconhecido_devolve_vazio(client: AsyncClient):
    r = await client.get(URL, params={"nip": "NAOEXISTE", "data": HOJE.isoformat()}, headers=_auth())
    assert r.status_code == 200
    assert r.json() == {"turnos": []}
