import os
import uuid
import hmac
import hashlib
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Union
from fastapi import APIRouter, Depends, HTTPException, Query, Header, Request, Response, status
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
from backend.app.domain.reports.bsa63_generator import Section63BSAGenerator
from backend.app.domain.evidence.generator import EvidenceGenerator
from backend.app.domain.evidence.models import AuditEvent, AuditEventType
from backend.app.domain.evidence.hasher import compute_content_hash
from backend.app.services.storage import get_storage_service
from backend.app.worker.queue import ReportJobPayload, get_report_queue
from backend.app.api.v1.schemas.reports import (
    EvidenceDossierCreateRequest,
    BNSS94DraftCreateRequest,
    Section63BSACreateRequest,
    ReportResponse,
    ReportJobStatusResponse,
    PresignedUrlRequest,
    PresignedUrlResponse,
)
from backend.app.core.auth import Role, OfficerSession
from backend.app.api.deps import get_current_officer, require_roles
from backend.app.logging import logger

router = APIRouter(tags=["Reports & Legal Export"])


def _ensure_report_dir(case_id: str) -> str:
    safe_case_id = "".join(c for c in case_id if c.isalnum() or c in ("-", "_"))
    base_dir = os.path.abspath(settings.REPORTS_DIR)
    dir_path = os.path.abspath(os.path.join(base_dir, safe_case_id))
    if not dir_path.startswith(base_dir):
        raise ValueError(f"Invalid case directory path: {case_id}")
    os.makedirs(dir_path, exist_ok=True)
    return dir_path


def _is_sync_request(sync: Optional[bool], prefer: Optional[str]) -> bool:
    """Determine whether to execute report compilation synchronously or asynchronously."""
    if sync is not None:
        return sync
    if prefer and "respond-async" in prefer.lower():
        return False
    # By default, run synchronously in test/dev for fast execution and backward compatibility
    return settings.APP_ENV in ("test", "development")


