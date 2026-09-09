import uuid
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.persistence.db import get_db
from backend.app.persistence.case_repository import CaseRepository
from backend.app.persistence.trace_repository import TraceRepository
from backend.app.persistence.evidence_repository import EvidenceRepository
from backend.app.persistence.audit_repository import AuditRepository
from backend.app.persistence.attribution_repository import AttributionRepository
from backend.app.domain.models import InvestigationGraph
from backend.app.domain.attribution.engine import AttributionEngine
from backend.app.domain.evidence.models import AuditEvent, AuditEventType
from backend.app.domain.evidence.hasher import compute_content_hash
from backend.app.domain.evidence.generator import EvidenceGenerator
from backend.app.api.v1.schemas.evidence import (
    EvidenceItemResponse,
    EvidenceChainResponse,
    AuditEventCreateRequest,
    AuditEventResponse,
    AttributionReviewRequest,
    AttributionReviewResponse,
)

router = APIRouter(tags=["Evidence & Audit"])


@router.get("/traces/{trace_id}/evidence", response_model=EvidenceChainResponse)
async def get_trace_evidence(
    trace_id: str,
    classification: Optional[str] = Query(None, description="Filter by OBSERVED, DERIVED, INFERRED, HUMAN_ACTION"),
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieve the complete structured evidence chain and provenance DAG for a trace.
    If evidence has not yet been compiled for this trace, generates it on-demand from the graph and attribution report.
    """
    trace = await TraceRepository.get_by_id(db, trace_id)
    if not trace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Trace '{trace_id}' not found."
        )

    # Check if evidence items already exist
    existing_items = await EvidenceRepository.get_by_trace_id(db, trace_id, classification=classification)

    if not existing_items and trace.graph_data:
        # Reconstruct graph and attribution report to generate complete evidence
        graph = InvestigationGraph(**trace.graph_data)
        engine = AttributionEngine()
        report = engine.evaluate_trace(trace_id=trace.id, graph=graph)

        generated_items = EvidenceGenerator.generate_trace_evidence(
            case_id=trace.case_id,
            trace_id=trace.id,
            graph=graph,
            attribution_report=report,
            config_snapshot=trace.config,
        )
        await EvidenceRepository.save_evidence_items(db, generated_items)
        existing_items = await EvidenceRepository.get_by_trace_id(db, trace_id, classification=classification)

    all_trace_items = await EvidenceRepository.get_by_trace_id(db, trace_id)

    observed_c = sum(1 for it in all_trace_items if it.classification == "OBSERVED")
    derived_c = sum(1 for it in all_trace_items if it.classification == "DERIVED")
    inferred_c = sum(1 for it in all_trace_items if it.classification == "INFERRED")
    human_c = sum(1 for it in all_trace_items if it.classification == "HUMAN_ACTION")

    return EvidenceChainResponse(
        trace_id=trace.id,
        case_id=trace.case_id,
        total_evidence_count=len(all_trace_items),
        observed_count=observed_c,
        derived_count=derived_c,
        inferred_count=inferred_c,
        human_action_count=human_c,
        items=[
            EvidenceItemResponse(
                id=it.id,
                case_id=it.case_id,
                trace_id=it.trace_id,
                evidence_type=it.evidence_type,
                classification=it.classification,
                title=it.title,
                description=it.description,
                source=it.source,
                source_reference=it.source_reference,
                payload=it.payload or {},
                parent_evidence_ids=it.parent_evidence_ids or [],
                content_hash=it.content_hash,
                engine_version=it.engine_version,
                configuration_snapshot=it.configuration_snapshot,
                collected_at=it.collected_at,
                analysis_timestamp=it.analysis_timestamp,
                created_at=it.created_at,
            )
            for it in existing_items
        ],
    )


@router.get("/cases/{case_id}/evidence", response_model=EvidenceChainResponse)
async def get_case_evidence(
    case_id: str,
    classification: Optional[str] = Query(None, description="Filter by OBSERVED, DERIVED, INFERRED, HUMAN_ACTION"),
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieve all evidence items compiled across all traces and actions for a case.
    """
    case = await CaseRepository.get_by_id(db, case_id)
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case '{case_id}' not found."
        )

    items = await EvidenceRepository.get_by_case_id(db, case_id, classification=classification)
    all_items = await EvidenceRepository.get_by_case_id(db, case_id)

    return EvidenceChainResponse(
        case_id=case.id,
        total_evidence_count=len(all_items),
        observed_count=sum(1 for it in all_items if it.classification == "OBSERVED"),
        derived_count=sum(1 for it in all_items if it.classification == "DERIVED"),
        inferred_count=sum(1 for it in all_items if it.classification == "INFERRED"),
        human_action_count=sum(1 for it in all_items if it.classification == "HUMAN_ACTION"),
        items=[
            EvidenceItemResponse(
                id=it.id,
                case_id=it.case_id,
                trace_id=it.trace_id,
                evidence_type=it.evidence_type,
                classification=it.classification,
                title=it.title,
                description=it.description,
                source=it.source,
                source_reference=it.source_reference,
                payload=it.payload or {},
                parent_evidence_ids=it.parent_evidence_ids or [],
                content_hash=it.content_hash,
                engine_version=it.engine_version,
                configuration_snapshot=it.configuration_snapshot,
                collected_at=it.collected_at,
                analysis_timestamp=it.analysis_timestamp,
                created_at=it.created_at,
            )
            for it in items
        ],
    )


