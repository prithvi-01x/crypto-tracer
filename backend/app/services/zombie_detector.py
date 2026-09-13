import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.app.persistence.models import Trace
from backend.app.persistence.trace_repository import TraceRepository
from backend.app.worker.queue import TraceQueue, TraceJobPayload, get_trace_queue

logger = logging.getLogger("crypto_tracer.services.zombie_detector")


class ZombieDetector:
    """
    Scans for stale/orphaned jobs stuck in RUNNING or RETRY due to killed or crashed workers.
    Performs deterministic recovery (re-enqueue up to max_retries, or terminal PARTIAL/FAILED).
    """

    def __init__(
        self,
        db_session_factory,
        queue: Optional[TraceQueue] = None,
        redis_client: Optional[Any] = None,
        zombie_threshold_seconds: float = 30.0,
    ):
        self.db_session_factory = db_session_factory
        self.queue = queue or get_trace_queue(redis_client)
        self.redis = redis_client
        self.zombie_threshold_seconds = zombie_threshold_seconds

    async def sweep_zombies(self) -> List[Dict[str, Any]]:
        """
        Scan database for active traces whose heartbeats have expired and recover them.
        Returns a list of recovery action reports.
        """
        recovered_actions: List[Dict[str, Any]] = []
        now = datetime.now(timezone.utc)
        cutoff_time = now - timedelta(seconds=self.zombie_threshold_seconds)

        async with self.db_session_factory() as session:
            query = select(Trace).where(
                Trace.status.in_(["RUNNING", "RETRY"])
            )
            res = await session.execute(query)
            candidates = list(res.scalars().all())

            for trace in candidates:
                last_active = trace.heartbeat_at or trace.started_at
                if not last_active:
                    continue

                # Ensure timezone awareness for comparison
                if last_active.tzinfo is None:
                    last_active = last_active.replace(tzinfo=timezone.utc)

                if last_active > cutoff_time:
                    # Still alive
                    continue

                # Check if Redis lock is still active
                if self.redis is not None:
                    try:
                        lock_exists = await self.redis.exists(f"trace:lock:{trace.id}")
                        if lock_exists:
                            continue
                    except Exception:
                        pass

                trace_id = trace.id
                max_retries = trace.max_retries or 3
                current_retries = trace.retry_count or 0

                if current_retries < max_retries:
                    # Recover by transitioning to RETRY and re-enqueuing
                    error_msg = f"Zombie detected: heartbeat expired (last seen {last_active.isoformat()})"
                    await TraceRepository.update_retry(
                        session=session,
                        trace_id=trace_id,
                        error_message=error_msg,
                        tenant_id=trace.tenant_id,
                    )

                    payload = TraceJobPayload(
                        trace_id=trace.id,
                        job_id=trace.job_id or trace.id,
                        case_id=trace.case_id,
                        tenant_id=trace.tenant_id,
                        district_id=trace.district_id,
                        police_station_id=trace.police_station_id,
                        officer_id="system-zombie-sweeper",
                        chain=trace.chain,
                        input_value=trace.input_value,
                        asset=trace.asset,
                        max_hops=trace.max_hops,
                        min_relevant_usd=str(trace.min_relevant_usd),
                        execution_mode=trace.execution_mode,
                    )
                    await self.queue.enqueue(payload)
                    await self.queue.publish_event(trace_id, {
                        "event": "ZOMBIE_RECOVERED_RETRY",
                        "trace_id": trace_id,
                        "retry_count": current_retries + 1,
                        "max_retries": max_retries,
                        "timestamp": now.isoformat(),
                    })
                    recovered_actions.append({
                        "trace_id": trace_id,
                        "action": "RETRY",
                        "retry_count": current_retries + 1,
                    })
                    logger.warning(
                        f"Zombie trace {trace_id} recovered to RETRY ({current_retries + 1}/{max_retries})"
                    )

                else:
                    # Retries exhausted -> Terminate as PARTIAL (if checkpoint exists) or FAILED
                    has_checkpoint = bool(trace.checkpoint_data)
                    final_status = "PARTIAL" if has_checkpoint else "FAILED"
                    boundary = "WORKER_HEARTBEAT_EXPIRED"
                    summary = f"Job aborted: worker heartbeat expired after {max_retries} attempts."

                    if has_checkpoint:
                        # Transition to PARTIAL
                        trace.status = "PARTIAL"
                        trace.completed_at = now
                        trace.boundary_code = boundary
                        trace.investigator_summary = summary
                        await session.commit()
                    else:
                        await TraceRepository.update_failed(
                            session=session,
                            trace_id=trace_id,
                            error_message="Worker heartbeat expired and retries exhausted.",
                            boundary_code=boundary,
                            investigator_summary=summary,
                            tenant_id=trace.tenant_id,
                        )

                    await self.queue.publish_event(trace_id, {
                        "event": "ZOMBIE_RECOVERED_FAILED",
                        "trace_id": trace_id,
                        "final_status": final_status,
                        "boundary_code": boundary,
                        "timestamp": now.isoformat(),
                    })
                    recovered_actions.append({
                        "trace_id": trace_id,
                        "action": final_status,
                        "boundary_code": boundary,
                    })
                    logger.error(
                        f"Zombie trace {trace_id} retries exhausted -> transitioned to {final_status}"
                    )

        return recovered_actions
