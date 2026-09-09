import uuid
from datetime import datetime, timezone
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as aioredis

from backend.app.persistence.db import get_db
from backend.app.persistence.redis import get_redis
from backend.app.persistence.case_repository import CaseRepository
from backend.app.persistence.trace_repository import TraceRepository
from backend.app.persistence.evidence_repository import EvidenceRepository
from backend.app.persistence.audit_repository import AuditRepository
from backend.app.domain.evidence.generator import EvidenceGenerator
from backend.app.domain.evidence.models import AuditEvent, AuditEventType
from backend.app.domain.evidence.hasher import compute_content_hash
from backend.app.adapters.tron_provider import TronProvider, validate_tron_address
from backend.app.domain.tracing.engine import GraphEngine
from backend.app.domain.models import InvestigationGraph
from backend.app.domain.attribution.engine import AttributionEngine
from backend.app.persistence.attribution_repository import AttributionRepository
from backend.app.api.v1.schemas.traces import TraceCreateRequest, TraceStatusResponse
from backend.app.api.v1.schemas.attribution import AttributionResponse

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
        min_relevant_usd=trace_in.min_relevant_usd,
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

        meta = graph.meta or {}
        pruned_records_count = len(graph.pruned_records)

        # 7. Automatically compile & persist baseline trace evidence items (Tier 1 & 2)
        try:
            evidence_items = EvidenceGenerator.generate_trace_evidence(
                case_id=updated_trace.case_id,
                trace_id=updated_trace.id,
                graph=graph,
                config_snapshot={"max_hops": updated_trace.max_hops, "min_relevant_usd": str(updated_trace.min_relevant_usd)},
            )
            await EvidenceRepository.save_evidence_items(db, evidence_items)

            # Record investigator audit event
            now_utc = datetime.now(timezone.utc)
            audit_ev = AuditEvent(
                id=str(uuid.uuid4()),
                case_id=updated_trace.case_id,
                trace_id=updated_trace.id,
                actor_id="investigator",
                event_type=AuditEventType.TRACE_STARTED,
                action_summary=f"Initiated multi-hop trace from suspect wallet {updated_trace.input_value} (Hops: {updated_trace.max_hops}, Duration: {duration_ms}ms).",
                metadata={"node_count": updated_trace.node_count, "edge_count": updated_trace.edge_count, "pruned_count": pruned_records_count},
                content_hash=compute_content_hash({"trace_id": updated_trace.id, "input": updated_trace.input_value, "timestamp": now_utc.isoformat()}),
                created_at=now_utc,
            )
            await AuditRepository.record_event(db, audit_ev)
        except Exception:
            pass

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
            pruned_count=pruned_records_count,
            nodes=updated_trace.node_count,
            edges=updated_trace.edge_count,
            pruned_nodes=pruned_records_count,
            raw_transfers_count=meta.get("raw_transfers_fetched_count", 0),
            relevant_transfers_count=meta.get("traversal_relevant_transfers_count", 0),
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

    meta = (trace.graph_data or {}).get("meta", {})
    pruned_count = getattr(trace, "pruned_count", 0) or meta.get("pruned_transfers_count", 0)

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
        pruned_count=pruned_count,
        nodes=trace.node_count,
        edges=trace.edge_count,
        pruned_nodes=pruned_count,
        raw_transfers_count=meta.get("raw_transfers_fetched_count", 0),
        relevant_transfers_count=meta.get("traversal_relevant_transfers_count", 0),
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


@router.get("/{trace_id}/attribution", response_model=AttributionResponse)
async def get_trace_attribution(
    trace_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Evaluate and retrieve explainable VASP attribution hypotheses for the specified trace graph.
    Computes calibrated confidence score based on direct tagging, sweep patterns,
    fan-in consolidation, and temporal delays.
    Persists evaluation results to PostgreSQL.
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

    # Reconstruct domain InvestigationGraph
    graph = InvestigationGraph(**trace.graph_data)

    # Execute Attribution Engine evaluation
    engine = AttributionEngine()
    report = engine.evaluate_trace(trace_id=trace.id, graph=graph)

    # Persist attribution results into PostgreSQL
    try:
        await AttributionRepository.save_report(db, report)
    except Exception:
        pass

    # Compile & persist complete attribution evidence items (Tier 1, 2, and 3)
    try:
        evidence_items = EvidenceGenerator.generate_trace_evidence(
            case_id=trace.case_id,
            trace_id=trace.id,
            graph=graph,
            attribution_report=report,
            config_snapshot=trace.config,
        )
        await EvidenceRepository.save_evidence_items(db, evidence_items)

        # Record investigator audit event
        now_utc = datetime.now(timezone.utc)
        top_vasp = report.best_candidate.vasp_name if report.best_candidate else "None"
        audit_ev = AuditEvent(
            id=str(uuid.uuid4()),
            case_id=trace.case_id,
            trace_id=trace.id,
            actor_id="investigator",
            event_type=AuditEventType.ATTRIBUTION_VIEWED,
            action_summary=f"Viewed VASP attribution hypotheses for trace {trace.id}. Primary hypothesis: {top_vasp}.",
            metadata={"candidates_count": len(report.candidates), "top_candidate": report.best_candidate.candidate_address if report.best_candidate else None},
            content_hash=compute_content_hash({"trace_id": trace.id, "action": "ATTRIBUTION_VIEWED", "timestamp": now_utc.isoformat()}),
            created_at=now_utc,
        )
        await AuditRepository.record_event(db, audit_ev)
    except Exception:
        pass

    return AttributionResponse.from_domain(report)
