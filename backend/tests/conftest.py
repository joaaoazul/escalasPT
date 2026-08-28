"""
Test fixtures.

Two differences from escalasPT's conftest, both deliberate:

  - The suite runs against TEST_DATABASE_URL, which Settings refuses unless the
    database name ends in `_test`. escalasPT points the suite at DATABASE_URL
    and calls drop_all, so running pytest with a dev .env wipes the dev DB.
  - The schema is built by running the real Alembic migrations, not
    metadata.create_all, because the RLS policies and the audit_logs REVOKE
    only exist in migrations — testing create_all would test a schema that
    never runs anywhere.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from fastapi import Request
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import get_settings
from app.dependencies import get_db
from app.routers import auth as auth_router
from app.main import create_app
from app.models import Base, Equipa, User, UserRole
from app.utils.security import hash_password

settings = get_settings()

# The application connects as the limited role; the owner is used only for
# schema work. In CI these are two different roles, which is what lets
# test_audit.py prove the audit log is append-only for the role that matters.
APP_DB_URL = settings.TEST_DATABASE_URL
ADMIN_DB_URL = os.getenv("MIGRATION_DATABASE_URL") or APP_DB_URL
RUNS_AS_LIMITED_ROLE = ADMIN_DB_URL != APP_DB_URL


def _run_migrations(url: str) -> None:
    """
    Apply every migration, exactly as production does — the RLS policies and the
    audit_logs REVOKE live in migrations, so a metadata.create_all schema would
    be testing something that never runs anywhere.
    """
    from alembic import command
    from alembic.config import Config

    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", url)
    os.environ["MIGRATION_DATABASE_URL"] = url
    command.upgrade(cfg, "head")


async def _reset_schema(url: str) -> None:
    engine = create_async_engine(url, poolclass=NullPool)
    try:
        async with engine.begin() as conn:
            await conn.execute(text("DROP SCHEMA public CASCADE"))
            await conn.execute(text("CREATE SCHEMA public"))
            # The limited role's grants live on the schema, so they come back
            # with it (in deployment this is scripts/init_db.sql's job).
            await conn.execute(text("GRANT USAGE ON SCHEMA public TO caderno_app"))
            await conn.execute(
                text(
                    "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
                    "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO caderno_app"
                )
            )
            await conn.execute(
                text(
                    "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
                    "GRANT USAGE, SELECT ON SEQUENCES TO caderno_app"
                )
            )
    finally:
        await engine.dispose()


@pytest.fixture(scope="session", autouse=True)
def schema():
    """Build the schema once per run, outside any test event loop."""
    if RUNS_AS_LIMITED_ROLE:
        asyncio.run(_reset_schema(ADMIN_DB_URL))
    _run_migrations(ADMIN_DB_URL)
    yield


@pytest_asyncio.fixture
async def admin_engine(schema):
    """Owner connection — truncation between tests."""
    engine = create_async_engine(ADMIN_DB_URL, poolclass=NullPool)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def test_engine(schema):
    """Application connection — the limited role, as in production."""
    engine = create_async_engine(APP_DB_URL, poolclass=NullPool)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def session_factory(test_engine):
    return async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture
async def db_session(session_factory) -> AsyncGenerator[AsyncSession, None]:
    """A session with no RLS context — the deny-by-default case."""
    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture(autouse=True)
async def clean_tables(admin_engine) -> AsyncGenerator[None, None]:
    """Truncate before each test; the schema is built once per run."""
    async with admin_engine.begin() as conn:
        await conn.execute(
            text(
                "TRUNCATE audit_logs, active_sessions, refresh_tokens, users, equipas "
                "RESTART IDENTITY CASCADE"
            )
        )
    yield


@pytest_asyncio.fixture
async def equipa(session_factory) -> Equipa:
    """An equipa, created with its own RLS context set (as the API would)."""
    equipa_id = uuid.uuid4()
    async with session_factory() as db:
        await db.execute(text(f"SET LOCAL app.current_equipa_id = '{equipa_id}'"))
        obj = Equipa(id=equipa_id, nome="Posto de Teste", codigo="TST", unidade="DTer Teste")
        db.add(obj)
        await db.commit()
    return Equipa(id=equipa_id, nome="Posto de Teste", codigo="TST", unidade="DTer Teste")


TEST_PASSWORD = "Caderno-2026-Teste!"


@pytest_asyncio.fixture
async def agente(session_factory, equipa) -> User:
    user_id = uuid.uuid4()
    async with session_factory() as db:
        db.add(
            User(
                id=user_id,
                username="agente",
                email="agente@example.pt",
                nome="Agente de Teste",
                nip="1000001",
                password_hash=hash_password(TEST_PASSWORD),
                role=UserRole.AGENTE,
                equipa_id=equipa.id,
            )
        )
        await db.commit()
    async with session_factory() as db:
        return await db.get(User, user_id)


@pytest_asyncio.fixture
async def app(session_factory):
    """The real app, with get_db swapped for one bound to the test engine."""
    application = create_app()

    # The login limiter keys on client IP, and every test here shares one. Left
    # on, the sixth login in the whole run would 429 instead of exercising what
    # the test is about. test_login_rate_limit turns it back on deliberately.
    auth_router.limiter.enabled = False

    async def _test_get_db(request: Request):
        async with session_factory() as session:
            try:
                raw = getattr(request.state, "rls_equipa_id", None)
                value = ""
                if raw:
                    try:
                        value = str(uuid.UUID(raw))
                    except (ValueError, AttributeError):
                        value = ""
                await session.execute(text(f"SET LOCAL app.current_equipa_id = '{value}'"))
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    application.dependency_overrides[get_db] = _test_get_db
    return application


@pytest_asyncio.fixture
async def client(app) -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="https://caderno.test"
    ) as ac:
        yield ac
