"""
Test fixtures for the EscalasPT backend.
Provides: async DB session, HTTP client, authenticated users per role.
"""

from __future__ import annotations

import os
import re
import uuid
from datetime import time
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

# Settings are read once, at import time, so these have to be in place before
# app.config is imported below. They only fill in what the suite needs and
# never override a value the environment already set.
os.environ.setdefault("APP_ENV", "development")
os.environ.setdefault(
    "JWT_SECRET_KEY",
    "test-only-secret-not-used-anywhere-outside-the-test-suite" * 2,
)
# A fixed Fernet key, so the TOTP tests run from a fresh clone with no setup.
os.environ.setdefault(
    "TOTP_ENCRYPTION_KEY", "ZXNjYWxhc3B0LXRlc3QtdG90cC1rZXktMzJieXRlcyE="
)

from app.config import get_settings  # noqa: E402
from app.database import get_async_session
from app.dependencies import get_db
from app.main import create_app
from app.models import Base, Station, ShiftType, User, UserRole
from app.models.user import ActiveSession
from app.rate_limit import limiter
from app.utils.security import create_access_token, hash_password

settings = get_settings()


# ── Database ──────────────────────────────────────────────

def _resolve_test_db_url() -> str:
    """
    The database the tests are allowed to destroy.

    The session fixture ends in ``drop_all()``, so pointing it at the database
    the application actually uses empties that database. It used to be exactly
    ``settings.DATABASE_URL`` — a ``pytest`` run with a real ``.env`` in place
    was enough to wipe it. So: take the app's URL, suffix the database name
    with ``_test``, and refuse to start if the name that comes out doesn't say
    ``_test``. ``TEST_DATABASE_URL`` overrides, and is held to the same rule.
    """
    explicit = os.getenv("TEST_DATABASE_URL")
    url = make_url(explicit or settings.DATABASE_URL)
    if not explicit:
        url = url.set(database=f"{url.database}_test")

    name = url.database or ""
    if not name.endswith("_test"):
        raise RuntimeError(
            f"Refusing to run the tests against the database {name!r}: these "
            "fixtures drop every table when the session ends, so the name has "
            "to end in '_test'."
        )
    if not re.fullmatch(r"[A-Za-z0-9_]+", name):
        raise RuntimeError(f"Unusable test database name: {name!r}")

    return url.render_as_string(hide_password=False)


TEST_DB_URL = _resolve_test_db_url()


