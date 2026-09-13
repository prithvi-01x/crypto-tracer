from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Set
import abc
import asyncio
import json
import logging
from pydantic import BaseModel, Field

logger = logging.getLogger("crypto_tracer.worker.queue")


class TraceJobPayload(BaseModel):
    trace_id: str
    job_id: str
    case_id: str
    tenant_id: str
    district_id: str
    police_station_id: str
    officer_id: str
    chain: str = "TRON"
    input_value: str
    asset: str = "TRC20:USDT"
    max_hops: int = 4
    min_relevant_usd: str = "1.00"
    execution_mode: str = "LIVE"
    enqueued_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TraceQueue(abc.ABC):
    """Abstract interface for background trace job queuing and event broadcasting."""

    @abc.abstractmethod
    async def enqueue(self, payload: TraceJobPayload) -> str:
        """Enqueue a trace job. Return job_id."""
        raise NotImplementedError

    @abc.abstractmethod
    async def pop(self, timeout_seconds: float = 2.0) -> Optional[TraceJobPayload]:
        """Pop the next available job, or return None if timeout expires."""
        raise NotImplementedError

    @abc.abstractmethod
    async def publish_event(self, trace_id: str, event_data: Dict[str, Any]) -> None:
        """Publish a real-time execution event to subscribers."""
        raise NotImplementedError

    @abc.abstractmethod
    async def cancel_job(self, trace_id: str) -> bool:
        """Flag a job as cancelled."""
        raise NotImplementedError

    @abc.abstractmethod
    async def is_cancelled(self, trace_id: str) -> bool:
        """Check if a job has been cancelled."""
        raise NotImplementedError


