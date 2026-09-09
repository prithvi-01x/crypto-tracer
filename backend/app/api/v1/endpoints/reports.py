import os
import uuid
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status, Response
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.config import settings
from backend.app.persistence.db import get_db
from backend.app.persistence.case_repository import CaseRepository
from backend.app.persistence.trace_repository import TraceRepository
from backend.app.persistence.report_repository import ReportRepository
from backend.app.persistence.evidence_repository import EvidenceRepository
from backend.app.persistence.audit_repository import AuditRepository
from backend.app.persistence.models import ReportModel
from backend.app.domain.models import InvestigationGraph
from backend.app.domain.attribution.engine import AttributionEngine
from backend.app.domain.reports.models import ReportType
from backend.app.domain.reports.dossier_generator import EvidenceDossierGenerator
from backend.app.domain.reports.bnss94_generator import BNSS94DraftGenerator
from backend.app.domain.evidence.generator import EvidenceGenerator
from backend.app.domain.evidence.models import AuditEvent, AuditEventType, EvidenceItem, EvidenceClassification, EvidenceType as EvType
from backend.app.domain.evidence.hasher import compute_content_hash
from backend.app.api.v1.schemas.reports import (
    EvidenceDossierCreateRequest,
    BNSS94DraftCreateRequest,
    ReportResponse,
)

router = APIRouter(tags=["Reports & Legal Export"])


def _ensure_report_dir(case_id: str) -> str:
    safe_case_id = "".join(c for c in case_id if c.isalnum() or c in ("-", "_"))
    base_dir = os.path.abspath(settings.REPORTS_DIR)
    dir_path = os.path.abspath(os.path.join(base_dir, safe_case_id))
    if not dir_path.startswith(base_dir):
        raise ValueError(f"Invalid case directory path: {case_id}")
    os.makedirs(dir_path, exist_ok=True)
    return dir_path


