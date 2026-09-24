"""
Ponte para o Caderno de Serviço: o turno de hoje de um militar, pelo NIP.

O Caderno pergunta, servidor a servidor, "que turno tem este NIP neste dia e
com quem?", para sugerir o serviço no ecrã Hoje ("Tens PAT-T 08–16 com o
Guarda X — iniciar serviço?"). A ponte é só num sentido: nada do Caderno
(ocorrências, identificações) chega aqui.

Autenticação por uma chave partilhada (CADERNO_INTEGRATION_KEY), enviada como
"Authorization: Bearer <chave>". Sem chave configurada o endpoint não existe
(404), como o /api/internal/cleanup. Só se devolvem turnos publicados — um
rascunho da escala ainda não é compromisso de ninguém.
"""

from __future__ import annotations

import hmac
import uuid
from datetime import date, datetime, time, timedelta, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from sqlalchemy import and_, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.dependencies import get_db
from app.models.shift import Shift, ShiftStatus
from app.models.shift_type import ShiftType
from app.models.user import User
from app.rate_limit import limiter

settings = get_settings()

router = APIRouter(prefix="/integracao", tags=["Integração"], include_in_schema=False)


def _verificar_chave(authorization: str | None) -> None:
    chave = settings.CADERNO_INTEGRATION_KEY
    if not chave or not hmac.compare_digest(
        (authorization or "").encode(), f"Bearer {chave}".encode()
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)


def _hora_local(dt: datetime) -> str:
    """
    As horas dos turnos são guardadas como hora de parede, com o rótulo +00
    (ver o frontend, que tira o Z ao mostrar). Devolve-se sem fuso, para o
    Caderno não as converter uma segunda vez.
    """
    return dt.replace(tzinfo=None).isoformat(timespec="minutes")


@router.get("/caderno/turnos")
@limiter.limit("120/minute")
async def turnos_do_dia(
    request: Request,
    nip: str = Query(min_length=1, max_length=20),
    data: date = Query(),
    authorization: str | None = Header(None),
    db: AsyncSession = Depends(get_db, scope="function"),
):
    _verificar_chave(authorization)

    militar = (
        await db.execute(select(User).where(User.nip == nip, User.is_active.is_(True)))
    ).scalar_one_or_none()
    if militar is None or militar.station_id is None:
        return {"turnos": []}

    # A RLS dos turnos filtra pelo posto; sem JWT, o contexto é o do militar.
    await db.execute(
        text(f"SET LOCAL app.current_station_id = '{uuid.UUID(str(militar.station_id))}'")
    )

    # Um turno da noite de ontem que ainda não acabou também é "o de hoje".
    meia_noite = datetime.combine(data, time(0), tzinfo=timezone.utc)
    turnos = (
        await db.execute(
            select(Shift)
            .outerjoin(ShiftType, Shift.shift_type_id == ShiftType.id)
            .options(selectinload(Shift.shift_type))
            .where(
                Shift.user_id == militar.id,
                Shift.status == ShiftStatus.PUBLISHED.value,
                Shift.date.in_([data - timedelta(days=1), data]),
                Shift.end_datetime > meia_noite,
                or_(ShiftType.id.is_(None), ShiftType.is_absence.is_(False)),
            )
            .order_by(Shift.start_datetime)
        )
    ).scalars().all()

    resultado = []
    for turno in turnos:
        # Colegas: no mesmo posto, do mesmo tipo de turno, a horas que se
        # sobrepõem — a patrulha a dois, o atendimento partilhado.
        mesmo_tipo = (
            Shift.shift_type_id == turno.shift_type_id
            if turno.shift_type_id
            else Shift.shift_type_id.is_(None)
        )
        colegas = (
            await db.execute(
                select(User.nip, User.full_name)
                .join(Shift, Shift.user_id == User.id)
                .where(
                    Shift.station_id == turno.station_id,
                    Shift.status == ShiftStatus.PUBLISHED.value,
                    Shift.user_id != militar.id,
                    User.is_active.is_(True),
                    mesmo_tipo,
                    and_(
                        Shift.start_datetime < turno.end_datetime,
                        Shift.end_datetime > turno.start_datetime,
                    ),
                )
                .order_by(User.full_name)
            )
        ).all()
        tipo = turno.shift_type
        resultado.append({
            "codigo": tipo.code if tipo else None,
            "nome": tipo.name if tipo else None,
            "inicio": _hora_local(turno.start_datetime),
            "fim": _hora_local(turno.end_datetime),
            "local": turno.location,
            "notas": turno.notes,
            "colegas": [{"nip": c.nip, "nome": c.full_name} for c in colegas],
        })

    return {"turnos": resultado}
