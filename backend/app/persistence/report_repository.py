from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.persistence.models import ReportModel


class ReportRepository:
    """Repository for managing generated forensic and legal reports."""

    @staticmethod
    async def create_report(session: AsyncSession, report: ReportModel) -> ReportModel:
        session.add(report)
        await session.commit()
        await session.refresh(report)
        return report

    @staticmethod
    async def get_by_id(session: AsyncSession, report_id: str) -> Optional[ReportModel]:
        stmt = select(ReportModel).where(ReportModel.id == report_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_case_id(
        session: AsyncSession,
        case_id: str,
        report_type: Optional[str] = None,
    ) -> List[ReportModel]:
        stmt = select(ReportModel).where(ReportModel.case_id == case_id)
        if report_type:
            stmt = stmt.where(ReportModel.report_type == report_type)
        stmt = stmt.order_by(ReportModel.created_at.desc())
        result = await session.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_by_trace_id(
        session: AsyncSession,
        trace_id: str,
    ) -> List[ReportModel]:
        stmt = select(ReportModel).where(ReportModel.trace_id == trace_id).order_by(ReportModel.created_at.desc())
        result = await session.execute(stmt)
        return list(result.scalars().all())