@router.post("/cases/{case_id}/reports/dossier", response_model=ReportResponse, status_code=status.HTTP_201_CREATED)
async def generate_evidence_dossier(
    case_id: str,
    request: EvidenceDossierCreateRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Generate an official Forensic Evidence Dossier PDF complying with Section 63 BSA electronic evidence standards.
    Embeds multi-hop graph snapshot, observed transaction records, derived metrics,
    accepted attribution hypothesis, and cryptographic SHA-256 integrity seal.
    """
    case = await CaseRepository.get_by_id(db, case_id)
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case '{case_id}' not found."
        )

    trace = await TraceRepository.get_by_id(db, request.trace_id)
    if not trace or trace.case_id != case_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Trace '{request.trace_id}' not found for case '{case_id}'."
        )

    if not trace.graph_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Trace does not contain transaction graph data."
        )

    # 1. Reconstruct graph and evaluate attribution report
    graph = InvestigationGraph(**trace.graph_data)
    engine = AttributionEngine()
    attribution_report = engine.evaluate_trace(trace_id=trace.id, graph=graph)

    # 2. Retrieve or generate evidence items
    evidence_items = await EvidenceRepository.get_by_trace_id(db, trace.id)
    if not evidence_items:
        evidence_items = EvidenceGenerator.generate_trace_evidence(
            case_id=case.id,
            trace_id=trace.id,
            graph=graph,
            attribution_report=attribution_report,
            config_snapshot=trace.config,
        )
        await EvidenceRepository.save_evidence_items(db, evidence_items)

    # 3. Generate PDF
    try:
        pdf_bytes, report_hash, meta = EvidenceDossierGenerator.generate_pdf(
            case=case,
            trace=trace,
            graph=graph,
            attribution_report=attribution_report,
            evidence_items=evidence_items,
            investigator_name=request.investigator_name,
            investigator_rank=request.investigator_rank,
            police_station=request.police_station,
            include_graph_snapshot=request.include_graph_snapshot,
            notes=request.notes,
        )
    except Exception as e:
        logger.error(f"Failed to generate evidence dossier: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "REPORT_GENERATION_FAILED",
                "message": f"Evidence dossier compilation failed: {e}",
                "case_id": case_id,
            }
        )

    # 4. Persist PDF file to disk
    report_id = str(uuid.uuid4())
    safe_fir = case.fir_number.replace("/", "-").replace(" ", "_")
    file_name = f"Dossier_{safe_fir}_{report_id[:8]}.pdf"
    report_dir = _ensure_report_dir(case_id)
    file_path = os.path.join(report_dir, file_name)

    with open(file_path, "wb") as f:
        f.write(pdf_bytes)

    # 5. Persist Report model in DB
    report_model = ReportModel(
        id=report_id,
        case_id=case.id,
        trace_id=trace.id,
        report_type=ReportType.EVIDENCE_DOSSIER.value,
        title=f"Evidence Dossier: {case.fir_number}",
        file_path=file_path,
        file_size_bytes=len(pdf_bytes),
        content_hash=report_hash,
        generated_by=request.investigator_name,
        metadata_json=meta,
    )
    await ReportRepository.create_report(db, report_model)

    # 6. Record Audit Event & Human Action Evidence Item
    now = datetime.now(timezone.utc)
    audit_ev = AuditEvent(
        id=str(uuid.uuid4()),
        case_id=case.id,
        trace_id=trace.id,
        actor_id=request.investigator_name,
        event_type=AuditEventType.REPORT_GENERATED,
        action_summary=f"Investigator {request.investigator_name} generated Section 63 BSA Evidence Dossier (SHA-256: {report_hash[:16]}...).",
        metadata={
            "report_id": report_id,
            "report_type": ReportType.EVIDENCE_DOSSIER.value,
            "report_hash": report_hash,
            "file_size": len(pdf_bytes),
        },
        content_hash=compute_content_hash({
            "report_id": report_id,
            "case_id": case.id,
            "report_hash": report_hash,
            "actor": request.investigator_name,
            "time": now.isoformat(),
        }),
        created_at=now,
    )
    await AuditRepository.record_event(db, audit_ev)

    return ReportResponse(
        id=report_model.id,
        case_id=report_model.case_id,
        trace_id=report_model.trace_id,
        report_type=ReportType.EVIDENCE_DOSSIER,
        title=report_model.title,
        file_name=file_name,
        file_size_bytes=report_model.file_size_bytes,
        content_hash=report_model.content_hash,
        generated_by=report_model.generated_by,
        metadata=report_model.metadata_json or {},
        created_at=report_model.created_at,
        download_url=f"/api/v1/reports/{report_model.id}/download",
    )


@router.post("/cases/{case_id}/reports/bnss94", response_model=ReportResponse, status_code=status.HTTP_201_CREATED)
async def generate_bnss94_draft(
    case_id: str,
    request: BNSS94DraftCreateRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Generate a Draft Section 94 BNSS Record-Production Request PDF.
    Prominently marked 'DRAFT — FOR OFFICER REVIEW ONLY'.
    Requisitions subscriber KYC, full account ledgers, P2P counterparties, and digital access logs.
    """
    case = await CaseRepository.get_by_id(db, case_id)
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case '{case_id}' not found."
        )

    trace = await TraceRepository.get_by_id(db, request.trace_id)
    if not trace or trace.case_id != case_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Trace '{request.trace_id}' not found for case '{case_id}'."
        )

    # 1. Reconstruct graph and evaluate attribution
    attribution_report = None
    if trace.graph_data:
        graph = InvestigationGraph(**trace.graph_data)
        engine = AttributionEngine()
        attribution_report = engine.evaluate_trace(trace_id=trace.id, graph=graph)

        # Boundary checks for Section 94 BNSS requisitions
        # 1. If trace has no transactions
        if len(graph.edges) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "NO_TRANSFERS_FOUND",
                    "message": "Cannot generate Section 94 BNSS notice: Trace contains no on-chain transactions or VASP endpoints to requisition.",
                }
            )

        # 2. Check candidate address or target for mixer / obfuscation boundary
        target_addr = request.candidate_address or (attribution_report.best_candidate.candidate_address if attribution_report and attribution_report.best_candidate else None)
        target_name = (request.target_vasp or (attribution_report.best_candidate.vasp_name if attribution_report and attribution_report.best_candidate else "")).lower()

        if (target_addr and engine.registry.is_mixer(target_addr)) or "mixer" in target_name or "tornado" in target_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "MIXER_BOUNDARY",
                    "message": (
                        "Cannot generate Section 94 BNSS notice: Target address is a decentralized privacy mixer/tumbler "
                        "with no custodial entity or KYC records to requisition."
                    ),
                }
            )

        # 3. Check for low confidence or unidentified entity when no manual VASP override is provided
        if not request.target_vasp:
            if attribution_report and attribution_report.best_candidate:
                best = attribution_report.best_candidate
                if best.vasp_id in ("unknown_entity", "unidentified") or best.confidence < 0.40 or best.is_low_confidence:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail={
                            "code": "LOW_CONFIDENCE",
                            "message": (
                                "Cannot generate Section 94 BNSS notice: Attribution confidence is insufficient. "
                                "Target address remains an unhosted or unidentified wallet with no verified VASP custodian."
                            ),
                        }
                    )
            elif not attribution_report or not attribution_report.best_candidate:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "code": "NO_VASP_FOUND",
                        "message": "Cannot generate Section 94 BNSS notice: No candidate VASP identified in the transaction graph.",
                    }
                )

    # 2. Generate PDF
    try:
        pdf_bytes, report_hash, meta = BNSS94DraftGenerator.generate_pdf(
            case=case,
            trace=trace,
            attribution_report=attribution_report,
            target_vasp_override=request.target_vasp,
            candidate_address_override=request.candidate_address,
            investigator_name=request.investigator_name,
            investigator_rank=request.investigator_rank,
            police_station=request.police_station,
            court_jurisdiction=request.court_jurisdiction,
            compliance_email=request.compliance_email,
            urgency_hours=request.urgency_hours,
            notes=request.notes,
        )
    except Exception as e:
        logger.error(f"Failed to generate Section 94 notice: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "REPORT_GENERATION_FAILED",
                "message": f"Section 94 BNSS notice compilation failed: {e}",
                "case_id": case_id,
            }
        )

    # 3. Persist PDF file to disk
    report_id = str(uuid.uuid4())
    safe_fir = case.fir_number.replace("/", "-").replace(" ", "_")
    file_name = f"Draft_BNSS94_{safe_fir}_{report_id[:8]}.pdf"
    report_dir = _ensure_report_dir(case_id)
    file_path = os.path.join(report_dir, file_name)

    with open(file_path, "wb") as f:
        f.write(pdf_bytes)

    # 4. Persist Report model in DB
    report_model = ReportModel(
        id=report_id,
        case_id=case.id,
        trace_id=trace.id,
        report_type=ReportType.SECTION_94_BNSS.value,
        title=f"Draft Section 94 BNSS Notice: {case.fir_number}",
        file_path=file_path,
        file_size_bytes=len(pdf_bytes),
        content_hash=report_hash,
        generated_by=request.investigator_name,
        metadata_json=meta,
    )
    await ReportRepository.create_report(db, report_model)

    # 5. Record Audit Event
    now = datetime.now(timezone.utc)
    audit_ev = AuditEvent(
        id=str(uuid.uuid4()),
        case_id=case.id,
        trace_id=trace.id,
        actor_id=request.investigator_name,
        event_type=AuditEventType.REPORT_GENERATED,
        action_summary=f"Investigator {request.investigator_name} generated Draft Section 94 BNSS Notice for officer review (Target: {meta.get('target_vasp')}).",
        metadata={
            "report_id": report_id,
            "report_type": ReportType.SECTION_94_BNSS.value,
            "report_hash": report_hash,
            "target_vasp": meta.get("target_vasp"),
        },
        content_hash=compute_content_hash({
            "report_id": report_id,
            "case_id": case.id,
            "report_hash": report_hash,
            "actor": request.investigator_name,
            "time": now.isoformat(),
        }),
        created_at=now,
    )
    await AuditRepository.record_event(db, audit_ev)

    return ReportResponse(
        id=report_model.id,
        case_id=report_model.case_id,
        trace_id=report_model.trace_id,
        report_type=ReportType.SECTION_94_BNSS,
        title=report_model.title,
        file_name=file_name,
        file_size_bytes=report_model.file_size_bytes,
        content_hash=report_model.content_hash,
        generated_by=report_model.generated_by,
        metadata=report_model.metadata_json or {},
        created_at=report_model.created_at,
        download_url=f"/api/v1/reports/{report_model.id}/download",
    )


