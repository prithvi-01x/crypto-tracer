from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.app.persistence.models import AuditEventModel
from backend.app.domain.evidence.models import AuditEvent


class AuditRepository:
    """
    Append-only repository for forensic investigator action logs and provenance audit trail.
    """

    @staticmethod
    async def record_event(
        session: AsyncSession,
        event: AuditEvent,
    ) -> AuditEventModel:
        record = AuditEventModel(
            id=event.id,
            case_id=event.case_id,
            trace_id=event.trace_id,
            actor_id=event.actor_id,
            event_type=event.event_type.value if hasattr(event.event_type, "value") else str(event.event_type),
            action_summary=event.action_summary,
            metadata_json=event.metadata,
            content_hash=event.content_hash,
            created_at=event.created_at,
        )
        session.add(record)
        await session.commit()
        await session.refresh(record)
        return record

    @staticmethod
    async def get_by_case_id(
        session: AsyncSession,
        case_id: str,
    ) -> List[AuditEventModel]:
        query = (
            select(AuditEventModel)
            .where(AuditEventModel.case_id == case_id)
            .order_by(AuditEventModel.created_at.desc())
        )
        result = await session.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def get_by_trace_id(
        session: AsyncSession,
        trace_id: str,
    ) -> List[AuditEventModel]:
        query = (
            select(AuditEventModel)
            .where(AuditEventModel.trace_id == trace_id)
            .order_by(AuditEventModel.created_at.desc())
        )
        result = await session.execute(query)
        return list(result.scalars().all())
