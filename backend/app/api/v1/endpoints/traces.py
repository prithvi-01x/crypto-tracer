import asyncio
import json
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, Union
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request, Response
from fastapi.responses import StreamingResponse
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
from backend.app.config import settings
from backend.app.adapters.base import (
    ProviderTimeoutError,
    ProviderRateLimitError,
    InvalidAddressError,
    BlockchainProviderError,
)
from backend.app.adapters.tron_provider import TronProvider, validate_tron_address
from backend.app.domain.demo.canonical_data import DemoFixtureProvider, is_canonical_demo_address
from backend.app.domain.tracing.engine import GraphEngine
from backend.app.domain.tracing.fsm import TraceStateMachine, InvalidStateTransitionError
from backend.app.domain.models import InvestigationGraph
from backend.app.domain.attribution.engine import AttributionEngine
from backend.app.persistence.attribution_repository import AttributionRepository
from backend.app.worker.queue import get_trace_queue, TraceJobPayload, InMemoryTraceQueue, get_in_memory_trace_queue
from backend.app.api.v1.schemas.traces import (
    TraceCreateRequest,
    TraceStatusResponse,
    TraceListResponse,
    JobStatusResponse,
    TraceCancelRequest,
    TraceCancelResponse,
    TraceProgressResponse,
)
from backend.app.api.v1.schemas.attribution import AttributionResponse
from backend.app.core.auth import Role, OfficerSession
from backend.app.api.deps import get_current_officer, require_roles

router = APIRouter(prefix="/traces", tags=["Traces"])


