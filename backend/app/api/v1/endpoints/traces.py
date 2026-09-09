from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as aioredis

from backend.app.persistence.db import get_db
from backend.app.persistence.redis import get_redis
from backend.app.persistence.case_repository import CaseRepository
from backend.app.persistence.trace_repository import TraceRepository
from backend.app.adapters.tron_provider import TronProvider, validate_tron_address
from backend.app.domain.tracing.engine import GraphEngine
from backend.app.domain.models import InvestigationGraph
from backend.app.api.v1.schemas.traces import TraceCreateRequest, TraceStatusResponse

router = APIRouter(prefix="/traces", tags=["Traces"])


@router.post("", response_model=TraceStatusResponse, status_code=status.HTTP_201_CREATED)
async def start_trace(
    trace_in: TraceCreateRequest,
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
):
    """
    Initiate a deterministic multi-hop transaction graph trace from a target suspect wallet.
    Executes BFS traversal using normalized TRON transfer data and persists the resulting graph in PostgreSQL.
    """
    # 1. Validate parent case exists
    case = await CaseRepository.get_by_id(db, trace_in.case_id)
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Parent case '{trace_in.case_id}' not found."
        )

    # 2. Validate input address format
    clean_input = trace_in.input.strip()
    if trace_in.chain.upper() == "TRON" and trace_in.input_type == "address":
        if not validate_tron_address(clean_input):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid TRON address format: '{clean_input}'. Expected 34-character Base58Check starting with 'T'."
            )

    # 3. Create initial trace record in PostgreSQL
    trace_record = await TraceRepository.create(
        session=db,
        case_id=trace_in.case_id,
        chain=trace_in.chain.upper(),
        input_type=trace_in.input_type,
        input_value=clean_input,
        asset=trace_in.asset,
        max_hops=trace_in.max_hops,
        min_relevant_usd=trace_in.min_relevant_usd,
    )

    # 4. Initialize Blockchain Provider & Graph Engine
    provider = TronProvider(redis_client=redis)
    engine = GraphEngine(
        provider=provider,
        max_hops=trace_in.max_hops,
    )

    # 5. Execute Graph Traversal
    try:
        graph = await engine.trace(source_address=clean_input)
        duration_ms = int(graph.meta.get("duration_ms", 0))

        # 6. Persist completed graph in PostgreSQL
        updated_trace = await TraceRepository.update_completed(
            session=db,
            trace_id=trace_record.id,
            graph=graph,
            duration_ms=duration_ms,
        )

        return TraceStatusResponse(
            trace_id=updated_trace.id,
            case_id=updated_trace.case_id,
            status=updated_trace.status,
            chain=updated_trace.chain,
            input_value=updated_trace.input_value,
            asset=updated_trace.asset,
            max_hops=updated_trace.max_hops,
            duration_ms=updated_trace.duration_ms,
            node_count=updated_trace.node_count,
            edge_count=updated_trace.edge_count,
            started_at=updated_trace.started_at,
            completed_at=updated_trace.completed_at,
        )
    except Exception as ex:
        await TraceRepository.update_failed(db, trace_record.id, str(ex))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Trace execution failed: {ex}"
        )


@router.get("/{trace_id}", response_model=TraceStatusResponse)
async def get_trace_status(
    trace_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieve status and execution summary for a specific trace.
    """
    trace = await TraceRepository.get_by_id(db, trace_id)
    if not trace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Trace '{trace_id}' not found."
        )

    return TraceStatusResponse(
        trace_id=trace.id,
        case_id=trace.case_id,
        status=trace.status,
        chain=trace.chain,
        input_value=trace.input_value,
        asset=trace.asset,
        max_hops=trace.max_hops,
        duration_ms=trace.duration_ms,
        node_count=trace.node_count,
        edge_count=trace.edge_count,
        started_at=trace.started_at,
        completed_at=trace.completed_at,
    )


@router.get("/{trace_id}/graph", response_model=InvestigationGraph)
async def get_trace_graph(
    trace_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieve the complete NetworkX-generated investigation graph (nodes, edges, metadata).
    """
    trace = await TraceRepository.get_by_id(db, trace_id)
    if not trace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Trace '{trace_id}' not found."
        )

    if not trace.graph_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Graph data not available for trace '{trace_id}' (status: {trace.status})."
        )

    return InvestigationGraph(**trace.graph_data)