class InMemoryTraceQueue(TraceQueue):
    """Hermetic in-memory job queue and pub/sub for unit tests and local development."""

    def __init__(self):
        self._queue: asyncio.Queue[TraceJobPayload] = asyncio.Queue()
        self._subscribers: Dict[str, Set[asyncio.Queue]] = {}
        self._cancelled: Set[str] = set()
        self._snapshots: Dict[str, Dict[str, Any]] = {}
        self._lock = asyncio.Lock()

    async def enqueue(self, payload: TraceJobPayload) -> str:
        await self._queue.put(payload)
        logger.debug(f"[InMemoryQueue] Enqueued job {payload.job_id} for trace {payload.trace_id}")
        return payload.job_id

    async def pop(self, timeout_seconds: float = 2.0) -> Optional[TraceJobPayload]:
        try:
            return await asyncio.wait_for(self._queue.get(), timeout=max(0.01, timeout_seconds))
        except asyncio.TimeoutError:
            return None

    async def publish_event(self, trace_id: str, event_data: Dict[str, Any]) -> None:
        async with self._lock:
            # Store snapshot for instant hydration
            if "progress" in event_data or event_data.get("event") == "HOP_PROGRESS":
                self._snapshots[trace_id] = event_data

            subs = list(self._subscribers.get(trace_id, set()))

        for q in subs:
            try:
                q.put_nowait(event_data)
            except Exception as e:
                logger.warning(f"Error publishing to in-memory subscriber: {e}")

    async def cancel_job(self, trace_id: str) -> bool:
        async with self._lock:
            self._cancelled.add(trace_id)
        await self.publish_event(trace_id, {
            "event": "JOB_CANCELLED",
            "trace_id": trace_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        return True

    async def is_cancelled(self, trace_id: str) -> bool:
        async with self._lock:
            return trace_id in self._cancelled

    def subscribe(self, trace_id: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        if trace_id not in self._subscribers:
            self._subscribers[trace_id] = set()
        self._subscribers[trace_id].add(q)
        return q

    def unsubscribe(self, trace_id: str, q: asyncio.Queue) -> None:
        if trace_id in self._subscribers:
            self._subscribers[trace_id].discard(q)
            if not self._subscribers[trace_id]:
                del self._subscribers[trace_id]

    def get_snapshot(self, trace_id: str) -> Optional[Dict[str, Any]]:
        return self._snapshots.get(trace_id)


class RedisTraceQueue(TraceQueue):
    """Production Redis-backed job queue using lists (LPUSH/BRPOP) and Pub/Sub."""

    QUEUE_KEY = "trace:queue"

    def __init__(self, redis_client: Any):
        self.redis = redis_client

    async def enqueue(self, payload: TraceJobPayload) -> str:
        try:
            await self.redis.lpush(self.QUEUE_KEY, payload.model_dump_json())
            logger.info(f"[RedisQueue] Enqueued job {payload.job_id} for trace {payload.trace_id}")
            return payload.job_id
        except Exception as e:
            logger.warning(f"RedisQueue enqueue failed ({e}), falling back to in-memory queue")
            return await get_in_memory_trace_queue().enqueue(payload)

    async def pop(self, timeout_seconds: float = 2.0) -> Optional[TraceJobPayload]:
        try:
            timeout_int = max(1, int(timeout_seconds))
            res = await self.redis.brpop(self.QUEUE_KEY, timeout=timeout_int)
            if res:
                _, raw_val = res
                if isinstance(raw_val, bytes):
                    raw_val = raw_val.decode("utf-8")
                return TraceJobPayload.model_validate_json(raw_val)
            return None
        except Exception as e:
            logger.warning(f"RedisQueue pop error: {e}")
            return None

    async def publish_event(self, trace_id: str, event_data: Dict[str, Any]) -> None:
        # 1. Local in-memory broadcast for SSE/WebSocket subscribers in this instance
        try:
            await get_in_memory_trace_queue().publish_event(trace_id, event_data)
        except Exception as e:
            logger.warning(f"InMemoryQueue broadcast error: {e}")

        # 2. Redis cluster broadcast
        try:
            payload_str = json.dumps(event_data)
            await self.redis.publish(f"trace:events:{trace_id}", payload_str)
            # Persist latest progress snapshot
            if "progress" in event_data or event_data.get("event") == "HOP_PROGRESS":
                await self.redis.set(f"trace:progress:{trace_id}", payload_str, ex=3600)
        except Exception as e:
            logger.warning(f"RedisQueue publish error: {e}")

    async def cancel_job(self, trace_id: str) -> bool:
        try:
            await self.redis.set(f"trace:cancel:{trace_id}", "1", ex=300)
            await self.publish_event(trace_id, {
                "event": "JOB_CANCELLED",
                "trace_id": trace_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            return True
        except Exception as e:
            logger.warning(f"RedisQueue cancel error: {e}")
            return False

    async def is_cancelled(self, trace_id: str) -> bool:
        try:
            return bool(await self.redis.exists(f"trace:cancel:{trace_id}"))
        except Exception as e:
            logger.warning(f"RedisQueue is_cancelled check error: {e}")
            return False


_in_memory_queue_instance: Optional[InMemoryTraceQueue] = None


def get_in_memory_trace_queue() -> InMemoryTraceQueue:
    global _in_memory_queue_instance
    if _in_memory_queue_instance is None:
        _in_memory_queue_instance = InMemoryTraceQueue()
    return _in_memory_queue_instance


def get_trace_queue(redis_client: Optional[Any] = None) -> TraceQueue:
    """Return RedisTraceQueue if redis_client is provided, else fallback to InMemoryTraceQueue."""
    if redis_client is not None:
        return RedisTraceQueue(redis_client)
    return get_in_memory_trace_queue()


class ReportJobPayload(BaseModel):
    job_id: str
    report_id: str
    case_id: str
    trace_id: Optional[str] = None
    tenant_id: str
    district_id: str
    police_station_id: str
    officer_id: str
    report_type: str  # EVIDENCE_DOSSIER, SECTION_94_BNSS, SECTION_63_BSA
    parameters: Dict[str, Any] = Field(default_factory=dict)
    enqueued_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ReportQueue(abc.ABC):
    """Abstract interface for background report generation job queue."""

    @abc.abstractmethod
    async def enqueue(self, payload: ReportJobPayload) -> str:
        """Enqueue a report job. Return job_id."""
        raise NotImplementedError

    @abc.abstractmethod
    async def pop(self, timeout_seconds: float = 2.0) -> Optional[ReportJobPayload]:
        """Pop the next available job, or return None if timeout expires."""
        raise NotImplementedError

    @abc.abstractmethod
    async def publish_event(self, job_id: str, event_data: Dict[str, Any]) -> None:
        """Publish report event."""
        raise NotImplementedError


class InMemoryReportQueue(ReportQueue):
    """Hermetic in-memory job queue for report generation."""

    def __init__(self):
        self._queue: asyncio.Queue[ReportJobPayload] = asyncio.Queue()
        self._subscribers: Dict[str, Set[asyncio.Queue]] = {}
        self._lock = asyncio.Lock()

    async def enqueue(self, payload: ReportJobPayload) -> str:
        await self._queue.put(payload)
        logger.debug(f"[InMemoryReportQueue] Enqueued job {payload.job_id} for report {payload.report_id}")
        return payload.job_id

    async def pop(self, timeout_seconds: float = 2.0) -> Optional[ReportJobPayload]:
        try:
            return await asyncio.wait_for(self._queue.get(), timeout=max(0.01, timeout_seconds))
        except asyncio.TimeoutError:
            return None

    async def publish_event(self, job_id: str, event_data: Dict[str, Any]) -> None:
        async with self._lock:
            subs = list(self._subscribers.get(job_id, set()))
        for q in subs:
            try:
                q.put_nowait(event_data)
            except Exception as e:
                logger.warning(f"Error publishing to in-memory report subscriber: {e}")


class RedisReportQueue(ReportQueue):
    """Production Redis-backed job queue for reports."""

    QUEUE_KEY = "report:queue"

    def __init__(self, redis_client: Any):
        self.redis = redis_client

    async def enqueue(self, payload: ReportJobPayload) -> str:
        try:
            await self.redis.lpush(self.QUEUE_KEY, payload.model_dump_json())
            logger.info(f"[RedisReportQueue] Enqueued job {payload.job_id} for report {payload.report_id}")
            return payload.job_id
        except Exception as e:
            logger.warning(f"RedisReportQueue enqueue failed ({e}), falling back to in-memory report queue")
            return await get_in_memory_report_queue().enqueue(payload)

    async def pop(self, timeout_seconds: float = 2.0) -> Optional[ReportJobPayload]:
        try:
            timeout_int = max(1, int(timeout_seconds))
            res = await self.redis.brpop(self.QUEUE_KEY, timeout=timeout_int)
            if res:
                _, raw_val = res
                if isinstance(raw_val, bytes):
                    raw_val = raw_val.decode("utf-8")
                return ReportJobPayload.model_validate_json(raw_val)
            return None
        except Exception as e:
            logger.warning(f"RedisReportQueue pop error: {e}")
            return None

    async def publish_event(self, job_id: str, event_data: Dict[str, Any]) -> None:
        try:
            await get_in_memory_report_queue().publish_event(job_id, event_data)
        except Exception as e:
            logger.warning(f"InMemoryReportQueue broadcast error: {e}")

        try:
            payload_str = json.dumps(event_data)
            await self.redis.publish(f"report:events:{job_id}", payload_str)
        except Exception as e:
            logger.warning(f"RedisReportQueue publish error: {e}")


_in_memory_report_queue_instance: Optional[InMemoryReportQueue] = None


def get_in_memory_report_queue() -> InMemoryReportQueue:
    global _in_memory_report_queue_instance
    if _in_memory_report_queue_instance is None:
        _in_memory_report_queue_instance = InMemoryReportQueue()
    return _in_memory_report_queue_instance


def get_report_queue(redis_client: Optional[Any] = None) -> ReportQueue:
    """Return RedisReportQueue if redis_client is provided, else fallback to InMemoryReportQueue."""
    if redis_client is not None:
        return RedisReportQueue(redis_client)
    return get_in_memory_report_queue()

