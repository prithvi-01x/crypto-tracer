import time
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import text
from backend.app.config import settings
from backend.app.logging import logger

import uuid
from sqlalchemy.pool import NullPool, StaticPool

def _create_engine(
    url: str = None,
    pool_size: int = None,
    max_overflow: int = None,
    pool_recycle: int = None,
    pool_pre_ping: bool = None,
    pgbouncer_mode: bool = None,
):
    db_url = url or (
        settings.DATABASE_URL.get_secret_value()
        if hasattr(settings.DATABASE_URL, "get_secret_value")
        else str(settings.DATABASE_URL)
    )
    is_sqlite = db_url.startswith("sqlite")

    p_pre_ping = settings.DB_POOL_PRE_PING if pool_pre_ping is None else pool_pre_ping
    p_size = settings.DB_POOL_SIZE if pool_size is None else pool_size
    p_max_overflow = settings.DB_MAX_OVERFLOW if max_overflow is None else max_overflow
    p_recycle = settings.DB_POOL_RECYCLE if pool_recycle is None else pool_recycle
    p_pgbouncer = settings.DB_PGBOUNCER_MODE if pgbouncer_mode is None else pgbouncer_mode

    engine_kwargs = {
        "echo": False,
        "future": True,
        "pool_pre_ping": p_pre_ping,
    }

    if is_sqlite:
        if ":memory:" in db_url:
            engine_kwargs["poolclass"] = StaticPool
        # SQLite engines do not accept pool_size, max_overflow, or pool_recycle
    else:
        # Production PostgreSQL (QueuePool)
        engine_kwargs["pool_recycle"] = p_recycle

        if p_pgbouncer:
            # PgBouncer transaction-pooling readiness
            engine_kwargs["poolclass"] = NullPool
            engine_kwargs["connect_args"] = {
                "statement_cache_size": 0,
                "prepared_statement_cache_size": 0,
                "prepared_statement_name_func": lambda: f"__asyncpg_{uuid.uuid4()}__",
            }
        else:
            engine_kwargs["pool_size"] = p_size
            engine_kwargs["max_overflow"] = p_max_overflow
            if "asyncpg" in db_url:
                engine_kwargs["connect_args"] = {
                    "server_settings": {"jit": "off"},
                }

    return create_async_engine(db_url, **engine_kwargs)

engine = _create_engine()

async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        try:
            yield session
        finally:
            await session.close()


async def check_db_connection() -> dict:
    start_time = time.perf_counter()
    try:
        async with async_session_factory() as session:
            result = await session.execute(text("SELECT 1"))
            val = result.scalar()
            latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
            if val == 1:
                return {"status": "HEALTHY", "latency_ms": latency_ms, "error": None}
            return {"status": "UNHEALTHY", "latency_ms": latency_ms, "error": "Unexpected query result"}
    except Exception as e:
        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
        logger.warning(f"Database health check failed: {e}")
        return {"status": "UNHEALTHY", "latency_ms": latency_ms, "error": str(e)}
