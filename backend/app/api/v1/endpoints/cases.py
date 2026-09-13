from typing import List, Optional, Any, Union
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.persistence.db import get_db
from backend.app.persistence.case_repository import CaseRepository
from backend.app.persistence.trace_repository import TraceRepository
from backend.app.api.v1.schemas.cases import CaseCreate, CaseUpdate, CaseNoteCreate, CaseResponse, CaseListResponse
from backend.app.api.v1.schemas.traces import TraceStatusResponse, TraceListResponse
from backend.app.core.auth import Role, OfficerSession
from backend.app.api.deps import get_current_officer, require_roles
from backend.app.adapters.tron_provider import validate_tron_address

router = APIRouter(prefix="/cases", tags=["Cases"])


@router.post("", response_model=CaseResponse, status_code=status.HTTP_201_CREATED)
async def create_case(
    case_in: CaseCreate,
    db: AsyncSession = Depends(get_db),
    current_officer: OfficerSession = Depends(require_roles([Role.INVESTIGATING_OFFICER, Role.SUPERVISOR, Role.ADMIN])),
):
    """
    Register a new crypto-fraud investigation case.
    Persists FIR metadata, reported loss, 1930 acknowledgement, and suspect wallet.
    Validates blockchain network, asset support, and TRON wallet address format.
    Scoped to the current officer's tenant hierarchy.
    """
    # 1. Chain validation
    if case_in.chain.upper() != "TRON":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "UNSUPPORTED_CHAIN",
                "message": f"Blockchain network '{case_in.chain}' is not supported. Supported blockchain: TRON.",
                "supported_chains": ["TRON"],
            }
        )

    # 2. Asset validation
    if case_in.asset.upper() not in ("USDT", "TRC20:USDT", "TRC-20:USDT"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "UNSUPPORTED_ASSET",
                "message": f"Asset '{case_in.asset}' is not supported. Supported asset: TRC20:USDT.",
                "supported_assets": ["TRC20:USDT"],
            }
        )

    # 3. Suspect wallet address / TxID format validation (if provided)
    if case_in.suspect_wallet and case_in.suspect_wallet.strip():
        clean_addr = case_in.suspect_wallet.strip()
        is_valid_tron_wallet = clean_addr.startswith("T") and (32 <= len(clean_addr) <= 40)
        is_valid_txid = (len(clean_addr) == 64) and all(c in "0123456789abcdefABCDEF" for c in clean_addr)
        if not (is_valid_tron_wallet or is_valid_txid):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "INVALID_ADDRESS",
                    "message": f"Invalid TRON address / TxID format: '{clean_addr}'. Expected TRON address starting with 'T' or 64-character transaction hash.",
                }
            )

    case = await CaseRepository.create(
        session=db,
        case_data=case_in,
        tenant_id=current_officer.tenant_id,
        district_id=current_officer.district_id,
        police_station_id=current_officer.police_station_id,
    )
    return CaseResponse(
        id=case.id,
        fir_number=case.fir_number,
        victim_reference=case.victim_reference,
        loss_amount_inr=case.loss_amount_inr,
        ack_number=case.ack_number,
        suspect_wallet=case.suspect_wallet,
        chain=case.chain,
        asset=case.asset,
        notes=case.notes,
        status=case.status,
        created_at=case.created_at,
        updated_at=case.updated_at,
        trace_count=len(case.traces) if hasattr(case, "traces") and case.traces else 0,
    )


@router.get("", response_model=CaseListResponse)
async def list_cases(
    cursor: Optional[str] = Query(None, description="Base64 keyset pagination cursor"),
    skip: int = Query(0, ge=0, description="Offset for pagination fallback"),
    limit: int = Query(50, ge=1, le=100, description="Maximum cases to return"),
    include_deleted: bool = Query(False, description="Include soft-deleted cases"),
    db: AsyncSession = Depends(get_db),
    current_officer: OfficerSession = Depends(get_current_officer),
):
    """
    List all recorded cases for the requesting officer's tenant in reverse chronological order.
    Supports keyset pagination (cursor) and offset fallback (skip).
    """
    if cursor is not None or skip == 0:
        try:
            cases, total, next_cursor, has_more = await CaseRepository.list_keyset(
                session=db,
                cursor=cursor,
                limit=limit,
                tenant_id=current_officer.tenant_id,
                include_deleted=include_deleted,
            )
        except ValueError as ex:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "INVALID_CURSOR", "message": str(ex)},
            )
    else:
        cases, total = await CaseRepository.list(
            session=db,
            skip=skip,
            limit=limit,
            tenant_id=current_officer.tenant_id,
            include_deleted=include_deleted,
        )
        next_cursor = None
        has_more = (skip + limit) < total

    response_items = [
        CaseResponse(
            id=c.id,
            fir_number=c.fir_number,
            victim_reference=c.victim_reference,
            loss_amount_inr=c.loss_amount_inr,
            ack_number=c.ack_number,
            suspect_wallet=c.suspect_wallet,
            chain=c.chain,
            asset=c.asset,
            notes=c.notes,
            status=c.status,
            created_at=c.created_at,
            updated_at=c.updated_at,
            trace_count=len(c.traces) if hasattr(c, "traces") and c.traces else 0,
        )
        for c in cases
    ]
    return CaseListResponse(
        total=total,
        cases=response_items,
        items=response_items,
        next_cursor=next_cursor,
        has_more=has_more,
    )


