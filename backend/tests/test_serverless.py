"""
The pieces that let the API run on Vercel against Supabase: Realtime signals,
the cron cleanup endpoint, the forwarded client address and the database URL.
"""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from datetime import date, datetime, timezone
from types import SimpleNamespace

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

import app.dependencies as dependencies
import app.main as main
from app.config import Settings, get_settings
from app.models import Station
from app.models.shift import Shift, ShiftStatus
from app.models.user import User
from app.rate_limit import client_address
from app.services import realtime
from tests.conftest import make_auth_header

settings = get_settings()


@pytest.fixture
def realtime_on(monkeypatch):
    monkeypatch.setattr(settings, "SUPABASE_URL", "https://ref.supabase.co")
    monkeypatch.setattr(settings, "SUPABASE_PUBLISHABLE_KEY", "sb_publishable_x")
    monkeypatch.setattr(settings, "REALTIME_CHANNEL_SECRET", "s" * 64)


@pytest.fixture
async def fake_realtime(db_session: AsyncSession):
    """
    A stand-in for Supabase's realtime.send(), same signature, that records
    its calls. Created inside the test's transaction, so it is gone after.
    """
    for statement in (
        "CREATE SCHEMA realtime",
        "CREATE TABLE realtime.sent (payload jsonb, event text, topic text, private boolean)",
        """
        CREATE FUNCTION realtime.send(payload jsonb, event text, topic text, private boolean)
        RETURNS void LANGUAGE sql AS
        $$ INSERT INTO realtime.sent VALUES (payload, event, topic, private) $$
        """,
    ):
        await db_session.execute(text(statement))
    # A savepoint release here (see db_session): a rollback in the code under
    # test must not take the stand-in with it.
    await db_session.commit()

    async def sent() -> list[tuple]:
        result = await db_session.execute(
            text("SELECT topic, event, payload, private FROM realtime.sent ORDER BY topic")
        )
        return [tuple(row) for row in result]

    return sent


class TestRealtimeConfig:
    async def test_disabled_by_default(self, client: AsyncClient, militar_user: User):
        resp = await client.get("/api/realtime/config", headers=make_auth_header(militar_user))
        assert resp.status_code == 200
        assert resp.json() == {"enabled": False}

    async def test_enabled_returns_own_channels(
        self, client: AsyncClient, militar_user: User, realtime_on,
    ):
        resp = await client.get("/api/realtime/config", headers=make_auth_header(militar_user))
        body = resp.json()
        assert body["enabled"] is True
        assert body["url"] == "https://ref.supabase.co"
        assert body["key"] == "sb_publishable_x"
        assert body["channels"] == [
            realtime.user_channel(str(militar_user.id)),
            realtime.station_channel(str(militar_user.station_id)),
        ]

    async def test_requires_auth(self, client: AsyncClient):
        resp = await client.get("/api/realtime/config")
        assert resp.status_code == 401

    async def test_channel_names_do_not_reveal_ids(self, realtime_on):
        user_id = str(uuid.uuid4())
        name = realtime.user_channel(user_id)
        assert user_id not in name
        assert name != realtime.station_channel(user_id)
        assert name == realtime.user_channel(user_id)