@router.post(
    "/cases/{case_id}/reports/dossier",
    response_model=Union[ReportResponse, ReportJobStatusResponse],
    status_code=status.HTTP_201_CREATED,
)
async def generate_evidence_dossier(
    case_id: str,
    request: EvidenceDossierCreateRequest,
    response: Response,
    sync: Optional[bool] = Query(None, description="Force synchronous (True) or asynchronous (False) execution"),
    prefer: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
    current_officer: OfficerSession = Depends(require_roles([Role.INVESTIGATING_OFFICER, Role.SUPERVISOR, Role.ADMIN])),
):
    """
    Generate an official Forensic Evidence Dossier PDF complying with Section 63 BSA electronic evidence standards.
    Supports dual-mode sync (201 Created) or async (202 Accepted with poll URL).
    Enforces tenant boundaries; cross-tenant requests return HTTP 404.
    """
    case = await CaseRepository.get_by_id(db, case_id, tenant_id=current_officer.tenant_id)
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "NOT_FOUND",
                "message": f"Case '{case_id}' not found.",
            },
        )

    trace = await TraceRepository.get_by_id(db, request.trace_id, tenant_id=current_officer.tenant_id)
    if not trace or trace.case_id != case_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "NOT_FOUND",
                "message": f"Trace '{request.trace_id}' not found for case '{case_id}'.",
            },
        )

    if not trace.graph_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "BAD_REQUEST",
                "message": "Trace does not contain transaction graph data.",
            },
        )

    report_id = str(uuid.uuid4())
    job_id = str(uuid.uuid4())
    now_utc = datetime.now(timezone.utc)

    # Async Background Queue Dispatch
    if not _is_sync_request(sync, prefer):
        report_model = ReportModel(
            id=report_id,
            case_id=case.id,
            trace_id=trace.id,
            tenant_id=current_officer.tenant_id,
            district_id=current_officer.district_id,
            police_station_id=current_officer.police_station_id,
            report_type=ReportType.EVIDENCE_DOSSIER.value,
            title=f"Evidence Dossier: {case.fir_number}",
            file_path="",
            file_size_bytes=0,
            content_hash="",
            status="QUEUED",
            job_id=job_id,
            generated_by=request.investigator_name,
            metadata_json={"investigator": request.investigator_name},
        )
        await ReportRepository.create_report(db, report_model)

        queue = get_report_queue()
        await queue.enqueue(
            ReportJobPayload(
                job_id=job_id,
                report_id=report_id,
                case_id=case.id,
                trace_id=trace.id,
                tenant_id=current_officer.tenant_id,
                district_id=current_officer.district_id,
                police_station_id=current_officer.police_station_id,
                officer_id=request.investigator_name or current_officer.officer_id,
                report_type=ReportType.EVIDENCE_DOSSIER.value,
                parameters={
                    "investigator_name": request.investigator_name,
                    "investigator_rank": request.investigator_rank,
                    "police_station": request.police_station,
                    "include_graph_snapshot": request.include_graph_snapshot,
                    "notes": request.notes,
                },
            )
        )
        response.status_code = status.HTTP_202_ACCEPTED
        return ReportJobStatusResponse(
            job_id=job_id,
            report_id=report_id,
            case_id=case.id,
            report_type=ReportType.EVIDENCE_DOSSIER,
            status="QUEUED",
            poll_url=f"/api/v1/reports/jobs/{job_id}",
            created_at=now_utc,
            message="Evidence dossier compilation job enqueued successfully.",
        )

    # Synchronous Execution Path
    graph = InvestigationGraph(**trace.graph_data)
    engine = AttributionEngine()
    attribution_report = engine.evaluate_trace(trace_id=trace.id, graph=graph)

    evidence_items = await EvidenceRepository.get_by_trace_id(db, trace.id, tenant_id=current_officer.tenant_id)
    if not evidence_items:
        evidence_items = EvidenceGenerator.generate_trace_evidence(
            case_id=case.id,
            trace_id=trace.id,
            graph=graph,
            attribution_report=attribution_report,
            config_snapshot=trace.config,
        )
        await EvidenceRepository.save_evidence_items(
            db,
            evidence_items,
            tenant_id=current_officer.tenant_id,
            district_id=current_officer.district_id,
            police_station_id=current_officer.police_station_id,
        )

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
        logger.error(f"Failed to generate Evidence Dossier: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "REPORT_GENERATION_FAILED",
                "message": f"Dossier PDF compilation failed: {e}",
                "case_id": case_id,
            },
        )

    safe_fir = case.fir_number.replace("/", "-").replace(" ", "_")
    file_name = f"Dossier_{safe_fir}_{report_id[:8]}.pdf"
    storage_key = f"reports/{current_officer.tenant_id}/{case_id}/{file_name}"
    storage_service = get_storage_service()
    stored_doc = await storage_service.put_object(
        key=storage_key,
        data=pdf_bytes,
        content_type="application/pdf",
        encrypt=True,
        metadata={"case_id": case_id, "report_id": report_id},
    )

    report_dir = _ensure_report_dir(case_id)
    local_file_path = os.path.join(report_dir, file_name)
    with open(local_file_path, "wb") as f:
        f.write(pdf_bytes)

    report_model = ReportModel(
        id=report_id,
        case_id=case.id,
        trace_id=trace.id,
        tenant_id=current_officer.tenant_id,
        district_id=current_officer.district_id,
        police_station_id=current_officer.police_station_id,
        report_type=ReportType.EVIDENCE_DOSSIER.value,
        title=f"Evidence Dossier: {case.fir_number}",
        file_path=local_file_path,
        storage_path=stored_doc.key,
        s3_key=stored_doc.key,
        storage_backend=stored_doc.storage_backend,
        file_hash=report_hash,
        file_size_bytes=len(pdf_bytes),
        content_hash=report_hash,
        status="COMPLETED",
        job_id=job_id,
        generated_by=request.investigator_name,
        metadata_json=meta,
        completed_at=now_utc,
    )
    await ReportRepository.create_report(db, report_model)

    audit_ev = AuditEvent(
        id=str(uuid.uuid4()),
        case_id=case.id,
        trace_id=trace.id,
        actor_id=request.investigator_name or current_officer.officer_id,
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
            "time": now_utc.isoformat(),
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


@router.post(
    "/cases/{case_id}/reports/bnss94",
    response_model=Union[ReportResponse, ReportJobStatusResponse],
    status_code=status.HTTP_201_CREATED,
)
async def generate_bnss94_draft(
    case_id: str,
    request: BNSS94DraftCreateRequest,
    response: Response,
    sync: Optional[bool] = Query(None, description="Force synchronous (True) or asynchronous (False) execution"),
    prefer: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
    current_officer: OfficerSession = Depends(require_roles([Role.INVESTIGATING_OFFICER, Role.SUPERVISOR, Role.ADMIN])),
):
    """
    Generate a Draft Section 94 BNSS Record-Production Request PDF.
    Supports dual-mode sync (201 Created) or async (202 Accepted with poll URL).
    Enforces tenant boundaries; cross-tenant requests return HTTP 404.
    """
    case = await CaseRepository.get_by_id(db, case_id, tenant_id=current_officer.tenant_id)
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "NOT_FOUND",
                "message": f"Case '{case_id}' not found.",
            },
        )

    trace = await TraceRepository.get_by_id(db, request.trace_id, tenant_id=current_officer.tenant_id)
    if not trace or trace.case_id != case_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "NOT_FOUND",
                "message": f"Trace '{request.trace_id}' not found for case '{case_id}'.",
            },
        )

    attribution_report = None
    if trace.graph_data:
        graph = InvestigationGraph(**trace.graph_data)
        engine = AttributionEngine()
        attribution_report = engine.evaluate_trace(trace_id=trace.id, graph=graph)

        if len(graph.edges) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "NO_TRANSFERS_FOUND",
                    "message": "Cannot generate Section 94 BNSS notice: Trace contains no on-chain transactions or VASP endpoints to requisition.",
                },
            )

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
                },
            )

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
                        },
                    )
            elif not attribution_report or not attribution_report.best_candidate:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "code": "NO_VASP_FOUND",
                        "message": "Cannot generate Section 94 BNSS notice: No candidate VASP identified in the transaction graph.",
                    },
                )

    report_id = str(uuid.uuid4())
    job_id = str(uuid.uuid4())
    now_utc = datetime.now(timezone.utc)

    # Async Background Queue Dispatch
    if not _is_sync_request(sync, prefer):
        report_model = ReportModel(
            id=report_id,
            case_id=case.id,
            trace_id=trace.id,
            tenant_id=current_officer.tenant_id,
            district_id=current_officer.district_id,
            police_station_id=current_officer.police_station_id,
            report_type=ReportType.SECTION_94_BNSS.value,
            title=f"Draft Section 94 BNSS Notice: {case.fir_number}",
            file_path="",
            file_size_bytes=0,
            content_hash="",
            status="QUEUED",
            job_id=job_id,
            generated_by=request.investigator_name,
            metadata_json={"target_vasp": request.target_vasp},
        )
        await ReportRepository.create_report(db, report_model)

        queue = get_report_queue()
        await queue.enqueue(
            ReportJobPayload(
                job_id=job_id,
                report_id=report_id,
                case_id=case.id,
                trace_id=trace.id,
                tenant_id=current_officer.tenant_id,
                district_id=current_officer.district_id,
                police_station_id=current_officer.police_station_id,
                officer_id=request.investigator_name or current_officer.officer_id,
                report_type=ReportType.SECTION_94_BNSS.value,
                parameters={
                    "target_vasp": request.target_vasp,
                    "candidate_address": request.candidate_address,
                    "investigator_name": request.investigator_name,
                    "investigator_rank": request.investigator_rank,
                    "police_station": request.police_station,
                    "court_jurisdiction": request.court_jurisdiction,
                    "compliance_email": request.compliance_email,
                    "urgency_hours": request.urgency_hours,
                    "notes": request.notes,
                },
            )
        )
        response.status_code = status.HTTP_202_ACCEPTED
        return ReportJobStatusResponse(
            job_id=job_id,
            report_id=report_id,
            case_id=case.id,
            report_type=ReportType.SECTION_94_BNSS,
            status="QUEUED",
            poll_url=f"/api/v1/reports/jobs/{job_id}",
            created_at=now_utc,
            message="Section 94 BNSS notice compilation job enqueued successfully.",
        )

    # Synchronous Execution Path
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
            },
        )

    safe_fir = case.fir_number.replace("/", "-").replace(" ", "_")
    file_name = f"Draft_BNSS94_{safe_fir}_{report_id[:8]}.pdf"
    storage_key = f"reports/{current_officer.tenant_id}/{case_id}/{file_name}"
    storage_service = get_storage_service()
    stored_doc = await storage_service.put_object(
        key=storage_key,
        data=pdf_bytes,
        content_type="application/pdf",
        encrypt=True,
        metadata={"case_id": case_id, "report_id": report_id},
    )

    report_dir = _ensure_report_dir(case_id)
    local_file_path = os.path.join(report_dir, file_name)
    with open(local_file_path, "wb") as f:
        f.write(pdf_bytes)

    report_model = ReportModel(
        id=report_id,
        case_id=case.id,
        trace_id=trace.id,
        tenant_id=current_officer.tenant_id,
        district_id=current_officer.district_id,
        police_station_id=current_officer.police_station_id,
        report_type=ReportType.SECTION_94_BNSS.value,
        title=f"Draft Section 94 BNSS Notice: {case.fir_number}",
        file_path=local_file_path,
        storage_path=stored_doc.key,
        s3_key=stored_doc.key,
        storage_backend=stored_doc.storage_backend,
        file_hash=report_hash,
        file_size_bytes=len(pdf_bytes),
        content_hash=report_hash,
        status="COMPLETED",
        job_id=job_id,
        generated_by=request.investigator_name,
        metadata_json=meta,
        completed_at=now_utc,
    )
    await ReportRepository.create_report(db, report_model)

    audit_ev = AuditEvent(
        id=str(uuid.uuid4()),
        case_id=case.id,
        trace_id=trace.id,
        actor_id=request.investigator_name or current_officer.officer_id,
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
            "time": now_utc.isoformat(),
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


@router.post(
    "/cases/{case_id}/reports/bsa63",
    response_model=Union[ReportResponse, ReportJobStatusResponse],
    status_code=status.HTTP_201_CREATED,
)
async def generate_bsa63_certificate(
    case_id: str,
    request: Section63BSACreateRequest,
    response: Response,
    sync: Optional[bool] = Query(None, description="Force synchronous (True) or asynchronous (False) execution"),
    prefer: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
    current_officer: OfficerSession = Depends(require_roles([Role.INVESTIGATING_OFFICER, Role.SUPERVISOR, Role.ADMIN])),
):
    """
    Generate an official Certificate of Electronic Evidence under Section 63(4) BSA, 2023.
    Contains Schedule Part A (Technical Specifications & Hash Anchors) and Part B (Lawful Control Declaration).
    Supports dual-mode sync (201 Created) or async (202 Accepted with poll URL).
    Enforces tenant boundaries; cross-tenant requests return HTTP 404.
    """
    case = await CaseRepository.get_by_id(db, case_id, tenant_id=current_officer.tenant_id)
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "NOT_FOUND",
                "message": f"Case '{case_id}' not found.",
            },
        )

    trace = await TraceRepository.get_by_id(db, request.trace_id, tenant_id=current_officer.tenant_id)
    if not trace or trace.case_id != case_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "NOT_FOUND",
                "message": f"Trace '{request.trace_id}' not found for case '{case_id}'.",
            },
        )

    report_id = str(uuid.uuid4())
    job_id = str(uuid.uuid4())
    now_utc = datetime.now(timezone.utc)

    # Async Background Queue Dispatch
    if not _is_sync_request(sync, prefer):
        report_model = ReportModel(
            id=report_id,
            case_id=case.id,
            trace_id=trace.id,
            tenant_id=current_officer.tenant_id,
            district_id=current_officer.district_id,
            police_station_id=current_officer.police_station_id,
            report_type=ReportType.SECTION_63_BSA.value,
            title=f"Section 63 BSA Evidence Certificate: {case.fir_number}",
            file_path="",
            file_size_bytes=0,
            content_hash="",
            status="QUEUED",
            job_id=job_id,
            generated_by=request.investigator_name,
            metadata_json={"investigator": request.investigator_name},
        )
        await ReportRepository.create_report(db, report_model)

        queue = get_report_queue()
        await queue.enqueue(
            ReportJobPayload(
                job_id=job_id,
                report_id=report_id,
                case_id=case.id,
                trace_id=trace.id,
                tenant_id=current_officer.tenant_id,
                district_id=current_officer.district_id,
                police_station_id=current_officer.police_station_id,
                officer_id=request.investigator_name or current_officer.officer_id,
                report_type=ReportType.SECTION_63_BSA.value,
                parameters={
                    "investigator_name": request.investigator_name,
                    "investigator_rank": request.investigator_rank,
                    "police_station": request.police_station,
                    "technical_examiner": request.technical_examiner,
                    "notes": request.notes,
                },
            )
        )
        response.status_code = status.HTTP_202_ACCEPTED
        return ReportJobStatusResponse(
            job_id=job_id,
            report_id=report_id,
            case_id=case.id,
            report_type=ReportType.SECTION_63_BSA,
            status="QUEUED",
            poll_url=f"/api/v1/reports/jobs/{job_id}",
            created_at=now_utc,
            message="Section 63 BSA certificate compilation job enqueued successfully.",
        )

    # Synchronous Execution Path
    evidence_items = await EvidenceRepository.get_by_trace_id(db, trace.id, tenant_id=current_officer.tenant_id)
    try:
        pdf_bytes, report_hash, meta = Section63BSAGenerator.generate_pdf(
            case=case,
            trace=trace,
            evidence_items=evidence_items,
            investigator_name=request.investigator_name,
            investigator_rank=request.investigator_rank,
            police_station=request.police_station,
            technical_examiner=request.technical_examiner,
            notes=request.notes,
        )
    except Exception as e:
        logger.error(f"Failed to generate Section 63 BSA certificate: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "REPORT_GENERATION_FAILED",
                "message": f"Section 63 BSA certificate compilation failed: {e}",
                "case_id": case_id,
            },
        )

    safe_fir = case.fir_number.replace("/", "-").replace(" ", "_")
    file_name = f"Certificate_BSA63_{safe_fir}_{report_id[:8]}.pdf"
    storage_key = f"reports/{current_officer.tenant_id}/{case_id}/{file_name}"
    storage_service = get_storage_service()
    stored_doc = await storage_service.put_object(
        key=storage_key,
        data=pdf_bytes,
        content_type="application/pdf",
        encrypt=True,
        metadata={"case_id": case_id, "report_id": report_id},
    )

    report_dir = _ensure_report_dir(case_id)
    local_file_path = os.path.join(report_dir, file_name)
    with open(local_file_path, "wb") as f:
        f.write(pdf_bytes)

    report_model = ReportModel(
        id=report_id,
        case_id=case.id,
        trace_id=trace.id,
        tenant_id=current_officer.tenant_id,
        district_id=current_officer.district_id,
        police_station_id=current_officer.police_station_id,
        report_type=ReportType.SECTION_63_BSA.value,
        title=f"Section 63 BSA Evidence Certificate: {case.fir_number}",
        file_path=local_file_path,
        storage_path=stored_doc.key,
        s3_key=stored_doc.key,
        storage_backend=stored_doc.storage_backend,
        file_hash=report_hash,
        file_size_bytes=len(pdf_bytes),
        content_hash=report_hash,
        status="COMPLETED",
        job_id=job_id,
        generated_by=request.investigator_name,
        metadata_json=meta,
        completed_at=now_utc,
    )
    await ReportRepository.create_report(db, report_model)

    audit_ev = AuditEvent(
        id=str(uuid.uuid4()),
        case_id=case.id,
        trace_id=trace.id,
        actor_id=request.investigator_name or current_officer.officer_id,
        event_type=AuditEventType.REPORT_GENERATED,
        action_summary=f"Investigator {request.investigator_name} generated Section 63 BSA Electronic Evidence Certificate (SHA-256: {report_hash[:16]}...).",
        metadata={
            "report_id": report_id,
            "report_type": ReportType.SECTION_63_BSA.value,
            "report_hash": report_hash,
            "file_size": len(pdf_bytes),
        },
        content_hash=compute_content_hash({
            "report_id": report_id,
            "case_id": case.id,
            "report_hash": report_hash,
            "actor": request.investigator_name,
            "time": now_utc.isoformat(),
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

    return ReportResponse(
        id=report_model.id,
        case_id=report_model.case_id,
        trace_id=report_model.trace_id,
        report_type=ReportType.SECTION_63_BSA,
        title=report_model.title,
        file_name=file_name,
        file_size_bytes=report_model.file_size_bytes,
        content_hash=report_model.content_hash,
        generated_by=report_model.generated_by,
        metadata=report_model.metadata_json or {},
        created_at=report_model.created_at,
        download_url=f"/api/v1/reports/{report_model.id}/download",
    )


@router.get("/reports/jobs/{job_id}", response_model=ReportJobStatusResponse)
async def get_report_job_status(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    current_officer: OfficerSession = Depends(get_current_officer),
):
    """
    Poll the execution status of an asynchronous report generation job.
    Enforces tenant boundaries; cross-tenant lookup returns HTTP 404 (IDOR defense).
    """
    report = await ReportRepository.get_by_job_id(db, job_id, tenant_id=current_officer.tenant_id)
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "NOT_FOUND",
                "message": f"Report job '{job_id}' not found.",
            },
        )

    storage_service = get_storage_service()
    presigned = None
    if report.status == "COMPLETED" and report.storage_key:
        try:
            presigned = await storage_service.generate_presigned_url(
                key=report.storage_key,
                expires_in_seconds=900,
                filename=report.title,
                tenant_id=current_officer.tenant_id,
                report_id=str(report.id),
            )
        except Exception:
            pass

    return ReportJobStatusResponse(
        job_id=job_id,
        report_id=str(report.id),
        case_id=str(report.case_id),
        report_type=ReportType(report.report_type),
        status=report.status,
        poll_url=f"/api/v1/reports/jobs/{job_id}",
        created_at=report.created_at,
        completed_at=report.completed_at,
        download_url=f"/api/v1/reports/{report.id}/download" if report.status == "COMPLETED" else None,
        presigned_url=presigned,
        content_hash=report.content_hash if report.status == "COMPLETED" else None,
        file_size_bytes=report.file_size_bytes if report.status == "COMPLETED" else None,
        error_message=report.error_message,
        message=f"Report job status: {report.status}",
    )


@router.post("/reports/{report_id}/presigned-url", response_model=PresignedUrlResponse)
async def create_report_presigned_url(
    report_id: str,
    request: PresignedUrlRequest = PresignedUrlRequest(),
    db: AsyncSession = Depends(get_db),
    current_officer: OfficerSession = Depends(
        require_roles([Role.INVESTIGATING_OFFICER, Role.SUPERVISOR, Role.ADMIN, Role.AUDITOR])
    ),
):
    """
    Issue an authenticated, time-limited pre-signed download URL for a completed legal report.
    Enforces strict tenant isolation: cross-tenant access returns HTTP 404 (IDOR defense).
    """
    report = await ReportRepository.get_by_id(db, report_id, tenant_id=current_officer.tenant_id)
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "NOT_FOUND",
                "message": f"Report '{report_id}' not found.",
            },
        )

    if report.status != "COMPLETED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "REPORT_NOT_READY",
                "message": f"Report '{report_id}' is not yet completed (current status: {report.status}).",
            },
        )

    storage_service = get_storage_service()
    url = await storage_service.generate_presigned_url(
        key=report.storage_key,
        expires_in_seconds=request.expires_in_seconds,
        filename=report.title,
        tenant_id=current_officer.tenant_id,
        report_id=str(report.id),
    )
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=request.expires_in_seconds)

    return PresignedUrlResponse(
        report_id=str(report.id),
        download_url=url,
        expires_in_seconds=request.expires_in_seconds,
        expires_at=expires_at,
    )