@router.get("/{case_id}", response_model=CaseResponse)
async def get_case(
    case_id: str,
    include_deleted: bool = Query(False, description="Include soft-deleted case if true"),
    db: AsyncSession = Depends(get_db),
    current_officer: OfficerSession = Depends(get_current_officer),
):
    """
    Retrieve full details of a specific investigation case by ID.
    Enforces tenant boundaries; cross-tenant lookup returns HTTP 404.
    Soft-deleted cases return HTTP 404 unless include_deleted=True.
    """
    case = await CaseRepository.get_by_id(
        db, case_id, tenant_id=current_officer.tenant_id, include_deleted=include_deleted
    )
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "NOT_FOUND",
                "message": f"Investigation case '{case_id}' not found.",
            }
        )
    return CaseResponse(
        id=case.id,
        fir_number=case.fir_number,
        victim_reference=case.victim_reference,
        loss_amount_inr=case.loss_amount_inr,
        ack_number=case.ack_number,
        suspect_wallet=case.suspect_wallet,
        chain=case.chain,
        asset=case.asset,
        notes=case.notes,
        status=case.status,
        created_at=case.created_at,
        updated_at=case.updated_at,
        trace_count=len(case.traces) if hasattr(case, "traces") and case.traces else 0,
    )


@router.patch("/{case_id}", response_model=CaseResponse)
async def update_case(
    case_id: str,
    case_update: CaseUpdate,
    db: AsyncSession = Depends(get_db),
    current_officer: OfficerSession = Depends(require_roles([Role.INVESTIGATING_OFFICER, Role.SUPERVISOR, Role.ADMIN])),
):
    """
    Update investigation case details (e.g. status or notes).
    Enforces tenant boundaries; cross-tenant modification returns HTTP 404.
    """
    case = await CaseRepository.update(db, case_id, case_update, tenant_id=current_officer.tenant_id)
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "NOT_FOUND",
                "message": f"Investigation case '{case_id}' not found.",
            }
        )
    return CaseResponse(
        id=case.id,
        fir_number=case.fir_number,
        victim_reference=case.victim_reference,
        loss_amount_inr=case.loss_amount_inr,
        ack_number=case.ack_number,
        suspect_wallet=case.suspect_wallet,
        chain=case.chain,
        asset=case.asset,
        notes=case.notes,
        status=case.status,
        created_at=case.created_at,
        updated_at=case.updated_at,
        trace_count=len(case.traces) if hasattr(case, "traces") and case.traces else 0,
    )


@router.post("/{case_id}/notes", response_model=CaseResponse)
async def add_case_note(
    case_id: str,
    note_in: CaseNoteCreate,
    db: AsyncSession = Depends(get_db),
    current_officer: OfficerSession = Depends(require_roles([Role.INVESTIGATING_OFFICER, Role.SUPERVISOR, Role.ADMIN])),
):
    """
    Append an investigator note with timestamp to the case record.
    Enforces tenant boundaries; cross-tenant operation returns HTTP 404.
    """
    author = note_in.author or current_officer.name or "Investigating Officer"
    case = await CaseRepository.add_note(db, case_id, note_in.note, author=author, tenant_id=current_officer.tenant_id)
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "NOT_FOUND",
                "message": f"Investigation case '{case_id}' not found.",
            }
        )
    return CaseResponse(
        id=case.id,
        fir_number=case.fir_number,
        victim_reference=case.victim_reference,
        loss_amount_inr=case.loss_amount_inr,
        ack_number=case.ack_number,
        suspect_wallet=case.suspect_wallet,
        chain=case.chain,
        asset=case.asset,
        notes=case.notes,
        status=case.status,
        created_at=case.created_at,
        updated_at=case.updated_at,
        trace_count=len(case.traces) if hasattr(case, "traces") and case.traces else 0,
    )


def _format_trace(t) -> TraceStatusResponse:
    meta = (t.graph_data or {}).get("meta", {})
    pruned_count = getattr(t, "pruned_count", 0) or meta.get("pruned_transfers_count", 0)
    return TraceStatusResponse(
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


@router.get("/{case_id}/traces", response_model=Any)
async def list_traces_for_case(
    case_id: str,
    cursor: Optional[str] = Query(None, description="Base64 keyset pagination cursor"),
    limit: int = Query(50, ge=1, le=100, description="Maximum traces to return"),
    db: AsyncSession = Depends(get_db),
    current_officer: OfficerSession = Depends(get_current_officer),
):
    """
    List all transaction traces executed for a specific case.
    Returns raw list when cursor is not supplied (backward compatibility).
    Returns TraceListResponse when cursor is supplied.
    """
    case = await CaseRepository.get_by_id(db, case_id, tenant_id=current_officer.tenant_id)
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "NOT_FOUND",
                "message": f"Investigation case '{case_id}' not found.",
            }
        )

    if cursor is not None:
        try:
            traces, total, next_cursor, has_more = await TraceRepository.list_by_case_id_keyset(
                db, case_id, cursor=cursor, limit=limit, tenant_id=current_officer.tenant_id
            )
        except ValueError as ex:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "INVALID_CURSOR", "message": str(ex)},
            )
        items = [_format_trace(t) for t in traces]
        return TraceListResponse(items=items, total=total, next_cursor=next_cursor, has_more=has_more)
    else:
        traces = await TraceRepository.list_by_case_id(db, case_id, tenant_id=current_officer.tenant_id)
        return [_format_trace(t) for t in traces]


@router.delete("/{case_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_case(
    case_id: str,
    db: AsyncSession = Depends(get_db),
    current_officer: OfficerSession = Depends(require_roles([Role.INVESTIGATING_OFFICER, Role.SUPERVISOR, Role.ADMIN])),
):
    """
    Soft-delete an investigation case. Retains evidence items, audit events, and trace records in the database.
    Enforces tenant boundaries; cross-tenant deletion returns HTTP 404.
    """
    deleted = await CaseRepository.delete(db, case_id, tenant_id=current_officer.tenant_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "NOT_FOUND",
                "message": f"Investigation case '{case_id}' not found.",
            }
        )