class TestSignalsFollowTheTransaction:
    @pytest.fixture
    def use_session(self, monkeypatch, db_session: AsyncSession):
        @asynccontextmanager
        async def factory():
            yield db_session

        monkeypatch.setattr(dependencies, "async_session_factory", factory)

    @staticmethod
    def _request():
        return SimpleNamespace(state=SimpleNamespace(rls_station_id=None))

    async def test_written_in_the_committed_transaction(
        self, use_session, realtime_on, fake_realtime,
    ):
        gen = dependencies.get_db(self._request())
        session = await anext(gen)
        realtime.queue(session, "user-abc", "notification")
        realtime.queue(session, "user-abc", "notification")  # deduplicated
        assert await fake_realtime() == []  # nothing until the handler is done

        with pytest.raises(StopAsyncIteration):
            await anext(gen)

        # Empty payload, public channel: the browser refetches the data.
        assert await fake_realtime() == [("user-abc", "notification", {}, False)]

    async def test_dropped_on_rollback(self, use_session, realtime_on, fake_realtime):
        gen = dependencies.get_db(self._request())
        session = await anext(gen)
        realtime.queue(session, "user-abc", "notification")

        with pytest.raises(RuntimeError):
            await gen.athrow(RuntimeError("handler failed"))

        assert await fake_realtime() == []
        assert "realtime_signals" not in session.info

    async def test_missing_realtime_schema_does_not_lose_the_change(
        self, use_session, realtime_on, db_session: AsyncSession,
    ):
        """No realtime.send() here (a plain Postgres): the write still commits."""
        gen = dependencies.get_db(self._request())
        session = await anext(gen)
        station = Station(
            id=uuid.uuid4(), name="Posto Realtime", code="PT-RT",
            comando_territorial="CT Teste", destacamento="DT Teste",
        )
        session.add(station)
        realtime.queue(session, "station-x", "calendar_sync")

        with pytest.raises(StopAsyncIteration):
            await anext(gen)

        assert await db_session.get(Station, station.id) is not None

    async def test_nothing_queued_when_disabled(self, db_session: AsyncSession):
        realtime.queue(db_session, "user-abc", "notification")
        assert "realtime_signals" not in db_session.info

    async def test_cancelling_a_shift_signals_user_and_station(
        self, client: AsyncClient, db_session: AsyncSession, realtime_on,
        comandante_user: User, militar_user: User, test_station,
    ):
        shift = Shift(
            id=uuid.uuid4(),
            user_id=militar_user.id,
            station_id=test_station.id,
            date=date(2026, 4, 25),
            start_datetime=datetime(2026, 4, 25, 0, 0, tzinfo=timezone.utc),
            end_datetime=datetime(2026, 4, 25, 8, 0, tzinfo=timezone.utc),
            status=ShiftStatus.PUBLISHED,
            created_by=comandante_user.id,
        )
        db_session.add(shift)
        await db_session.flush()

        resp = await client.delete(
            f"/api/shifts/{shift.id}", headers=make_auth_header(comandante_user),
        )
        assert resp.status_code == 204

        # The test app hands handlers this session directly, bypassing
        # get_db, so the queue is still here to look at.
        assert db_session.info["realtime_signals"] == {
            (realtime.user_channel(str(militar_user.id)), "notification"),
            (realtime.station_channel(str(test_station.id)), "calendar_sync"),
        }


class TestCommitBeforeResponse:
    def test_every_db_dependency_is_function_scoped(self):
        """
        With the default "request" scope, the commit in get_db would run
        after the response is sent — see its docstring. One route left on
        the default is enough to bring that back.
        """
        import importlib
        import pkgutil

        from fastapi.routing import APIRoute

        import app.routers

        # The routers themselves, not app.routes: FastAPI resolves included
        # routers lazily now, and app.routes no longer lists their routes.
        routes = [
            route
            for info in pkgutil.iter_modules(app.routers.__path__)
            for route in importlib.import_module(f"app.routers.{info.name}").router.routes
            if isinstance(route, APIRoute)
        ]

        def walk(dependant):
            for dep in dependant.dependencies:
                yield dep
                yield from walk(dep)

        uses_db = [
            (route, dep)
            for route in routes
            for dep in walk(route.dependant)
            if dep.call is dependencies.get_db
        ]
        assert len(uses_db) > 40  # the walk really reached them
        offenders = sorted({route.path for route, dep in uses_db if dep.scope != "function"})
        assert offenders == []

    async def test_emails_awaited_on_serverless(self):
        import asyncio
        from app.services import email_service

        done = asyncio.Event()

        async def slow_send():
            await asyncio.sleep(0.05)
            done.set()

        task = asyncio.create_task(slow_send())
        email_service._in_flight.add(task)
        task.add_done_callback(email_service._in_flight.discard)

        await email_service.drain()
        assert done.is_set()
        assert not email_service._in_flight


