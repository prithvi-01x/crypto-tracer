import time
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import text
from backend.app.config import settings
from backend.app.logging import logger

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    future=True,
    pool_pre_ping=True,
)

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