@router.post(
    "",
    response_model=Union[TraceStatusResponse, JobStatusResponse],
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_201_CREATED: {
            "model": TraceStatusResponse,
            "description": "Synchronous trace executed and completed",
        },
        status.HTTP_202_ACCEPTED: {
            "model": JobStatusResponse,
            "description": "Asynchronous trace job accepted and queued",
        },
    },
)
async def start_trace(
    trace_in: TraceCreateRequest,
    response: Response,
    request: Request,
    sync: Optional[bool] = Query(None, description="Force sync (True -> 201) or async (False -> 202) execution"),
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
    current_officer: OfficerSession = Depends(require_roles([Role.INVESTIGATING_OFFICER, Role.SUPERVISOR, Role.ADMIN])),
):
    """
    Initiate a deterministic multi-hop transaction graph trace from a target suspect wallet.
    Dual-mode execution:
      - When sync=True (or test/dev default): executes synchronously returning HTTP 201 Created with TraceStatusResponse.
      - When sync=False (or production default): enqueues background job returning HTTP 202 Accepted with JobStatusResponse.
    Scoped to the current officer's tenant hierarchy.
    """
    # 1. Validate parent case exists for officer's tenant (IDOR prevention)
    case = await CaseRepository.get_by_id(db, trace_in.case_id, tenant_id=current_officer.tenant_id)
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "NOT_FOUND",
                "message": f"Parent case '{trace_in.case_id}' not found.",
            }
        )

    # 2. Validate input blockchain, asset, and address
    if trace_in.chain.upper() != "TRON":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "UNSUPPORTED_CHAIN",
                "message": f"Blockchain network '{trace_in.chain}' is not supported. Supported blockchain: TRON.",
                "supported_chains": ["TRON"],
            }
        )

    if trace_in.asset.upper() not in ("USDT", "TRC20:USDT", "TRC-20:USDT"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "UNSUPPORTED_ASSET",
                "message": f"Asset '{trace_in.asset}' is not supported. Supported asset: TRC20:USDT.",
                "supported_assets": ["TRC20:USDT"],
            }
        )

    clean_input = trace_in.input.strip()

    # 3. Determine execution mode & validate address format
    raw_mode = getattr(trace_in, "execution_mode", None)
    requested_mode = (raw_mode or settings.DEFAULT_EXECUTION_MODE).upper()
    is_canonical = is_canonical_demo_address(clean_input)

    if requested_mode == "DEMO" and is_canonical:
        resolved_mode = "DEMO"
    else:
        if trace_in.input_type == "address":
            if not validate_tron_address(clean_input):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "code": "INVALID_ADDRESS",
                        "message": f"Invalid TRON address format: '{clean_input}'. Expected 34-character Base58Check starting with 'T'.",
                    }
                )
        resolved_mode = "DEMO" if requested_mode == "DEMO" else "LIVE"

    # 4. Resolve Sync vs Async execution mode
    if sync is not None:
        is_sync = sync
    elif trace_in.sync is not None:
        is_sync = trace_in.sync
    elif request.headers.get("X-Execution-Sync") is not None:
        is_sync = request.headers.get("X-Execution-Sync", "").lower() in ("true", "1")
    elif request.headers.get("Prefer") == "respond-async":
        is_sync = False
    elif settings.APP_ENV.lower() == "production":
        is_sync = False
    else:
        # Development / Test defaults to sync to guarantee 100% regression safety for existing tests
        is_sync = True

    if not is_sync:
        # ====================================================================
        # ASYNCHRONOUS PATH (Feature 20: HTTP 202 Accepted)
        # ====================================================================
        job_id = str(uuid.uuid4())
        trace_record = await TraceRepository.create(
            session=db,
            case_id=trace_in.case_id,
            chain=trace_in.chain.upper(),
            input_type=trace_in.input_type,
            input_value=clean_input,
            asset=trace_in.asset,
            max_hops=trace_in.max_hops,
            min_relevant_usd=trace_in.min_relevant_usd,
            execution_mode=resolved_mode,
            status="QUEUED",
            job_id=job_id,
            tenant_id=current_officer.tenant_id,
            district_id=current_officer.district_id,
            police_station_id=current_officer.police_station_id,
        )

        queue = get_trace_queue(redis)
        payload = TraceJobPayload(
            trace_id=trace_record.id,
            job_id=job_id,
            case_id=trace_record.case_id,
            tenant_id=current_officer.tenant_id,
            district_id=current_officer.district_id,
            police_station_id=current_officer.police_station_id,
            officer_id=current_officer.officer_id,
            chain=trace_record.chain,
            input_value=trace_record.input_value,
            asset=trace_record.asset,
            max_hops=trace_record.max_hops,
            min_relevant_usd=str(trace_record.min_relevant_usd),
            execution_mode=resolved_mode,
        )
        await queue.enqueue(payload)
        await queue.publish_event(trace_record.id, {
            "event": "JOB_QUEUED",
            "trace_id": trace_record.id,
            "job_id": job_id,
            "status": "QUEUED",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        response.status_code = status.HTTP_202_ACCEPTED
        return JobStatusResponse(
            job_id=job_id,
            trace_id=trace_record.id,
            case_id=trace_record.case_id,
            status="QUEUED",
            chain=trace_record.chain,
            input_value=trace_record.input_value,
            asset=trace_record.asset,
            max_hops=trace_record.max_hops,
            execution_mode=resolved_mode,
            poll_url=f"/api/v1/traces/{trace_record.id}",
            ws_url=f"/ws/traces/{trace_record.id}",
            created_at=trace_record.started_at or datetime.now(timezone.utc),
            message="Trace job queued for background execution.",
        )

    # ========================================================================
    # SYNCHRONOUS PATH (HTTP 201 Created)
    # ========================================================================
    trace_record = await TraceRepository.create(
        session=db,
        case_id=trace_in.case_id,
        chain=trace_in.chain.upper(),
        input_type=trace_in.input_type,
        input_value=clean_input,
        asset=trace_in.asset,
        max_hops=trace_in.max_hops,
        min_relevant_usd=trace_in.min_relevant_usd,
        execution_mode=resolved_mode,
        status="RUNNING",
        tenant_id=current_officer.tenant_id,
        district_id=current_officer.district_id,
        police_station_id=current_officer.police_station_id,
    )

    if resolved_mode == "DEMO":
        provider = DemoFixtureProvider()
    else:
        provider = TronProvider(redis_client=redis)

    engine = GraphEngine(
        provider=provider,
        max_hops=trace_in.max_hops,
        min_relevant_usd=trace_in.min_relevant_usd,
    )

    try:
        graph = await engine.trace(source_address=clean_input)
        graph.meta["execution_mode"] = resolved_mode
        duration_ms = int(graph.meta.get("duration_ms", 0))
        is_partial = graph.meta.get("is_partial", False)
        boundary_code = graph.meta.get("boundary_reached")
        investigator_summary = graph.meta.get("investigator_explanation")

        trace_status = "PARTIAL" if is_partial else "COMPLETED"

        updated_trace = await TraceRepository.update_completed(
            session=db,
            trace_id=trace_record.id,
            graph=graph,
            duration_ms=duration_ms,
            boundary_code=boundary_code,
            investigator_summary=investigator_summary,
            status=trace_status,
            tenant_id=current_officer.tenant_id,
        )

        meta = graph.meta or {}
        pruned_records_count = len(graph.pruned_records)

        # Evidence generation
        try:
            evidence_items = EvidenceGenerator.generate_trace_evidence(
                case_id=updated_trace.case_id,
                trace_id=updated_trace.id,
                graph=graph,
                config_snapshot={"max_hops": updated_trace.max_hops, "min_relevant_usd": str(updated_trace.min_relevant_usd)},
            )
            await EvidenceRepository.save_evidence_items(
                db,
                evidence_items,
                tenant_id=current_officer.tenant_id,
                district_id=current_officer.district_id,
                police_station_id=current_officer.police_station_id,
            )

            now_utc = datetime.now(timezone.utc)
            audit_ev = AuditEvent(
                id=str(uuid.uuid4()),
                case_id=updated_trace.case_id,
                trace_id=updated_trace.id,
                actor_id=current_officer.officer_id,
                event_type=AuditEventType.TRACE_STARTED,
                action_summary=f"Initiated multi-hop trace from suspect wallet {updated_trace.input_value} (Hops: {updated_trace.max_hops}, Duration: {duration_ms}ms, Status: {trace_status}).",
                metadata={"node_count": updated_trace.node_count, "edge_count": updated_trace.edge_count, "pruned_count": pruned_records_count, "status": trace_status},
                content_hash=compute_content_hash({"trace_id": updated_trace.id, "input": updated_trace.input_value, "timestamp": now_utc.isoformat()}),
                created_at=now_utc,
            )
            await AuditRepository.record_event(
                db,
                audit_ev,
                tenant_id=current_officer.tenant_id,
                district_id=current_officer.district_id,
                police_station_id=current_officer.police_station_id,
            )
        except Exception:
            pass

        response.status_code = status.HTTP_201_CREATED
        return TraceStatusResponse(
            trace_id=updated_trace.id,
            case_id=updated_trace.case_id,
            status=updated_trace.status,
            chain=updated_trace.chain,
            input_value=updated_trace.input_value,
            asset=updated_trace.asset,
            max_hops=updated_trace.max_hops,
            execution_mode=updated_trace.execution_mode,
            duration_ms=updated_trace.duration_ms,
            node_count=updated_trace.node_count,
            edge_count=updated_trace.edge_count,
            pruned_count=pruned_records_count,
            nodes=updated_trace.node_count,
            edges=updated_trace.edge_count,
            pruned_nodes=pruned_records_count,
            raw_transfers_count=meta.get("raw_transfers_fetched_count", 0),
            relevant_transfers_count=meta.get("traversal_relevant_transfers_count", 0),
            boundary_code=boundary_code,
            investigator_summary=investigator_summary,
            is_partial=is_partial,
            started_at=updated_trace.started_at,
            completed_at=updated_trace.completed_at,
        )
    except InvalidAddressError as ex:
        boundary_code = "INVALID_ADDRESS"
        explanation = f"TRON address rejected: {ex}"
        await TraceRepository.update_failed(db, trace_record.id, str(ex), boundary_code=boundary_code, investigator_summary=explanation, tenant_id=current_officer.tenant_id)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": boundary_code,
                "message": str(ex),
                "trace_id": trace_record.id,
            }
        )
    except ProviderTimeoutError as ex:
        boundary_code = "PROVIDER_TIMEOUT"
        explanation = f"Blockchain provider timed out while querying suspect wallet {clean_input}. Upstream service was unresponsive after bounded retries."
        await TraceRepository.update_failed(db, trace_record.id, str(ex), boundary_code=boundary_code, investigator_summary=explanation, tenant_id=current_officer.tenant_id)
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail={
                "code": boundary_code,
                "message": explanation,
                "trace_id": trace_record.id,
            }
        )
    except ProviderRateLimitError as ex:
        boundary_code = "PROVIDER_RATE_LIMITED"
        explanation = f"Blockchain provider returned HTTP 429 (Too Many Requests) while querying suspect wallet {clean_input}. Traversal halted."
        await TraceRepository.update_failed(db, trace_record.id, str(ex), boundary_code=boundary_code, investigator_summary=explanation, tenant_id=current_officer.tenant_id)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "code": boundary_code,
                "message": explanation,
                "trace_id": trace_record.id,
            }
        )
    except BlockchainProviderError as ex:
        boundary_code = "BLOCKCHAIN_PROVIDER_ERROR"
        explanation = f"Blockchain provider error: {ex}"
        await TraceRepository.update_failed(db, trace_record.id, str(ex), boundary_code=boundary_code, investigator_summary=explanation, tenant_id=current_officer.tenant_id)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "code": boundary_code,
                "message": explanation,
                "trace_id": trace_record.id,
            }
        )
    except Exception as ex:
        await TraceRepository.update_failed(db, trace_record.id, str(ex), tenant_id=current_officer.tenant_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "TRACE_EXECUTION_FAILED",
                "message": f"Trace execution failed: {ex}",
                "trace_id": trace_record.id,
            }
        )