@router.get("/evidence/{evidence_id}", response_model=EvidenceItemResponse)
async def get_evidence_by_id(
    evidence_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieve a single specific evidence item with its complete payload and provenance parent links.
    """
    item = await EvidenceRepository.get_by_id(db, evidence_id)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Evidence item '{evidence_id}' not found."
        )

    return EvidenceItemResponse(
        id=item.id,
        case_id=item.case_id,
        trace_id=item.trace_id,
        evidence_type=item.evidence_type,
        classification=item.classification,
        title=item.title,
        description=item.description,
        source=item.source,
        source_reference=item.source_reference,
        payload=item.payload or {},
        parent_evidence_ids=item.parent_evidence_ids or [],
        content_hash=item.content_hash,
        engine_version=item.engine_version,
        configuration_snapshot=item.configuration_snapshot,
        collected_at=item.collected_at,
        analysis_timestamp=item.analysis_timestamp,
        created_at=item.created_at,
    )


@router.post("/cases/{case_id}/audit", response_model=AuditEventResponse, status_code=status.HTTP_201_CREATED)
async def record_audit_event(
    case_id: str,
    event_in: AuditEventCreateRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Record an immutable investigator action in the case audit log.
    Computes a cryptographic SHA-256 content hash for tamper-evident verification.
    """
    case = await CaseRepository.get_by_id(db, case_id)
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case '{case_id}' not found."
        )

    now = datetime.now(timezone.utc)
    event_id = str(uuid.uuid4())

    hash_payload = {
        "event_id": event_id,
        "case_id": case_id,
        "actor_id": event_in.actor_id,
        "event_type": event_in.event_type,
        "action_summary": event_in.action_summary,
        "metadata": event_in.metadata,
        "created_at": now.isoformat(),
    }
    content_hash = compute_content_hash(hash_payload)

    audit_domain = AuditEvent(
        id=event_id,
        case_id=case_id,
        trace_id=event_in.trace_id,
        actor_id=event_in.actor_id,
        event_type=event_in.event_type,
        action_summary=event_in.action_summary,
        metadata=event_in.metadata,
        content_hash=content_hash,
        created_at=now,
    )

    saved_model = await AuditRepository.record_event(db, audit_domain)

    return AuditEventResponse(
        id=saved_model.id,
        case_id=saved_model.case_id,
        trace_id=saved_model.trace_id,
        actor_id=saved_model.actor_id,
        event_type=saved_model.event_type,
        action_summary=saved_model.action_summary,
        metadata=saved_model.metadata_json or {},
        content_hash=saved_model.content_hash,
        created_at=saved_model.created_at,
    )


@router.get("/cases/{case_id}/audit", response_model=List[AuditEventResponse])
async def list_case_audit_events(
    case_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieve the chronological, append-only investigator audit trail for a case.
    """
    case = await CaseRepository.get_by_id(db, case_id)
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case '{case_id}' not found."
        )

    events = await AuditRepository.get_by_case_id(db, case_id)

    return [
        AuditEventResponse(
            id=ev.id,
            case_id=ev.case_id,
            trace_id=ev.trace_id,
            actor_id=ev.actor_id,
            event_type=ev.event_type,
            action_summary=ev.action_summary,
            metadata=ev.metadata_json or {},
            content_hash=ev.content_hash,
            created_at=ev.created_at,
        )
        for ev in events
    ]


@router.post("/cases/{case_id}/attributions/{candidate_address}/review", response_model=AttributionReviewResponse)
async def review_attribution_hypothesis(
    case_id: str,
    candidate_address: str,
    review_in: AttributionReviewRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Human Investigator Decision Gate: Formally ACCEPT or REJECT an automated VASP attribution hypothesis.
    Creates an append-only audit event and an immutable HUMAN_ACTION evidence item linked to the attribution.
    Preserves human-in-the-loop legal accountability.
    """
    case = await CaseRepository.get_by_id(db, case_id)
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case '{case_id}' not found."
        )

    decision_clean = review_in.decision.upper().strip()
    if decision_clean not in ("ACCEPT", "REJECT"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid decision '{review_in.decision}'. Expected 'ACCEPT' or 'REJECT'."
        )

    now = datetime.now(timezone.utc)
    event_type = AuditEventType.ATTRIBUTION_ACCEPTED if decision_clean == "ACCEPT" else AuditEventType.ATTRIBUTION_REJECTED
    action_desc = (
        f"Investigator {review_in.actor_id} ACCEPTED attribution hypothesis for wallet {candidate_address}."
        if decision_clean == "ACCEPT"
        else f"Investigator {review_in.actor_id} REJECTED attribution hypothesis for wallet {candidate_address} as inconclusive."
    )
    if review_in.notes:
        action_desc += f" Justification: {review_in.notes}"

    event_id = str(uuid.uuid4())
    meta = {
        "candidate_address": candidate_address,
        "decision": decision_clean,
        "notes": review_in.notes,
    }
    content_hash = compute_content_hash({
        "event_id": event_id,
        "case_id": case_id,
        "actor_id": review_in.actor_id,
        "decision": decision_clean,
        "candidate_address": candidate_address,
        "timestamp": now.isoformat(),
    })

    audit_domain = AuditEvent(
        id=event_id,
        case_id=case_id,
        actor_id=review_in.actor_id,
        event_type=event_type,
        action_summary=action_desc,
        metadata=meta,
        content_hash=content_hash,
        created_at=now,
    )
    await AuditRepository.record_event(db, audit_domain)

    # Also create a HUMAN_ACTION tier evidence item
    human_ev = EvidenceGenerator.generate_human_action_evidence(
        audit_event=audit_domain,
        parent_evidence_id=f"ev_sweep_{candidate_address[:16]}",
    )
    await EvidenceRepository.save_evidence_items(db, [human_ev])

    return AttributionReviewResponse(
        status="SUCCESS",
        candidate_address=candidate_address,
        decision=decision_clean,
        evidence_id=human_ev.id,
        audit_event_id=event_id,
        reviewed_at=now,
    )
