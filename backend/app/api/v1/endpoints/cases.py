from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.persistence.db import get_db
from backend.app.persistence.case_repository import CaseRepository
from backend.app.api.v1.schemas.cases import CaseCreate, CaseResponse, CaseListResponse

router = APIRouter(prefix="/cases", tags=["Cases"])


@router.post("", response_model=CaseResponse, status_code=status.HTTP_201_CREATED)
async def create_case(
    case_in: CaseCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    Register a new crypto-fraud investigation case.
    Persists FIR metadata, reported loss, 1930 acknowledgement, and suspect wallet.
    """
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