@router.post("/{trace_id}/cancel", response_model=TraceCancelResponse)
async def cancel_trace(
    trace_id: str,
    cancel_in: Optional[TraceCancelRequest] = None,
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
    current_officer: OfficerSession = Depends(require_roles([Role.INVESTIGATING_OFFICER, Role.SUPERVISOR, Role.ADMIN])),
):
    """
    Cancel an active or queued trace job.
    Enforces tenant boundaries and FSM transition constraints.
    """
    trace = await TraceRepository.get_by_id(db, trace_id, tenant_id=current_officer.tenant_id)
    if not trace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": f"Trace '{trace_id}' not found."},
        )

    if not TraceStateMachine.can_transition(trace.status, "CANCEL"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "INVALID_STATE_TRANSITION",
                "message": f"Cannot cancel trace in state '{trace.status}'. Allowed from QUEUED, RUNNING, RETRY.",
            }
        )

    reason = cancel_in.reason if cancel_in and cancel_in.reason else "Cancelled by investigator"
    queue = get_trace_queue(redis)
    await queue.cancel_job(trace_id)

    try:
        updated = await TraceRepository.update_cancelled(
            session=db,
            trace_id=trace_id,
            cancel_reason=reason,
            tenant_id=current_officer.tenant_id,
        )
    except InvalidStateTransitionError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "INVALID_STATE_TRANSITION",
                "message": str(e),
            }
        )

    return TraceCancelResponse(
        trace_id=trace_id,
        status="CANCEL",
        message=f"Trace execution cancelled: {reason}",
        cancelled_at=updated.cancelled_at or datetime.now(timezone.utc),
    )