class TestCronCleanup:
    @pytest.fixture(autouse=True)
    def stub_cleanup(self, monkeypatch):
        async def fake():
            return 3, 1

        monkeypatch.setattr(main, "cleanup_expired_tokens", fake)

    async def test_hidden_without_secret(self, client: AsyncClient):
        resp = await client.get("/api/internal/cleanup", headers={"Authorization": "Bearer "})
        assert resp.status_code == 404

    async def test_rejects_wrong_secret(self, client: AsyncClient, monkeypatch):
        monkeypatch.setattr(settings, "CRON_SECRET", "right")
        resp = await client.get("/api/internal/cleanup", headers={"Authorization": "Bearer wrong"})
        assert resp.status_code == 404
        resp = await client.get("/api/internal/cleanup")
        assert resp.status_code == 404

    async def test_runs_with_secret(self, client: AsyncClient, monkeypatch):
        monkeypatch.setattr(settings, "CRON_SECRET", "right")
        resp = await client.get("/api/internal/cleanup", headers={"Authorization": "Bearer right"})
        assert resp.status_code == 200
        assert resp.json() == {"expired_tokens": 3, "stale_sessions": 1}


class TestClientAddress:
    @staticmethod
    def _request(forwarded: str | None, peer: str = "10.0.0.9"):
        headers = {"x-forwarded-for": forwarded} if forwarded is not None else {}
        return SimpleNamespace(
            headers=headers, client=SimpleNamespace(host=peer),
        )

    def test_peer_when_self_hosted(self, monkeypatch):
        monkeypatch.setattr(settings, "SERVERLESS", False)
        # Behind nginx, uvicorn already resolved the header into client.host;
        # reading it again here would let a client pick its own bucket.
        assert client_address(self._request("6.6.6.6")) == "10.0.0.9"

    def test_forwarded_on_vercel(self, monkeypatch):
        monkeypatch.setattr(settings, "SERVERLESS", True)
        assert client_address(self._request("203.0.113.7")) == "203.0.113.7"
        assert client_address(self._request("203.0.113.7, 10.1.1.1")) == "203.0.113.7"
        assert client_address(self._request(None)) == "10.0.0.9"


class TestDatabaseUrl:
    @pytest.mark.parametrize("given, expected", [
        (
            "postgresql://postgres.ref:pw@aws-0-eu-west-3.pooler.supabase.com:6543/postgres",
            "postgresql+asyncpg://postgres.ref:pw@aws-0-eu-west-3.pooler.supabase.com:6543/postgres",
        ),
        (
            "postgres://u:p@h:5432/db?sslmode=require",
            "postgresql+asyncpg://u:p@h:5432/db",
        ),
        (
            "postgresql://u:p@h/db?sslmode=require&pgbouncer=true&application_name=x",
            "postgresql+asyncpg://u:p@h/db?application_name=x",
        ),
        (
            "postgresql+asyncpg://u:p@h/db",
            "postgresql+asyncpg://u:p@h/db",
        ),
    ])
    def test_normalised_for_asyncpg(self, given, expected):
        assert Settings(DATABASE_URL=given, APP_ENV="development").DATABASE_URL == expected

    def test_serverless_detected_from_vercel(self, monkeypatch):
        monkeypatch.setenv("VERCEL", "1")
        monkeypatch.delenv("SERVERLESS", raising=False)
        assert Settings(APP_ENV="development").SERVERLESS is True
        monkeypatch.delenv("VERCEL")
        assert Settings(APP_ENV="development").SERVERLESS is False


class TestHealthWithoutRedis:
    async def test_memory_storage_is_not_checked(self, client: AsyncClient, monkeypatch):
        async def db_up():
            return True

        async def redis_must_not_be_called():
            raise AssertionError("memory:// has no server to check")

        monkeypatch.setattr(main, "_check_database", db_up)
        monkeypatch.setattr(main, "_check_redis", redis_must_not_be_called)
        monkeypatch.setattr(settings, "REDIS_URL", "memory://")

        resp = await client.get("/api/health")
        assert resp.status_code == 200
        assert resp.json()["checks"] == {"database": "up"}


class TestRequirementsInSync:
    def test_vercel_copy_matches_backend(self):
        """The root requirements.txt (Vercel) must pin what the Dockerfile does."""
        from pathlib import Path

        root = Path(__file__).resolve().parents[2]

        def pins(path: Path) -> list[str]:
            return sorted(
                line.strip()
                for line in path.read_text().splitlines()
                if line.strip() and not line.strip().startswith("#")
            )

        assert pins(root / "requirements.txt") == pins(root / "backend" / "requirements.txt")