@router.get("/cases/{case_id}/reports", response_model=List[ReportResponse])
async def list_case_reports(
    case_id: str,
    report_type: Optional[str] = Query(None, description="Filter by EVIDENCE_DOSSIER or SECTION_94_BNSS"),
    db: AsyncSession = Depends(get_db),
):
    """
    List all generated forensic dossiers and legal drafts for a case.
    """
    case = await CaseRepository.get_by_id(db, case_id)
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case '{case_id}' not found."
        )

    reports = await ReportRepository.get_by_case_id(db, case_id, report_type=report_type)

    return [
        ReportResponse(
            id=r.id,
            case_id=r.case_id,
            trace_id=r.trace_id,
            report_type=ReportType(r.report_type),
            title=r.title,
            file_name=os.path.basename(r.file_path),
            file_size_bytes=r.file_size_bytes,
            content_hash=r.content_hash,
            generated_by=r.generated_by,
            metadata=r.metadata_json or {},
            created_at=r.created_at,
            download_url=f"/api/v1/reports/{r.id}/download",
        )
        for r in reports
    ]


@router.get("/reports/{report_id}", response_model=ReportResponse)
async def get_report_by_id(
    report_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get metadata and content hash of a specific report.
    """
    r = await ReportRepository.get_by_id(db, report_id)
    if not r:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report '{report_id}' not found."
        )

    return ReportResponse(
        id=r.id,
        case_id=r.case_id,
        trace_id=r.trace_id,
        report_type=ReportType(r.report_type),
        title=r.title,
        file_name=os.path.basename(r.file_path),
        file_size_bytes=r.file_size_bytes,
        content_hash=r.content_hash,
        generated_by=r.generated_by,
        metadata=r.metadata_json or {},
        created_at=r.created_at,
        download_url=f"/api/v1/reports/{r.id}/download",
    )


@router.get("/reports/{report_id}/download")
async def download_report_pdf(
    report_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Download or stream the generated PDF document with proper MIME headers.
    """
    report = await ReportRepository.get_by_id(db, report_id)
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report '{report_id}' not found."
        )

    if not os.path.exists(report.file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report file on disk could not be located."
        )

    base_dir = os.path.abspath(settings.REPORTS_DIR)
    abs_file_path = os.path.abspath(report.file_path)
    if not abs_file_path.startswith(base_dir):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access to specified report path is denied."
        )

    filename = os.path.basename(report.file_path)
    return FileResponse(
        path=report.file_path,
        media_type="application/pdf",
        filename=filename,
    )
