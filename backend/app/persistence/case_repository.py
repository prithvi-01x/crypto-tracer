from datetime import datetime, timezone
from typing import List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc

from backend.app.config import (
    DEFAULT_TENANT_ID,
    DEFAULT_DISTRICT_ID,
    DEFAULT_POLICE_STATION_ID,
)
from backend.app.persistence.models import Case
from backend.app.persistence.pagination import apply_keyset_pagination, process_keyset_results
from backend.app.api.v1.schemas.cases import CaseCreate, CaseUpdate


class CaseRepository:
    @staticmethod
    async def create(
        session: AsyncSession,
        case_data: CaseCreate,
        tenant_id: str = DEFAULT_TENANT_ID,
        district_id: str = DEFAULT_DISTRICT_ID,
        police_station_id: str = DEFAULT_POLICE_STATION_ID,
    ) -> Case:
        new_case = Case(
            fir_number=case_data.fir_number.strip(),
            victim_reference=case_data.victim_reference.strip() if case_data.victim_reference else None,
            loss_amount_inr=case_data.loss_amount_inr,
            ack_number=case_data.ack_number.strip() if case_data.ack_number else None,
            suspect_wallet=case_data.suspect_wallet.strip() if case_data.suspect_wallet else None,
            chain=case_data.chain,
            asset=case_data.asset,
            notes=case_data.notes.strip() if case_data.notes else None,
            status="OPEN",
            tenant_id=tenant_id,
            district_id=district_id,
            police_station_id=police_station_id,
        )
        session.add(new_case)
        await session.commit()
        await session.refresh(new_case)
        return new_case

    @staticmethod
    async def get_by_id(
        session: AsyncSession,
        case_id: str,
        tenant_id: Optional[str] = None,
        include_deleted: bool = False,
    ) -> Optional[Case]:
        query = select(Case).where(Case.id == case_id)
        if not include_deleted:
            query = query.where(Case.is_deleted == False)
        if tenant_id:
            query = query.where(Case.tenant_id == tenant_id)
        result = await session.execute(query)
        return result.scalars().first()

    @staticmethod
    async def list(
        session: AsyncSession,
        skip: int = 0,
        limit: int = 50,
        tenant_id: Optional[str] = None,
        district_id: Optional[str] = None,
        police_station_id: Optional[str] = None,
        include_deleted: bool = False,
    ) -> Tuple[List[Case], int]:
        count_query = select(func.count()).select_from(Case)
        query = select(Case).order_by(desc(Case.created_at)).offset(skip).limit(limit)

        if not include_deleted:
            count_query = count_query.where(Case.is_deleted == False)
            query = query.where(Case.is_deleted == False)

        if tenant_id:
            count_query = count_query.where(Case.tenant_id == tenant_id)
            query = query.where(Case.tenant_id == tenant_id)
        if district_id:
            count_query = count_query.where(Case.district_id == district_id)
            query = query.where(Case.district_id == district_id)
        if police_station_id:
            count_query = count_query.where(Case.police_station_id == police_station_id)
            query = query.where(Case.police_station_id == police_station_id)

        total_result = await session.execute(count_query)
        total = total_result.scalar_one()

        result = await session.execute(query)
        cases = list(result.scalars().all())
        return cases, total

    @staticmethod
    async def list_keyset(
        session: AsyncSession,
        cursor: Optional[str] = None,
        limit: int = 50,
        tenant_id: Optional[str] = None,
        district_id: Optional[str] = None,
        police_station_id: Optional[str] = None,
        include_deleted: bool = False,
    ) -> Tuple[List[Case], int, Optional[str], bool]:
        query = select(Case)
        count_query = select(func.count()).select_from(Case)

        if not include_deleted:
            query = query.where(Case.is_deleted == False)
            count_query = count_query.where(Case.is_deleted == False)

        if tenant_id:
            query = query.where(Case.tenant_id == tenant_id)
            count_query = count_query.where(Case.tenant_id == tenant_id)
        if district_id:
            query = query.where(Case.district_id == district_id)
            count_query = count_query.where(Case.district_id == district_id)
        if police_station_id:
            query = query.where(Case.police_station_id == police_station_id)
            count_query = count_query.where(Case.police_station_id == police_station_id)

        total_res = await session.execute(count_query)
        total = total_res.scalar_one()

        query, _ = apply_keyset_pagination(query, Case, cursor=cursor, limit=limit, descending=True)
        res = await session.execute(query)
        raw_cases = list(res.scalars().all())

        cases, next_cursor, has_more = process_keyset_results(raw_cases, limit)
        return cases, total, next_cursor, has_more

    @staticmethod
    async def update(
        session: AsyncSession,
        case_id: str,
        case_update: CaseUpdate,
        tenant_id: Optional[str] = None,
        include_deleted: bool = False,
    ) -> Optional[Case]:
        case = await CaseRepository.get_by_id(session, case_id, tenant_id=tenant_id, include_deleted=include_deleted)
        if not case:
            return None
        if case_update.notes is not None:
            case.notes = case_update.notes.strip() if case_update.notes else None
        if case_update.status is not None:
            case.status = case_update.status.strip()
        case.updated_at = datetime.now(timezone.utc)
        await session.commit()
        await session.refresh(case)
        return case

    @staticmethod
    async def add_note(
        session: AsyncSession,
        case_id: str,
        note_text: str,
        author: Optional[str] = "Investigating Officer",
        tenant_id: Optional[str] = None,
        include_deleted: bool = False,
    ) -> Optional[Case]:
        case = await CaseRepository.get_by_id(session, case_id, tenant_id=tenant_id, include_deleted=include_deleted)
        if not case:
            return None
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        formatted_entry = f"[{now_str} | {author or 'Investigating Officer'}]\n{note_text.strip()}"
        if case.notes and case.notes.strip():
            case.notes = f"{case.notes.strip()}\n\n{formatted_entry}"
        else:
            case.notes = formatted_entry
        case.updated_at = datetime.now(timezone.utc)
        await session.commit()
        await session.refresh(case)
        return case

    @staticmethod
    async def delete(
        session: AsyncSession,
        case_id: str,
        tenant_id: Optional[str] = None,
    ) -> bool:
        """
        Soft-delete an investigation case.
        Sets is_deleted = True and deleted_at = utc_now().
        Retains evidence_items, audit_events, traces, and reports in the database.
        """
        case = await CaseRepository.get_by_id(session, case_id, tenant_id=tenant_id, include_deleted=False)
        if not case:
            return False
        case.is_deleted = True
        case.deleted_at = datetime.now(timezone.utc)
        await session.commit()
        return True
