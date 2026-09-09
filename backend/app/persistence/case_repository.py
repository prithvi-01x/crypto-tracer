from typing import List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from backend.app.persistence.models import Case
from backend.app.api.v1.schemas.cases import CaseCreate


class CaseRepository:
    @staticmethod
    async def create(session: AsyncSession, case_data: CaseCreate) -> Case:
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
        )
        session.add(new_case)
        await session.commit()
        await session.refresh(new_case)
        return new_case

    @staticmethod
    async def get_by_id(session: AsyncSession, case_id: str) -> Optional[Case]:
        query = select(Case).where(Case.id == case_id)
        result = await session.execute(query)
        return result.scalars().first()

    @staticmethod
    async def list(
        session: AsyncSession,
        skip: int = 0,
        limit: int = 50
    ) -> Tuple[List[Case], int]:
        count_query = select(func.count()).select_from(Case)
        total_result = await session.execute(count_query)
        total = total_result.scalar_one()

        query = select(Case).order_by(desc(Case.created_at)).offset(skip).limit(limit)
        result = await session.execute(query)
        cases = list(result.scalars().all())
        return cases, total