@router.get("/cases/{case_id}/reports", response_model=List[ReportResponse])
async def list_case_reports(
    case_id: str,
    report_type: Optional[str] = Query(None, description="Filter by EVIDENCE_DOSSIER, SECTION_94_BNSS, SECTION_63_BSA"),
    db: AsyncSession = Depends(get_db),
    current_officer: OfficerSession = Depends(get_current_officer),
):
    """
    List all generated forensic dossiers and legal drafts for a case.
    Enforces tenant boundaries; cross-tenant lookup returns HTTP 404.
    """
    case = await CaseRepository.get_by_id(db, case_id, tenant_id=current_officer.tenant_id)
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "NOT_FOUND",
                "message": f"Case '{case_id}' not found.",
            },
        )

    reports = await ReportRepository.get_by_case_id(
        db,
        case_id,
        report_type=report_type,
        tenant_id=current_officer.tenant_id,
    )

    return [
        ReportResponse(
            id=str(r.id),
            case_id=str(r.case_id),
            trace_id=str(r.trace_id) if r.trace_id else None,
            report_type=ReportType(r.report_type),
            title=r.title,
            file_name=os.path.basename(r.file_path or f"report_{str(r.id)[:8]}.pdf"),
            file_size_bytes=r.file_size_bytes,
            content_hash=r.content_hash,
            generated_by=r.generated_by,
            metadata=r.metadata_json or {},
            created_at=r.created_at,
            download_url=f"/api/v1/reports/{r.id}/download",
        )
        for r in reports
    ]


