import time
from typing import AsyncGenerator
import redis.asyncio as aioredis
from backend.app.config import settings
from backend.app.logging import logger

redis_pool = aioredis.ConnectionPool.from_url(
    settings.REDIS_URL,
    decode_responses=True,
    max_connections=10,
)


async def get_redis() -> AsyncGenerator[aioredis.Redis, None]:
    client = aioredis.Redis(connection_pool=redis_pool)
    try:
        yield client
    finally:
        await client.aclose()


async def check_redis_connection() -> dict:
    start_time = time.perf_counter()
    client = aioredis.Redis(connection_pool=redis_pool)
    try:
        response = await client.ping()
        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
        if response:
            return {"status": "HEALTHY", "latency_ms": latency_ms, "error": None}
        return {"status": "UNHEALTHY", "latency_ms": latency_ms, "error": "No PONG received"}
    except Exception as e:
        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
        logger.warning(f"Redis health check failed: {e}")
        return {"status": "UNHEALTHY", "latency_ms": latency_ms, "error": str(e)}
    finally:
        await client.aclose()
