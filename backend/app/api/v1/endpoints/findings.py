import uuid
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.persistence.db import get_db
from backend.app.persistence.case_repository import CaseRepository
from backend.app.persistence.trace_repository import TraceRepository
from backend.app.persistence.evidence_repository import EvidenceRepository
from backend.app.persistence.audit_repository import AuditRepository
from backend.app.persistence.finding_repository import FindingRepository
from backend.app.domain.models import InvestigationGraph
from backend.app.domain.attribution.engine import AttributionEngine
from backend.app.domain.evidence.models import AuditEvent, AuditEventType
from backend.app.domain.evidence.hasher import compute_content_hash
from backend.app.domain.findings.models import FindingStatus, FindingSeverity, ForensicFinding
from backend.app.domain.findings.generator import FindingsGenerator
from backend.app.api.v1.schemas.findings import (
    FindingResponse,
    FindingListResponse,
    FindingReviewRequest,
)

router = APIRouter(tags=["Findings"])


async def _process_findings_for_trace(
    db: AsyncSession,
    case_id: str,
    trace,
) -> List[ForensicFinding]:
    """
    Helper to deterministically generate, persist, and retrieve findings for a trace.
    """
    if not trace.graph_data:
        return []

    graph = InvestigationGraph(**trace.graph_data)

    # 1. Evaluate attribution report
    attr_engine = AttributionEngine()
    attr_report = attr_engine.evaluate_trace(trace_id=trace.id, graph=graph)

    # 2. Fetch existing evidence items for evidence linkage
    evidence_models = await EvidenceRepository.get_by_trace(db, trace.id)
    from backend.app.domain.evidence.models import EvidenceItem
    evidence_items = [
        EvidenceItem(
            id=em.id,
            case_id=em.case_id,
            trace_id=em.trace_id,
            evidence_type=em.evidence_type,
            classification=em.classification,
            title=em.title,
            description=em.description,
            source=em.source,
            source_reference=em.source_reference,
            payload=em.payload,
            parent_evidence_ids=em.parent_evidence_ids,
            content_hash=em.content_hash,
            engine_version=em.engine_version,
            configuration_snapshot=em.configuration_snapshot,
            collected_at=em.collected_at,
            analysis_timestamp=em.analysis_timestamp,
        )
        for em in evidence_models
    ]

    # 3. Fetch existing persisted review records
    existing_records = await FindingRepository.get_by_trace(db, trace.id)
    review_states = {
        r.id: {
            "status": r.status,
            "reviewed_by": r.reviewed_by,
            "reviewed_at": r.reviewed_at,
            "review_notes": r.review_notes,
        }
        for r in existing_records
    }

    # 4. Generate deterministic findings with review overlay
    generated = FindingsGenerator.generate_findings(
        case_id=case_id,
        trace_id=trace.id,
        graph=graph,
        attribution_report=attr_report,
        evidence_items=evidence_items,
        persisted_reviews=review_states,
    )

    # 5. Upsert to ensure all generated findings exist in DB
    await FindingRepository.upsert_findings(db, generated)
    return generated


