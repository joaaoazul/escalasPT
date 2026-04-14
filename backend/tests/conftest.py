"""
Test fixtures for the Shifting backend.
Provides: async DB session, HTTP client, authenticated users per role.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import time
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings
from app.database import get_async_session
from app.dependencies import get_db
from app.main import create_app
from app.models import Base, Station, ShiftType, User, UserRole
from app.utils.security import create_access_token, hash_password

settings = get_settings()


# ── Async event loop ──────────────────────────────────────

@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for the test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ── Database ──────────────────────────────────────────────

# Use the same DB URL but with a test database suffix
TEST_DB_URL = settings.DATABASE_URL


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    """Create a test database engine."""
    engine = create_async_engine(TEST_DB_URL, echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Provide a clean DB session per test with transaction rollback."""
    session_factory = async_sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )

    async with session_factory() as session:
        async with session.begin():
            yield session
            await session.rollback()


# ── Application ───────────────────────────────────────────

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
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ── Seed Data ─────────────────────────────────────────────

@pytest_asyncio.fixture
async def test_station(db_session: AsyncSession) -> Station:
    """Create a test station."""
    station = Station(
        id=uuid.uuid4(),
        name="Posto de Teste",
        code="PT-TST",
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
    return user


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
    return user


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
    return user


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
    return user


# ── Auth Helpers ──────────────────────────────────────────


def make_auth_header(user: User) -> dict:
    """Create an Authorization header for a user."""
    token = create_access_token(
        user_id=str(user.id),
        role=user.role.value,
        station_id=str(user.station_id) if user.station_id else None,
    )
    return {"Authorization": f"Bearer {token}"}
