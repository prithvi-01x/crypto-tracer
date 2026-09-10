from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from backend.app.persistence.models import EvidenceItemModel
from backend.app.domain.evidence.models import EvidenceItem


class EvidenceRepository:
    """
    Persistence layer for immutable forensic evidence records and provenance DAG.
    """

    @staticmethod
    async def save_evidence_items(
        session: AsyncSession,
        items: List[EvidenceItem],
    ) -> List[EvidenceItemModel]:
        """
        Persist a batch of evidence items. Uses delete-and-insert per item id to avoid duplicates.
        """
        if not items:
            return []

        item_ids = [item.id for item in items]
        await session.execute(
            delete(EvidenceItemModel).where(EvidenceItemModel.id.in_(item_ids))
        )

        db_records: List[EvidenceItemModel] = []
        for item in items:
            record = EvidenceItemModel(
                id=item.id,
                case_id=item.case_id,
                trace_id=item.trace_id,
                evidence_type=item.evidence_type.value if hasattr(item.evidence_type, "value") else str(item.evidence_type),
                classification=item.classification.value if hasattr(item.classification, "value") else str(item.classification),
                title=item.title,
                description=item.description,
                source=item.source,
                source_reference=item.source_reference,
                payload=item.payload,
                parent_evidence_ids=item.parent_evidence_ids,
                content_hash=item.content_hash,
                engine_version=item.engine_version,
                configuration_snapshot=item.configuration_snapshot,
                collected_at=item.collected_at,
                analysis_timestamp=item.analysis_timestamp,
            )
            session.add(record)
            db_records.append(record)

        await session.commit()
        return db_records

    @staticmethod
    async def get_by_trace_id(
        session: AsyncSession,
        trace_id: str,
        classification: Optional[str] = None,
    ) -> List[EvidenceItemModel]:
        query = select(EvidenceItemModel).where(EvidenceItemModel.trace_id == trace_id)
        if classification:
            query = query.where(EvidenceItemModel.classification == classification.upper())
        query = query.order_by(EvidenceItemModel.created_at.asc())
        result = await session.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def get_by_case_id(
        session: AsyncSession,
        case_id: str,
        classification: Optional[str] = None,
    ) -> List[EvidenceItemModel]:
        query = select(EvidenceItemModel).where(EvidenceItemModel.case_id == case_id)
        if classification:
            query = query.where(EvidenceItemModel.classification == classification.upper())
        query = query.order_by(EvidenceItemModel.created_at.asc())
        result = await session.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def get_by_id(
        session: AsyncSession,
        evidence_id: str,
    ) -> Optional[EvidenceItemModel]:
        query = select(EvidenceItemModel).where(EvidenceItemModel.id == evidence_id)
        result = await session.execute(query)
        return result.scalar_one_or_none()

    get_by_trace = get_by_trace_id
    get_by_case = get_by_case_id