@router.get("/cases/{case_id}/findings", response_model=FindingListResponse)
async def get_case_findings(
    case_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieve all investigative forensic findings and alerts associated with a case.
    Derives real signals across the case's completed multi-hop traces.
    """
    case = await CaseRepository.get_by_id(db, case_id)
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case '{case_id}' not found."
        )

    traces = await TraceRepository.get_by_case(db, case_id)
    if not traces:
        return FindingListResponse(
            case_id=case_id,
            total=0,
            open_count=0,
            reviewed_count=0,
            dismissed_count=0,
            findings=[],
        )

    all_findings: List[ForensicFinding] = []
    seen_ids = set()

    for trace in traces:
        trace_findings = await _process_findings_for_trace(db, case_id, trace)
        for f in trace_findings:
            if f.finding_id not in seen_ids:
                seen_ids.add(f.finding_id)
                all_findings.append(f)

    # Calculate count metrics
    open_c = sum(1 for f in all_findings if f.status == FindingStatus.OPEN)
    rev_c = sum(1 for f in all_findings if f.status == FindingStatus.REVIEWED)
    dism_c = sum(1 for f in all_findings if f.status == FindingStatus.DISMISSED)

    crit_c = sum(1 for f in all_findings if f.severity == FindingSeverity.CRITICAL)
    high_c = sum(1 for f in all_findings if f.severity == FindingSeverity.HIGH)
    med_c = sum(1 for f in all_findings if f.severity == FindingSeverity.MEDIUM)
    low_c = sum(1 for f in all_findings if f.severity == FindingSeverity.LOW)
    info_c = sum(1 for f in all_findings if f.severity == FindingSeverity.INFO)

    return FindingListResponse(
        case_id=case_id,
        trace_id=traces[0].id if traces else None,
        total=len(all_findings),
        open_count=open_c,
        reviewed_count=rev_c,
        dismissed_count=dism_c,
        critical_count=crit_c,
        high_count=high_c,
        medium_count=med_c,
        low_count=low_c,
        info_count=info_c,
        findings=[FindingResponse.from_domain(f) for f in all_findings],
    )


@router.get("/traces/{trace_id}/findings", response_model=FindingListResponse)
async def get_trace_findings(
    trace_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieve forensic findings for a specific trace execution.
    """
    trace = await TraceRepository.get_by_id(db, trace_id)
    if not trace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Trace '{trace_id}' not found."
        )

    findings = await _process_findings_for_trace(db, trace.case_id, trace)

    open_c = sum(1 for f in findings if f.status == FindingStatus.OPEN)
    rev_c = sum(1 for f in findings if f.status == FindingStatus.REVIEWED)
    dism_c = sum(1 for f in findings if f.status == FindingStatus.DISMISSED)

    crit_c = sum(1 for f in findings if f.severity == FindingSeverity.CRITICAL)
    high_c = sum(1 for f in findings if f.severity == FindingSeverity.HIGH)
    med_c = sum(1 for f in findings if f.severity == FindingSeverity.MEDIUM)
    low_c = sum(1 for f in findings if f.severity == FindingSeverity.LOW)
    info_c = sum(1 for f in findings if f.severity == FindingSeverity.INFO)

    return FindingListResponse(
        case_id=trace.case_id,
        trace_id=trace.id,
        total=len(findings),
        open_count=open_c,
        reviewed_count=rev_c,
        dismissed_count=dism_c,
        critical_count=crit_c,
        high_count=high_c,
        medium_count=med_c,
        low_count=low_c,
        info_count=info_c,
        findings=[FindingResponse.from_domain(f) for f in findings],
    )


@router.post("/cases/{case_id}/findings/{finding_id}/review", response_model=FindingResponse)
async def review_finding(
    case_id: str,
    finding_id: str,
    review_req: FindingReviewRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Update the investigator review status of a forensic finding (OPEN -> REVIEWED | DISMISSED).
    Logs an immutable audit event to maintain statutory forensic chain-of-custody.
    """
    case = await CaseRepository.get_by_id(db, case_id)
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case '{case_id}' not found."
        )

    finding = await FindingRepository.get_by_id(db, finding_id)
    if not finding or finding.case_id != case_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Finding '{finding_id}' not found in case '{case_id}'."
        )

    updated_record = await FindingRepository.update_review_status(
        session=db,
        finding_id=finding_id,
        case_id=case_id,
        status=review_req.status,
        reviewed_by=review_req.reviewed_by or "investigator",
        review_notes=review_req.notes,
    )

    # Record immutable audit event
    now_utc = datetime.now(timezone.utc)
    audit_ev = AuditEvent(
        id=str(uuid.uuid4()),
        case_id=case_id,
        trace_id=finding.trace_id,
        actor_id=review_req.reviewed_by or "investigator",
        event_type=AuditEventType.FINDING_REVIEWED,
        action_summary=f"Investigator marked finding '{finding.title}' as {review_req.status.value}. Notes: {review_req.notes or 'None'}",
        metadata={
            "finding_id": finding_id,
            "finding_type": finding.finding_type,
            "status": review_req.status.value,
            "notes": review_req.notes,
        },
        content_hash=compute_content_hash({
            "finding_id": finding_id,
            "status": review_req.status.value,
            "actor": review_req.reviewed_by,
            "timestamp": now_utc.isoformat(),
        }),
        created_at=now_utc,
    )
    await AuditRepository.record_event(db, audit_ev)

    domain_finding = ForensicFinding(
        finding_id=updated_record.id,
        case_id=updated_record.case_id,
        trace_id=updated_record.trace_id or "",
        severity=FindingSeverity(updated_record.severity),
        finding_type=updated_record.finding_type,
        title=updated_record.title,
        description=updated_record.description,
        timestamp=updated_record.created_at,
        source_signal=updated_record.source_signal,
        confidence=float(updated_record.confidence) if updated_record.confidence is not None else None,
        related_address=updated_record.related_address,
        related_tx_hash=updated_record.related_tx_hash,
        related_vasp=updated_record.related_vasp,
        evidence_refs=updated_record.evidence_refs or [],
        status=FindingStatus(updated_record.status),
        reviewed_by=updated_record.reviewed_by,
        reviewed_at=updated_record.reviewed_at,
        review_notes=updated_record.review_notes,
        graph_node_id=updated_record.graph_node_id,
        graph_edge_id=updated_record.graph_edge_id,
    )

    return FindingResponse.from_domain(domain_finding)
