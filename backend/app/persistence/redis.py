import time
import asyncio
from typing import AsyncGenerator, Dict, Optional
import redis.asyncio as aioredis
from backend.app.config import settings
from backend.app.logging import logger

_pools: Dict[Optional[asyncio.AbstractEventLoop], aioredis.ConnectionPool] = {}


def get_redis_pool() -> aioredis.ConnectionPool:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop not in _pools or _pools[loop] is None:
        _pools[loop] = aioredis.ConnectionPool.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            max_connections=10,
        )
    return _pools[loop]


class _RedisPoolProxy:
    def __getattr__(self, name):
        return getattr(get_redis_pool(), name)


redis_pool = _RedisPoolProxy()


async def get_redis() -> AsyncGenerator[aioredis.Redis, None]:
    pool = get_redis_pool()
    client = aioredis.Redis(connection_pool=pool)
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
