from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.persistence.db import get_db
from backend.app.persistence.case_repository import CaseRepository
from backend.app.persistence.trace_repository import TraceRepository
from backend.app.api.v1.schemas.cases import CaseCreate, CaseResponse, CaseListResponse
from backend.app.api.v1.schemas.traces import TraceStatusResponse

from backend.app.adapters.tron_provider import validate_tron_address

router = APIRouter(prefix="/cases", tags=["Cases"])


@router.post("", response_model=CaseResponse, status_code=status.HTTP_201_CREATED)
async def create_case(
    case_in: CaseCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    Register a new crypto-fraud investigation case.
    Persists FIR metadata, reported loss, 1930 acknowledgement, and suspect wallet.
    Validates blockchain network, asset support, and TRON wallet address format.
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
        # Case creation allows suspect wallet (Base58Check starting with T) OR on-chain TxID (64 hex characters)
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

    case = await CaseRepository.create(db, case_in)
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
    skip: int = Query(0, ge=0, description="Offset for pagination"),
    limit: int = Query(50, ge=1, le=100, description="Maximum cases to return"),
    db: AsyncSession = Depends(get_db)
):
    """
    List all recorded cases in reverse chronological order.
    """
    cases, total = await CaseRepository.list(db, skip=skip, limit=limit)
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
            trace_count=len(c.traces) if c.traces else 0,
        )
        for c in cases
    ]
    return CaseListResponse(total=total, cases=response_items)


@router.get("/{case_id}", response_model=CaseResponse)
async def get_case(
    case_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieve full details of a specific investigation case by ID.
    """
    case = await CaseRepository.get_by_id(db, case_id)
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Investigation case '{case_id}' not found."
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


@router.get("/{case_id}/traces", response_model=List[TraceStatusResponse])
async def list_traces_for_case(
    case_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    List all transaction traces executed for a specific case.
    """
    case = await CaseRepository.get_by_id(db, case_id)
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Investigation case '{case_id}' not found."
        )

    traces = await TraceRepository.list_by_case_id(db, case_id)
    results = []
    for t in traces:
        meta = (t.graph_data or {}).get("meta", {})
        pruned_count = getattr(t, "pruned_count", 0) or meta.get("pruned_transfers_count", 0)
        results.append(
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
    return results
