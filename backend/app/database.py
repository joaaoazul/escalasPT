"""
Async SQLAlchemy engine and session factory.
"""

from __future__ import annotations

import uuid
from typing import AsyncGenerator

from sqlalchemy.pool import NullPool
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import get_settings

settings = get_settings()

def _engine_options() -> dict:
    connect_args: dict = {
        "timeout": 10,
        "command_timeout": 30,
    }
    if settings.DATABASE_SSL:
        connect_args["ssl"] = "require"

    if not settings.SERVERLESS:
        return {
            "pool_size": 5,
            "max_overflow": 5,
            "pool_pre_ping": True,
            "pool_recycle": 300,
            "connect_args": connect_args,
        }

    # Serverless: an instance can be frozen mid-idle and thawed minutes later,
    # so a pooled connection is as likely to be dead as alive. Open one per
    # request and let Supabase's pooler (Supavisor) do the pooling.
    #
    # In transaction mode (port 6543) consecutive statements can land on
    # different server connections, so a statement prepared on one is missing
    # on the next. Both caches (asyncpg's and SQLAlchemy's own) are turned
    # off, and the statements SQLAlchemy still prepares get unique names so
    # two can never collide.
    connect_args["statement_cache_size"] = 0
    connect_args["prepared_statement_cache_size"] = 0
    connect_args["prepared_statement_name_func"] = lambda: f"__asyncpg_{uuid.uuid4()}__"
    return {"poolclass": NullPool, "connect_args": connect_args}


engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.APP_DEBUG and settings.APP_ENV == "development",
    **_engine_options(),
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an async DB session."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
