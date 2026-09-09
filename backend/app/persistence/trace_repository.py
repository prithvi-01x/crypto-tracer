from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.app.persistence.models import Trace
from backend.app.domain.models import InvestigationGraph


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
    ) -> Trace:
        trace = Trace(
            case_id=case_id,
            chain=chain,
            input_type=input_type,
            input_value=input_value.strip(),
            asset=asset,
            status="RUNNING",
            max_hops=max_hops,
            min_relevant_usd=min_relevant_usd,
            started_at=datetime.now(timezone.utc),
            engine_version="0.1.0",
        )
        session.add(trace)
        await session.commit()
        await session.refresh(trace)
        return trace

    @staticmethod
    async def update_completed(
        session: AsyncSession,
        trace_id: str,
        graph: InvestigationGraph,
        duration_ms: int,
        boundary_code: Optional[str] = None,
        investigator_summary: Optional[str] = None,
        status: str = "COMPLETED",
    ) -> Optional[Trace]:
        trace = await TraceRepository.get_by_id(session, trace_id)
        if not trace:
            return None

        trace.status = status
        trace.completed_at = datetime.now(timezone.utc)
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
    ) -> Optional[Trace]:
        trace = await TraceRepository.get_by_id(session, trace_id)
        if not trace:
            return None

        trace.status = "FAILED"
        trace.completed_at = datetime.now(timezone.utc)
        trace.boundary_code = boundary_code
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
    async def get_by_id(session: AsyncSession, trace_id: str) -> Optional[Trace]:
        query = select(Trace).where(Trace.id == trace_id)
        result = await session.execute(query)
        return result.scalars().first()

    @staticmethod
    async def list_by_case_id(session: AsyncSession, case_id: str) -> List[Trace]:
        query = select(Trace).where(Trace.case_id == case_id).order_by(Trace.started_at.desc())
        result = await session.execute(query)
        return list(result.scalars().all())