async def _ensure_test_database_exists() -> None:
    """Create the _test database on first run, so a fresh clone just works."""
    target = make_url(TEST_DB_URL)
    # CREATE DATABASE can't run inside a transaction, hence AUTOCOMMIT, and it
    # can't run from the database being created, hence the admin connection.
    admin_url = target.set(database="postgres").render_as_string(hide_password=False)
    engine = create_async_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        async with engine.connect() as conn:
            exists = await conn.scalar(
                text("SELECT 1 FROM pg_database WHERE datname = :name"),
                {"name": target.database},
            )
            if not exists:
                # The name is our own, and _resolve_test_db_url already checked
                # it against [A-Za-z0-9_]+ — an identifier can't be bound.
                await conn.execute(text(f'CREATE DATABASE "{target.database}"'))
    finally:
        await engine.dispose()


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    """Create a test database engine."""
    await _ensure_test_database_exists()
    engine = create_async_engine(TEST_DB_URL, echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """
    A session whose writes never outlive the test.

    The route handlers call ``db.commit()`` themselves, and the ``app`` fixture
    hands them this very session — so the old ``session.rollback()`` at the end
    had nothing left to undo, and every test leaked its rows into the next one.
    The tell was the second test to ask for the ``PT-TST`` station dying on a
    unique violation; each test passed on its own and the suite failed as a
    whole.

    Binding the session to a connection-level transaction and letting its
    commits land as savepoints keeps the application code honest — it really
    does commit — while this fixture still rolls the whole thing back.
    """
    async with test_engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(
            bind=connection,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )
        try:
            yield session
        finally:
            await session.close()
            if transaction.is_active:
                await transaction.rollback()


# ── Application ───────────────────────────────────────────

@pytest.fixture(autouse=True)
def _disable_rate_limiting():
    """
    Rate limiting is off for the suite.

    Every test drives the app from the same client address, so the global
    60/minute default would start returning 429 partway through a run and
    make failures depend on test order. It also needs Redis, which the suite
    otherwise doesn't. The limits are exercised against a real Redis instead.
    """
    limiter.enabled = False
    yield
    limiter.enabled = True


@pytest_asyncio.fixture
async def app(db_session):
    """Create test application with overridden DB dependency."""
    application = create_app()

    async def override_get_db():
        yield db_session

    application.dependency_overrides[get_db] = override_get_db
    return application


@pytest_asyncio.fixture
async def client(app) -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP client for testing."""
    transport = ASGITransport(app=app)
    # https, not http: the refresh cookie is set Secure, and over a plain http
    # base_url httpx drops it, so anything exercising the refresh flow fails
    # for a reason that has nothing to do with the code under test.
    async with AsyncClient(transport=transport, base_url="https://test") as ac:
        yield ac


# ── Seed Data ─────────────────────────────────────────────


def _session_id_for(user: User) -> str:
    """
    The session id a test user's token carries. Derived from the user id so
    that make_auth_header — which has no database to write to — and
    _with_active_session agree without passing anything between them. Fits
    ActiveSession.session_id, which is a 36-char column.
    """
    return str(user.id)


async def _with_active_session(db_session: AsyncSession, user: User) -> User:
    """
    Register the session that the user's token will claim.

    get_current_user checks, on every request, that the token's ``sid`` still
    matches a live ActiveSession row. The test fixtures minted tokens without
    one, so every authenticated request in the suite came back 401.
    """
    db_session.add(ActiveSession(user_id=user.id, session_id=_session_id_for(user)))
    await db_session.flush()
    return user

@pytest_asyncio.fixture
async def test_station(db_session: AsyncSession) -> Station:
    """Create a test station."""
    station = Station(
        id=uuid.uuid4(),
        name="Posto de Teste",
        code="PT-TST",
        comando_territorial="Comando de Teste",
        destacamento="Destacamento de Teste",
        address="Rua de Teste, 1",
    )
    db_session.add(station)
    await db_session.flush()
    return station


@pytest_asyncio.fixture
async def test_shift_types(db_session: AsyncSession, test_station: Station) -> list[ShiftType]:
    """Create standard GNR shift types for tests."""
    types = [
        ShiftType(
            id=uuid.uuid4(),
            station_id=test_station.id,
            name="Patrulha (Manhã)",
            code="PAT-M",
            start_time=time(0, 0),
            end_time=time(8, 0),
            color="#1E40AF",
        ),
        ShiftType(
            id=uuid.uuid4(),
            station_id=test_station.id,
            name="Patrulha (Tarde)",
            code="PAT-T",
            start_time=time(8, 0),
            end_time=time(16, 0),
            color="#2563EB",
        ),
        ShiftType(
            id=uuid.uuid4(),
            station_id=test_station.id,
            name="Patrulha (Noite)",
            code="PAT-N",
            start_time=time(16, 0),
            end_time=time(0, 0),
            color="#1E3A8A",
        ),
    ]
    for t in types:
        db_session.add(t)
    await db_session.flush()
    return types


@pytest_asyncio.fixture
async def admin_user(db_session: AsyncSession) -> User:
    """Create an admin user."""
    user = User(
        id=uuid.uuid4(),
        username="test_admin",
        email="test_admin@gnr.pt",
        password_hash=hash_password("TestAdmin123!"),
        full_name="Admin de Teste",
        nip="ADM999",
        role=UserRole.ADMIN,
        station_id=None,
    )
    db_session.add(user)
    await db_session.flush()
    return await _with_active_session(db_session, user)


@pytest_asyncio.fixture
async def comandante_user(db_session: AsyncSession, test_station: Station) -> User:
    """Create a comandante user."""
    user = User(
        id=uuid.uuid4(),
        username="test_comandante",
        email="test_cmd@gnr.pt",
        password_hash=hash_password("TestCmd123!"),
        full_name="Comandante de Teste",
        nip="CMD999",
        role=UserRole.COMANDANTE,
        station_id=test_station.id,
    )
    db_session.add(user)
    await db_session.flush()
    return await _with_active_session(db_session, user)


@pytest_asyncio.fixture
async def militar_user(db_session: AsyncSession, test_station: Station) -> User:
    """Create a militar user."""
    user = User(
        id=uuid.uuid4(),
        username="test_militar",
        email="test_mil@gnr.pt",
        password_hash=hash_password("TestMil123!"),
        full_name="Militar de Teste",
        nip="MIL999",
        role=UserRole.MILITAR,
        station_id=test_station.id,
    )
    db_session.add(user)
    await db_session.flush()
    return await _with_active_session(db_session, user)


@pytest_asyncio.fixture
async def militar_user_2(db_session: AsyncSession, test_station: Station) -> User:
    """Create a second militar user for swap tests."""
    user = User(
        id=uuid.uuid4(),
        username="test_militar2",
        email="test_mil2@gnr.pt",
        password_hash=hash_password("TestMil123!"),
        full_name="Militar de Teste 2",
        nip="MIL998",
        role=UserRole.MILITAR,
        station_id=test_station.id,
    )
    db_session.add(user)
    await db_session.flush()
    return await _with_active_session(db_session, user)


# ── Auth Helpers ──────────────────────────────────────────


def make_auth_header(user: User) -> dict:
    """Create an Authorization header for a user."""
    token = create_access_token(
        user_id=str(user.id),
        role=user.role.value,
        station_id=str(user.station_id) if user.station_id else None,
        session_id=_session_id_for(user),
    )
    return {"Authorization": f"Bearer {token}"}
