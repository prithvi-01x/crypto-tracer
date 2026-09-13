from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, List, Tuple, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update

from backend.app.config import (
    DEFAULT_TENANT_ID,
    DEFAULT_DISTRICT_ID,
    DEFAULT_POLICE_STATION_ID,
)
from backend.app.persistence.models import Trace
from backend.app.persistence.pagination import apply_keyset_pagination, process_keyset_results
from backend.app.domain.models import InvestigationGraph
from backend.app.domain.tracing.fsm import TraceStateMachine, InvalidStateTransitionError


class TraceRepository:
    @staticmethod
    async def create(
        session: AsyncSession,
        case_id: str,
        chain: str = "TRON",
        input_type: str = "address",
        input_value: str = "",
        asset: str = "TRC20:USDT",
        max_hops: int = 4,
        min_relevant_usd: Decimal = Decimal("1.00"),
        execution_mode: str = "DEMO",
        status: str = "RUNNING",
        job_id: Optional[str] = None,
        worker_id: Optional[str] = None,
        max_retries: int = 3,
        tenant_id: str = DEFAULT_TENANT_ID,
        district_id: str = DEFAULT_DISTRICT_ID,
        police_station_id: str = DEFAULT_POLICE_STATION_ID,
    ) -> Trace:
        trace = Trace(
            case_id=case_id,
            chain=chain,
            input_type=input_type,
            input_value=input_value.strip(),
            asset=asset,
            status=status.upper(),
            job_id=job_id,
            worker_id=worker_id,
            max_hops=max_hops,
            current_hop=0,
            progress_percent=Decimal("0.00"),
            min_relevant_usd=min_relevant_usd,
            execution_mode=execution_mode.upper(),
            started_at=datetime.now(timezone.utc),
            engine_version="0.1.0",
            max_retries=max_retries,
            retry_count=0,
            tenant_id=tenant_id,
            district_id=district_id,
            police_station_id=police_station_id,
        )
        session.add(trace)
        await session.commit()
        await session.refresh(trace)
        return trace

    @staticmethod
    async def update_running(
        session: AsyncSession,
        trace_id: str,
        worker_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> Optional[Trace]:
        trace = await TraceRepository.get_by_id(session, trace_id, tenant_id=tenant_id)
        if not trace:
            return None

        TraceStateMachine.validate_transition(trace.status, "RUNNING")
        trace.status = "RUNNING"
        if worker_id:
            trace.worker_id = worker_id
        trace.heartbeat_at = datetime.now(timezone.utc)
        await session.commit()
        await session.refresh(trace)
        return trace

    @staticmethod
    async def update_progress(
        session: AsyncSession,
        trace_id: str,
        current_hop: int,
        progress_percent: float,
        checkpoint_data: Optional[Dict[str, Any]] = None,
        tenant_id: Optional[str] = None,
    ) -> Optional[Trace]:
        trace = await TraceRepository.get_by_id(session, trace_id, tenant_id=tenant_id)
        if not trace:
            return None

        trace.current_hop = current_hop
        trace.progress_percent = Decimal(str(round(progress_percent, 2)))
        trace.heartbeat_at = datetime.now(timezone.utc)
        if checkpoint_data is not None:
            trace.checkpoint_data = checkpoint_data

        await session.commit()
        await session.refresh(trace)
        return trace

    @staticmethod
    async def update_heartbeat(
        session: AsyncSession,
        trace_id: str,
        tenant_id: Optional[str] = None,
    ) -> Optional[Trace]:
        trace = await TraceRepository.get_by_id(session, trace_id, tenant_id=tenant_id)
        if not trace:
            return None

        trace.heartbeat_at = datetime.now(timezone.utc)
        await session.commit()
        await session.refresh(trace)
        return trace

    @staticmethod
    async def update_retry(
        session: AsyncSession,
        trace_id: str,
        error_message: str,
        tenant_id: Optional[str] = None,
    ) -> Optional[Trace]:
        trace = await TraceRepository.get_by_id(session, trace_id, tenant_id=tenant_id)
        if not trace:
            return None

        TraceStateMachine.validate_transition(trace.status, "RETRY")
        trace.status = "RETRY"
        trace.retry_count = trace.retry_count + 1
        trace.error_message = error_message
        trace.heartbeat_at = datetime.now(timezone.utc)

        await session.commit()
        await session.refresh(trace)
        return trace

    @staticmethod
    async def update_cancelled(
        session: AsyncSession,
        trace_id: str,
        cancel_reason: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> Optional[Trace]:
        now = datetime.now(timezone.utc)
        stmt = (
            update(Trace)
            .where(
                Trace.id == trace_id,
                Trace.status.in_(["QUEUED", "RUNNING", "RETRY"]),
            )
            .values(
                status="CANCEL",
                cancelled_at=now,
                cancel_reason=cancel_reason,
            )
        )
        if tenant_id:
            stmt = stmt.where(Trace.tenant_id == tenant_id)
        result = await session.execute(stmt)
        await session.commit()
        if result.rowcount == 0:
            existing = await TraceRepository.get_by_id(session, trace_id, tenant_id=tenant_id)
            if not existing:
                return None
            TraceStateMachine.validate_transition(existing.status, "CANCEL")
        return await TraceRepository.get_by_id(session, trace_id, tenant_id=tenant_id)

    @staticmethod
    async def update_completed(
        session: AsyncSession,
        trace_id: str,
        graph: InvestigationGraph,
        duration_ms: int,
        boundary_code: Optional[str] = None,
        investigator_summary: Optional[str] = None,
        status: str = "COMPLETED",
        tenant_id: Optional[str] = None,
    ) -> Optional[Trace]:
        trace = await TraceRepository.get_by_id(session, trace_id, tenant_id=tenant_id)
        if not trace:
            return None

        TraceStateMachine.validate_transition(trace.status, status)
        trace.status = status
        trace.completed_at = datetime.now(timezone.utc)
        trace.progress_percent = Decimal("100.00")
        trace.graph_data = graph.model_dump(mode="json")
        trace.node_count = len(graph.nodes)
        trace.edge_count = len(graph.edges)
        trace.pruned_count = len(graph.pruned_records)
        trace.duration_ms = duration_ms
        trace.boundary_code = boundary_code
        trace.investigator_summary = investigator_summary

        await session.commit()
        await session.refresh(trace)
        return trace

    @staticmethod
    async def update_failed(
        session: AsyncSession,
        trace_id: str,
        error_message: str,
        boundary_code: Optional[str] = None,
        investigator_summary: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> Optional[Trace]:
        trace = await TraceRepository.get_by_id(session, trace_id, tenant_id=tenant_id)
        if not trace:
            return None

        TraceStateMachine.validate_transition(trace.status, "FAILED")
        trace.status = "FAILED"
        trace.completed_at = datetime.now(timezone.utc)
        trace.boundary_code = boundary_code
        trace.error_message = error_message
        trace.investigator_summary = investigator_summary or error_message
        trace.config = {
            "error": error_message,
            "boundary_code": boundary_code,
            "investigator_summary": investigator_summary or error_message,
        }

        await session.commit()
        await session.refresh(trace)
        return trace

    @staticmethod
    async def get_by_id(
        session: AsyncSession,
        trace_id: str,
        tenant_id: Optional[str] = None,
    ) -> Optional[Trace]:
        query = select(Trace).where(Trace.id == trace_id)
        if tenant_id:
            query = query.where(Trace.tenant_id == tenant_id)
        result = await session.execute(query)
        return result.scalars().first()

    @staticmethod
    async def list_by_case_id(
        session: AsyncSession,
        case_id: str,
        tenant_id: Optional[str] = None,
    ) -> List[Trace]:
        query = select(Trace).where(Trace.case_id == case_id)
        if tenant_id:
            query = query.where(Trace.tenant_id == tenant_id)
        query = query.order_by(Trace.started_at.desc())
        result = await session.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def list_by_case_id_keyset(
        session: AsyncSession,
        case_id: str,
        cursor: Optional[str] = None,
        limit: int = 50,
        tenant_id: Optional[str] = None,
    ) -> Tuple[List[Trace], int, Optional[str], bool]:
        query = select(Trace).where(Trace.case_id == case_id)
        count_query = select(func.count()).select_from(Trace).where(Trace.case_id == case_id)

        if tenant_id:
            query = query.where(Trace.tenant_id == tenant_id)
            count_query = count_query.where(Trace.tenant_id == tenant_id)

        total_res = await session.execute(count_query)
        total = total_res.scalar_one()

        query, _ = apply_keyset_pagination(
            query, Trace, cursor=cursor, limit=limit, timestamp_col_name="started_at", descending=True
        )
        res = await session.execute(query)
        raw_traces = list(res.scalars().all())

        traces, next_cursor, has_more = process_keyset_results(
            raw_traces, limit, timestamp_col_name="started_at"
        )
        return traces, total, next_cursor, has_more

    get_by_case = list_by_case_id