@router.get("/{trace_id}/progress", response_model=TraceProgressResponse)
async def get_trace_progress(
    trace_id: str,
    db: AsyncSession = Depends(get_db),
    current_officer: OfficerSession = Depends(get_current_officer),
):
    """
    Retrieve real-time progress metrics and hop traversal status for an executing trace.
    """
    trace = await TraceRepository.get_by_id(db, trace_id, tenant_id=current_officer.tenant_id)
    if not trace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": f"Trace '{trace_id}' not found."},
        )

    return TraceProgressResponse(
        trace_id=trace.id,
        status=trace.status,
        current_hop=trace.current_hop or 0,
        max_hops=trace.max_hops,
        progress_percent=float(trace.progress_percent or 0.0),
        node_count=trace.node_count or 0,
        edge_count=trace.edge_count or 0,
        pruned_count=trace.pruned_count or 0,
        heartbeat_at=trace.heartbeat_at,
        error_message=trace.error_message,
    )


@router.get("/{trace_id}/stream")
async def stream_trace_events(
    trace_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis: aioredis.Redis = Depends(get_redis),
    current_officer: OfficerSession = Depends(get_current_officer),
):
    """
    Server-Sent Events (SSE) stream relaying real-time trace execution events.
    """
    trace = await TraceRepository.get_by_id(db, trace_id, tenant_id=current_officer.tenant_id)
    if not trace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": f"Trace '{trace_id}' not found."},
        )

    async def event_generator():
        yield f"data: {json.dumps({'event': 'INITIAL_STATE', 'trace_id': trace.id, 'status': trace.status})}\n\n"
        if TraceStateMachine.is_terminal(trace.status):
            return

        in_mem_queue = get_in_memory_trace_queue()
        q = in_mem_queue.subscribe(trace_id)
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    item = await asyncio.wait_for(q.get(), timeout=1.0)
                    yield f"data: {json.dumps(item)}\n\n"
                    if item.get("event") in ("JOB_COMPLETED", "JOB_FAILED", "JOB_CANCELLED"):
                        break
                except asyncio.TimeoutError:
                    yield f": ping\n\n"
        finally:
            in_mem_queue.unsubscribe(trace_id, q)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/{trace_id}", response_model=TraceStatusResponse)
