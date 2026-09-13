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
    async def get_by_id(
        session: AsyncSession,
        report_id: str,
        tenant_id: Optional[str] = None,
    ) -> Optional[ReportModel]:
        stmt = select(ReportModel).where(ReportModel.id == report_id)
        if tenant_id:
            stmt = stmt.where(ReportModel.tenant_id == tenant_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_case_id(
        session: AsyncSession,
        case_id: str,
        report_type: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> List[ReportModel]:
        stmt = select(ReportModel).where(ReportModel.case_id == case_id)
        if tenant_id:
            stmt = stmt.where(ReportModel.tenant_id == tenant_id)
        if report_type:
            stmt = stmt.where(ReportModel.report_type == report_type)
        stmt = stmt.order_by(ReportModel.created_at.desc())
        result = await session.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_by_trace_id(
        session: AsyncSession,
        trace_id: str,
        tenant_id: Optional[str] = None,
    ) -> List[ReportModel]:
        stmt = select(ReportModel).where(ReportModel.trace_id == trace_id)
        if tenant_id:
            stmt = stmt.where(ReportModel.tenant_id == tenant_id)
        stmt = stmt.order_by(ReportModel.created_at.desc())
        result = await session.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_by_job_id(
        session: AsyncSession,
        job_id: str,
        tenant_id: Optional[str] = None,
    ) -> Optional[ReportModel]:
        stmt = select(ReportModel).where(ReportModel.job_id == job_id)
        if tenant_id:
            stmt = stmt.where(ReportModel.tenant_id == tenant_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

