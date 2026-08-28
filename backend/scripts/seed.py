"""
Seed the first equipa and an admin user.

Usage (from backend/, with the .env in place):
    python -m scripts.seed --equipa "Posto de Castro Marim" --codigo CTM \
        --username joao --nome "João Azul" --nip 1234567 --email joao@example.pt

The password is read from the CADERNO_SEED_PASSWORD environment variable, never
from the command line (it would land in the shell history).
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import uuid

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings
from app.models import Equipa, User, UserRole
from app.utils.security import hash_password, validate_password_strength

settings = get_settings()


async def seed(args: argparse.Namespace, password: str) -> None:
    # Seeding runs as the table owner; FORCE ROW LEVEL SECURITY applies to the
    # owner too, so the equipa context has to be set explicitly — the same
    # discipline the API follows on every request.
    engine = create_async_engine(
        os.getenv("MIGRATION_DATABASE_URL") or settings.DATABASE_URL, echo=False
    )
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    equipa_id = uuid.uuid4()

    async with factory() as db:
        await db.execute(text(f"SET app.current_equipa_id = '{equipa_id}'"))

        existing = await db.execute(select(Equipa).where(Equipa.codigo == args.codigo))
        equipa = existing.scalar_one_or_none()
        if equipa is None:
            equipa = Equipa(
                id=equipa_id, nome=args.equipa, codigo=args.codigo, unidade=args.unidade
            )
            db.add(equipa)
            await db.flush()
            print(f"Equipa criada: {equipa.codigo} ({equipa.id})")
        else:
            equipa_id = equipa.id
            await db.execute(text(f"SET app.current_equipa_id = '{equipa_id}'"))
            print(f"Equipa já existia: {equipa.codigo} ({equipa.id})")

        user_exists = await db.execute(select(User).where(User.username == args.username))
        if user_exists.scalar_one_or_none() is not None:
            print(f"Utilizador '{args.username}' já existe — nada a fazer.")
            return

        db.add(
            User(
                id=uuid.uuid4(),
                username=args.username,
                email=args.email,
                nome=args.nome,
                nip=args.nip,
                password_hash=hash_password(password),
                role=UserRole.ADMIN,
                equipa_id=equipa_id,
            )
        )
        await db.commit()
        print(f"Utilizador admin criado: {args.username}")

    await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed the first equipa and admin user")
    parser.add_argument("--equipa", required=True)
    parser.add_argument("--codigo", required=True)
    parser.add_argument("--unidade", default=None)
    parser.add_argument("--username", required=True)
    parser.add_argument("--nome", required=True)
    parser.add_argument("--nip", required=True)
    parser.add_argument("--email", required=True)
    args = parser.parse_args()

    password = os.getenv("CADERNO_SEED_PASSWORD", "")
    if not password:
        print("FATAL: set CADERNO_SEED_PASSWORD in the environment.", file=sys.stderr)
        sys.exit(1)

    issues = validate_password_strength(password)
    if issues:
        print("FATAL: password rejected:\n  - " + "\n  - ".join(issues), file=sys.stderr)
        sys.exit(1)

    asyncio.run(seed(args, password))


if __name__ == "__main__":
    main()