async def get_trace_status(
    trace_id: str,
    db: AsyncSession = Depends(get_db),
    current_officer: OfficerSession = Depends(get_current_officer),
):
    """
    Retrieve status and execution summary for a specific trace.
    Enforces tenant boundaries; cross-tenant lookup returns HTTP 404.
    """
    trace = await TraceRepository.get_by_id(db, trace_id, tenant_id=current_officer.tenant_id)
    if not trace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "NOT_FOUND",
                "message": f"Trace '{trace_id}' not found.",
            }
        )

    meta = (trace.graph_data or {}).get("meta", {})
    pruned_count = getattr(trace, "pruned_count", 0) or meta.get("pruned_transfers_count", 0)
    boundary_code = getattr(trace, "boundary_code", None) or meta.get("boundary_reached")
    investigator_summary = getattr(trace, "investigator_summary", None) or meta.get("investigator_explanation")
    is_partial = (trace.status == "PARTIAL") or meta.get("is_partial", False)

    return TraceStatusResponse(
        trace_id=trace.id,
        case_id=trace.case_id,
        status=trace.status,
        chain=trace.chain,
        input_value=trace.input_value,
        asset=trace.asset,
        max_hops=trace.max_hops,
        execution_mode=trace.execution_mode,
        duration_ms=trace.duration_ms,
        node_count=trace.node_count,
        edge_count=trace.edge_count,
        pruned_count=pruned_count,
        nodes=trace.node_count,
        edges=trace.edge_count,
        pruned_nodes=pruned_count,
        raw_transfers_count=meta.get("raw_transfers_fetched_count", 0),
        relevant_transfers_count=meta.get("traversal_relevant_transfers_count", 0),
        boundary_code=boundary_code,
        investigator_summary=investigator_summary,
        is_partial=is_partial,
        started_at=trace.started_at,
        completed_at=trace.completed_at,
    )


@router.get("/{trace_id}/graph", response_model=InvestigationGraph)
async def get_trace_graph(
    trace_id: str,
    db: AsyncSession = Depends(get_db),
    current_officer: OfficerSession = Depends(get_current_officer),
):
    """
    Retrieve the complete NetworkX-generated investigation graph (nodes, edges, metadata).
    Enforces tenant boundaries; cross-tenant lookup returns HTTP 404.
    """
    trace = await TraceRepository.get_by_id(db, trace_id, tenant_id=current_officer.tenant_id)
    if not trace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "NOT_FOUND",
                "message": f"Trace '{trace_id}' not found.",
            }
        )

    if not trace.graph_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "BAD_REQUEST",
                "message": f"Graph data not available for trace '{trace_id}' (status: {trace.status}).",
            }
        )

    return InvestigationGraph(**trace.graph_data)