@router.get("/reports/{report_id}/download")
async def download_report_pdf(
    report_id: str,
    request: Request,
    token: Optional[str] = Query(None, description="Pre-signed HMAC signature token"),
    expires: Optional[int] = Query(None, description="Token expiration timestamp"),
    tenant: Optional[str] = Query(None, description="Tenant ID from pre-signed URL"),
    authorization: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
):
    """
    Download or stream the generated PDF document with proper MIME headers.
    Supports dual authentication:
      1. Authenticated Officer Session via Bearer JWT.
      2. Time-limited pre-signed URL token with HMAC-SHA256 signature verification.
    Enforces tenant boundaries to prevent cross-tenant report IDOR.
    """
    # 1. Dual-Authentication Resolution
    if token:
        # Pre-Signed Token Authentication Path
        now_ts = int(datetime.now(timezone.utc).timestamp())
        if expires is None or expires < now_ts:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "EXPIRED_TOKEN",
                    "message": "Pre-signed download URL has expired.",
                },
            )

        report = await ReportRepository.get_by_id(db, report_id, tenant_id=tenant)
        if not report:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "code": "NOT_FOUND",
                    "message": f"Report '{report_id}' not found.",
                },
            )

        # Validate HMAC-SHA256 signature across potential canonical keys
        valid_sigs = [
            hmac.new(settings.secret_key_value.encode("utf-8"), f"{report.storage_path or report.file_path}:{expires}:{tenant or ''}".encode("utf-8"), hashlib.sha256).hexdigest(),
            hmac.new(settings.secret_key_value.encode("utf-8"), f"{report.storage_key}:{expires}:{tenant or ''}".encode("utf-8"), hashlib.sha256).hexdigest(),
            hmac.new(settings.secret_key_value.encode("utf-8"), f"{report_id}:{expires}:{tenant or ''}".encode("utf-8"), hashlib.sha256).hexdigest(),
        ]
        if token not in valid_sigs:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "INVALID_TOKEN",
                    "message": "Pre-signed download token signature is invalid or tampered.",
                },
            )
    else:
        # Interactive Officer Session Authentication Path
        current_officer = await get_current_officer(request, authorization=authorization)
        report = await ReportRepository.get_by_id(db, report_id, tenant_id=current_officer.tenant_id)
        if not report:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "code": "NOT_FOUND",
                    "message": f"Report '{report_id}' not found.",
                },
            )

    # 2. Retrieve PDF content from Encrypted Storage Vault or Local Disk
    storage_service = get_storage_service()
    filename = os.path.basename(report.file_path or f"report_{str(report.id)[:8]}.pdf")
    if not filename.endswith(".pdf"):
        filename += ".pdf"

    try:
        pdf_bytes, doc = await storage_service.get_object(report.storage_key)
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "X-Content-Type-Options": "nosniff",
            },
        )
    except Exception:
        # Fallback to local file on disk
        if report.file_path and os.path.exists(report.file_path):
            base_dir = os.path.abspath(settings.REPORTS_DIR)
            abs_file_path = os.path.abspath(report.file_path)
            if not abs_file_path.startswith(base_dir):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={
                        "code": "FORBIDDEN",
                        "message": "Access to specified report path is denied.",
                    },
                )
            return FileResponse(
                path=report.file_path,
                media_type="application/pdf",
                filename=filename,
            )

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "NOT_FOUND",
                "message": "Report document could not be located in storage vault.",
            },
        )
