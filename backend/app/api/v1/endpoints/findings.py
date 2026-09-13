import uuid
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Query
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
from backend.app.core.auth import Role, OfficerSession
from backend.app.api.deps import get_current_officer, require_roles

router = APIRouter(tags=["Findings"])


async def _process_findings_for_trace(
    db: AsyncSession,
    case_id: str,
    trace,
    officer: OfficerSession,
) -> List[ForensicFinding]:
    """
    Helper to deterministically generate, persist, and retrieve findings for a trace.
    Scoped to the officer's tenant hierarchy.
    """
    if not trace.graph_data:
        return []

    graph = InvestigationGraph(**trace.graph_data)

    # 1. Evaluate attribution report
    attr_engine = AttributionEngine()
    attr_report = attr_engine.evaluate_trace(trace_id=trace.id, graph=graph)

    # 2. Fetch existing evidence items for evidence linkage
    evidence_models = await EvidenceRepository.get_by_trace(
        db,
        trace.id,
        tenant_id=officer.tenant_id,
    )
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
    existing_records = await FindingRepository.get_by_trace(
        db,
        trace.id,
        tenant_id=officer.tenant_id,
    )
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

    # 5. Upsert to ensure all generated findings exist in DB with tenant scoping
    await FindingRepository.upsert_findings(
        db,
        generated,
        tenant_id=officer.tenant_id,
        district_id=officer.district_id,
        police_station_id=officer.police_station_id,
    )
    return generated


@router.get("/cases/{case_id}/findings", response_model=FindingListResponse)
async def get_case_findings(
    case_id: str,
    cursor: Optional[str] = Query(None, description="Base64 keyset pagination cursor"),
    limit: int = Query(50, ge=1, le=100, description="Maximum findings to return"),
    db: AsyncSession = Depends(get_db),
    current_officer: OfficerSession = Depends(get_current_officer),
):
    """
    Retrieve all investigative forensic findings and alerts associated with a case.
    Supports keyset pagination with cursor.
    Enforces tenant boundaries; cross-tenant lookup returns HTTP 404.
    """
    case = await CaseRepository.get_by_id(db, case_id, tenant_id=current_officer.tenant_id)
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "NOT_FOUND",
                "message": f"Case '{case_id}' not found.",
            }
        )

    traces = await TraceRepository.get_by_case(db, case_id, tenant_id=current_officer.tenant_id)
    if not traces:
        return FindingListResponse(
            case_id=case_id,
            total=0,
            open_count=0,
            reviewed_count=0,
            dismissed_count=0,
            findings=[],
            items=[],
            next_cursor=None,
            has_more=False,
        )

    for trace in traces:
        await _process_findings_for_trace(db, case_id, trace, current_officer)

    # Metrics counts across entire case
    all_case_findings = await FindingRepository.get_by_case(db, case_id, tenant_id=current_officer.tenant_id)
    open_c = sum(1 for f in all_case_findings if f.status == "OPEN")
    rev_c = sum(1 for f in all_case_findings if f.status == "REVIEWED")
    dism_c = sum(1 for f in all_case_findings if f.status == "DISMISSED")

    crit_c = sum(1 for f in all_case_findings if f.severity == "CRITICAL")
    high_c = sum(1 for f in all_case_findings if f.severity == "HIGH")
    med_c = sum(1 for f in all_case_findings if f.severity == "MEDIUM")
    low_c = sum(1 for f in all_case_findings if f.severity == "LOW")
    info_c = sum(1 for f in all_case_findings if f.severity == "INFO")

    try:
        records, total, next_cursor, has_more = await FindingRepository.get_by_case_keyset(
            db, case_id, cursor=cursor, limit=limit, tenant_id=current_officer.tenant_id
        )
    except ValueError as ex:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_CURSOR", "message": str(ex)},
        )

    finding_items = [FindingResponse.from_record(r) for r in records]

    return FindingListResponse(
        case_id=case_id,
        trace_id=traces[0].id if traces else None,
        total=total,
        open_count=open_c,
        reviewed_count=rev_c,
        dismissed_count=dism_c,
        critical_count=crit_c,
        high_count=high_c,
        medium_count=med_c,
        low_count=low_c,
        info_count=info_c,
        findings=finding_items,
        items=finding_items,
        next_cursor=next_cursor,
        has_more=has_more,
    )


@router.get("/traces/{trace_id}/findings", response_model=FindingListResponse)
async def get_trace_findings(
    trace_id: str,
    db: AsyncSession = Depends(get_db),
    current_officer: OfficerSession = Depends(get_current_officer),
):
    """
    Retrieve forensic findings for a specific trace execution.
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

    findings = await _process_findings_for_trace(db, trace.case_id, trace, current_officer)

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
        items=[FindingResponse.from_domain(f) for f in findings],
    )


@router.post("/cases/{case_id}/findings/{finding_id}/review", response_model=FindingResponse)
async def review_finding(
    case_id: str,
    finding_id: str,
    review_req: FindingReviewRequest,
    db: AsyncSession = Depends(get_db),
    current_officer: OfficerSession = Depends(require_roles([Role.INVESTIGATING_OFFICER, Role.SUPERVISOR, Role.ADMIN])),
):
    """
    Update the investigator review status of a forensic finding (OPEN -> REVIEWED | DISMISSED).
    Enforces tenant boundaries; cross-tenant review returns HTTP 404.
    """
    case = await CaseRepository.get_by_id(db, case_id, tenant_id=current_officer.tenant_id)
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "NOT_FOUND",
                "message": f"Case '{case_id}' not found.",
            }
        )

    finding = await FindingRepository.get_by_id(db, finding_id, tenant_id=current_officer.tenant_id)
    if not finding or finding.case_id != case_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "NOT_FOUND",
                "message": f"Finding '{finding_id}' not found in case '{case_id}'.",
            }
        )

    reviewed_by = review_req.reviewed_by or current_officer.name or "investigator"
    updated_record = await FindingRepository.update_review_status(
        session=db,
        finding_id=finding_id,
        case_id=case_id,
        status=review_req.status,
        reviewed_by=reviewed_by,
        review_notes=review_req.notes,
        tenant_id=current_officer.tenant_id,
    )

    # Record immutable audit event with tenant attributes
    now_utc = datetime.now(timezone.utc)
    audit_ev = AuditEvent(
        id=str(uuid.uuid4()),
        case_id=case_id,
        trace_id=finding.trace_id,
        actor_id=current_officer.officer_id,
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
            "actor": reviewed_by,
            "timestamp": now_utc.isoformat(),
        }),
        created_at=now_utc,
    )
    await AuditRepository.record_event(
        db,
        audit_ev,
        tenant_id=current_officer.tenant_id,
        district_id=current_officer.district_id,
        police_station_id=current_officer.police_station_id,
    )

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
