"""
ARQ Worker Settings adapter for production CLI and container environments.
Can be invoked via: arq backend.app.worker.arq_config.WorkerSettings
"""
import os
from typing import Any, Dict


async def process_trace_job(ctx: Dict[str, Any], payload_dict: Dict[str, Any]):
    """ARQ job handler binding."""
    from backend.app.persistence.db import async_session_factory
    from backend.app.worker.queue import TraceJobPayload, get_trace_queue
    from backend.app.worker.fleet import TraceWorker

    redis = ctx.get("redis")
    payload = TraceJobPayload(**payload_dict)
    queue = get_trace_queue(redis)
    worker = TraceWorker(
        worker_id=os.getenv("HOSTNAME", "arq-worker-1"),
        queue=queue,
        db_session_factory=async_session_factory,
        redis_client=redis,
    )
    await worker.process_job(payload)


class WorkerSettings:
    """Standard ARQ Worker configuration settings."""
    functions = [process_trace_job]
    max_jobs = 10
    job_timeout = 300
    keep_result = 60