@router.get("/{trace_id}/attribution", response_model=AttributionResponse)
async def get_trace_attribution(
    trace_id: str,
    db: AsyncSession = Depends(get_db),
    current_officer: OfficerSession = Depends(get_current_officer),
):
    """
    Evaluate and retrieve explainable VASP attribution hypotheses for the specified trace graph.
    Enforces tenant boundaries; cross-tenant lookup returns HTTP 404.
    """
    trace = await TraceRepository.get_by_id(db, trace_id, tenant_id=current_officer.tenant_id)
    if not trace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "NOT_FOUND",
                "message": f"Trace '{trace_id}' not found.",
            }
        )

    if not trace.graph_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "BAD_REQUEST",
                "message": f"Graph data not available for trace '{trace_id}' (status: {trace.status}).",
            }
        )

    graph = InvestigationGraph(**trace.graph_data)
    engine = AttributionEngine()
    report = engine.evaluate_trace(trace_id=trace.id, graph=graph)

    try:
        await AttributionRepository.save_report(db, report)
    except Exception:
        pass

    try:
        evidence_items = EvidenceGenerator.generate_trace_evidence(
            case_id=trace.case_id,
            trace_id=trace.id,
            graph=graph,
            attribution_report=report,
            config_snapshot=trace.config,
        )
        await EvidenceRepository.save_evidence_items(
            db,
            evidence_items,
            tenant_id=current_officer.tenant_id,
            district_id=current_officer.district_id,
            police_station_id=current_officer.police_station_id,
        )

        now_utc = datetime.now(timezone.utc)
        top_vasp = report.best_candidate.vasp_name if report.best_candidate else "None"
        audit_ev = AuditEvent(
            id=str(uuid.uuid4()),
            case_id=trace.case_id,
            trace_id=trace.id,
            actor_id=current_officer.officer_id,
            event_type=AuditEventType.ATTRIBUTION_VIEWED,
            action_summary=f"Viewed VASP attribution hypotheses for trace {trace.id}. Primary hypothesis: {top_vasp}.",
            metadata={"candidates_count": len(report.candidates), "top_candidate": report.best_candidate.candidate_address if report.best_candidate else None},
            content_hash=compute_content_hash({"trace_id": trace.id, "action": "ATTRIBUTION_VIEWED", "timestamp": now_utc.isoformat()}),
            created_at=now_utc,
        )
        await AuditRepository.record_event(
            db,
            audit_ev,
            tenant_id=current_officer.tenant_id,
            district_id=current_officer.district_id,
            police_station_id=current_officer.police_station_id,
        )
    except Exception:
        pass

    return AttributionResponse.from_domain(report)


@router.get("/case/{case_id}", response_model=TraceListResponse)
async def get_traces_by_case_keyset(
    case_id: str,
    cursor: Optional[str] = Query(None, description="Base64 keyset pagination cursor"),
    limit: int = Query(50, ge=1, le=100, description="Maximum traces to return"),
    db: AsyncSession = Depends(get_db),
    current_officer: OfficerSession = Depends(get_current_officer),
):
    """Dedicated keyset-paginated endpoint for listing traces belonging to a case."""
    case = await CaseRepository.get_by_id(db, case_id, tenant_id=current_officer.tenant_id)
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": f"Parent case '{case_id}' not found."},
        )
    try:
        traces, total, next_cursor, has_more = await TraceRepository.list_by_case_id_keyset(
            db, case_id, cursor=cursor, limit=limit, tenant_id=current_officer.tenant_id
        )
    except ValueError as ex:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_CURSOR", "message": str(ex)},
        )
    items = []
    for t in traces:
        meta = (t.graph_data or {}).get("meta", {})
        pruned_count = getattr(t, "pruned_count", 0) or meta.get("pruned_transfers_count", 0)
        items.append(
            TraceStatusResponse(
                trace_id=t.id,
                case_id=t.case_id,
                status=t.status,
                chain=t.chain,
                input_value=t.input_value,
                asset=t.asset,
                max_hops=t.max_hops,
                execution_mode=getattr(t, "execution_mode", "DEMO"),
                duration_ms=t.duration_ms,
                node_count=t.node_count,
                edge_count=t.edge_count,
                pruned_count=pruned_count,
                nodes=t.node_count,
                edges=t.edge_count,
                pruned_nodes=pruned_count,
                raw_transfers_count=meta.get("raw_transfers_fetched_count", 0),
                relevant_transfers_count=meta.get("traversal_relevant_transfers_count", 0),
                boundary_code=getattr(t, "boundary_code", None) or meta.get("boundary_reached"),
                investigator_summary=getattr(t, "investigator_summary", None) or meta.get("investigator_explanation"),
                is_partial=(t.status == "PARTIAL") or meta.get("is_partial", False),
                started_at=t.started_at,
                completed_at=t.completed_at,
            )
        )
    return TraceListResponse(items=items, total=total, next_cursor=next_cursor, has_more=has_more)
