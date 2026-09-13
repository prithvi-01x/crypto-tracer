import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, Set

logger = logging.getLogger("crypto_tracer.worker.heartbeat")

# Process-local in-memory lock registry for tests when Redis is absent
_in_memory_locks: Dict[str, str] = {}
_in_memory_lock_times: Dict[str, float] = {}
_in_memory_lock_mutex = asyncio.Lock()


class HeartbeatManager:
    """
    Manages worker heartbeats, distributed execution locks, and progress snapshots.
    Guarantees that active jobs maintain liveness signals and stale zombie jobs can be detected.
    """

    def __init__(
        self,
        trace_id: str,
        worker_id: str,
        redis_client: Optional[Any] = None,
        lock_ttl: int = 30,
        heartbeat_interval: float = 10.0,
    ):
        self.trace_id = trace_id
        self.worker_id = worker_id
        self.redis = redis_client
        self.lock_ttl = lock_ttl
        self.heartbeat_interval = heartbeat_interval
        self._task: Optional[asyncio.Task] = None
        self._running = False

    @classmethod
    async def acquire_lock(
        cls,
        trace_id: str,
        worker_id: str,
        redis_client: Optional[Any] = None,
        lock_ttl: int = 30,
    ) -> bool:
        """Attempt to acquire distributed execution lock. Returns True if acquired."""
        lock_key = f"trace:lock:{trace_id}"
        if redis_client is not None:
            try:
                acquired = await redis_client.set(lock_key, worker_id, nx=True, ex=lock_ttl)
                return bool(acquired)
            except Exception as e:
                logger.warning(f"Redis lock acquisition error for {trace_id}: {e}")

        # Fallback to in-memory lock registry
        async with _in_memory_lock_mutex:
            now = asyncio.get_event_loop().time()
            if lock_key in _in_memory_locks:
                expire_at = _in_memory_lock_times.get(lock_key, 0)
                if now < expire_at:
                    return False  # Still locked by another worker
            _in_memory_locks[lock_key] = worker_id
            _in_memory_lock_times[lock_key] = now + lock_ttl
            return True

    @classmethod
    async def release_lock(
        cls,
        trace_id: str,
        worker_id: str,
        redis_client: Optional[Any] = None,
    ) -> None:
        """Release distributed execution lock."""
        lock_key = f"trace:lock:{trace_id}"
        if redis_client is not None:
            try:
                await redis_client.delete(lock_key)
            except Exception as e:
                logger.warning(f"Redis lock release error: {e}")

        async with _in_memory_lock_mutex:
            if _in_memory_locks.get(lock_key) == worker_id:
                _in_memory_locks.pop(lock_key, None)
                _in_memory_lock_times.pop(lock_key, None)

    async def start(self):
        """Start the periodic heartbeat pulse task."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._heartbeat_loop())

    async def stop(self):
        """Stop the heartbeat pulse task and release lock."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        # Cleanup lock and heartbeat key
        await self.release_lock(self.trace_id, self.worker_id, self.redis)
        if self.redis is not None:
            try:
                await self.redis.delete(f"trace:heartbeat:{self.trace_id}")
            except Exception:
                pass

    async def _heartbeat_loop(self):
        lock_key = f"trace:lock:{self.trace_id}"
        heartbeat_key = f"trace:heartbeat:{self.trace_id}"

        while self._running:
            try:
                await asyncio.sleep(self.heartbeat_interval)
                now_iso = datetime.now(timezone.utc).isoformat()
                heartbeat_payload = json.dumps({
                    "worker_id": self.worker_id,
                    "trace_id": self.trace_id,
                    "timestamp": now_iso,
                })

                if self.redis is not None:
                    await self.redis.expire(lock_key, self.lock_ttl)
                    await self.redis.set(heartbeat_key, heartbeat_payload, ex=self.lock_ttl)
                else:
                    async with _in_memory_lock_mutex:
                        now = asyncio.get_event_loop().time()
                        if _in_memory_locks.get(lock_key) == self.worker_id:
                            _in_memory_lock_times[lock_key] = now + self.lock_ttl

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"Heartbeat pulse failed for {self.trace_id}: {e}")

    @classmethod
    async def save_progress_snapshot(
        cls,
        trace_id: str,
        snapshot: Dict[str, Any],
        redis_client: Optional[Any] = None,
        ttl: int = 3600,
    ):
        """Persist latest progress metrics snapshot."""
        if redis_client is not None:
            try:
                key = f"trace:progress:{trace_id}"
                await redis_client.set(key, json.dumps(snapshot), ex=ttl)
            except Exception as e:
                logger.warning(f"Failed to save progress snapshot to Redis: {e}")

    @classmethod
    async def save_checkpoint(
        cls,
        trace_id: str,
        checkpoint: Dict[str, Any],
        redis_client: Optional[Any] = None,
        ttl: int = 86400,
    ):
        """Persist intermediate graph checkpoint for resume/partial recovery."""
        if redis_client is not None:
            try:
                key = f"trace:checkpoint:{trace_id}"
                await redis_client.set(key, json.dumps(checkpoint), ex=ttl)
            except Exception as e:
                logger.warning(f"Failed to save checkpoint to Redis: {e}")
