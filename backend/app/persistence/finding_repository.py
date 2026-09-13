from datetime import datetime, timezone
from typing import List, Optional, Dict, Any, Tuple
from decimal import Decimal
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.config import (
    DEFAULT_TENANT_ID,
    DEFAULT_DISTRICT_ID,
    DEFAULT_POLICE_STATION_ID,
)
from backend.app.persistence.models import FindingRecord
from backend.app.persistence.pagination import apply_keyset_pagination, process_keyset_results
from backend.app.domain.findings.models import ForensicFinding, FindingStatus


class FindingRepository:
    """
    Persistence operations for forensic findings and investigator review states.
    """

    @classmethod
    async def get_by_case(
        cls,
        session: AsyncSession,
        case_id: str,
        tenant_id: Optional[str] = None,
    ) -> List[FindingRecord]:
        stmt = select(FindingRecord).where(FindingRecord.case_id == case_id)
        if tenant_id:
            stmt = stmt.where(FindingRecord.tenant_id == tenant_id)
        stmt = stmt.order_by(FindingRecord.created_at.desc())
        res = await session.execute(stmt)
        return list(res.scalars().all())

    @classmethod
    async def get_by_case_keyset(
        cls,
        session: AsyncSession,
        case_id: str,
        cursor: Optional[str] = None,
        limit: int = 50,
        tenant_id: Optional[str] = None,
    ) -> Tuple[List[FindingRecord], int, Optional[str], bool]:
        query = select(FindingRecord).where(FindingRecord.case_id == case_id)
        count_query = select(func.count()).select_from(FindingRecord).where(FindingRecord.case_id == case_id)

        if tenant_id:
            query = query.where(FindingRecord.tenant_id == tenant_id)
            count_query = count_query.where(FindingRecord.tenant_id == tenant_id)

        total_res = await session.execute(count_query)
        total = total_res.scalar_one()

        query, _ = apply_keyset_pagination(
            query, FindingRecord, cursor=cursor, limit=limit, timestamp_col_name="created_at", descending=True
        )
        res = await session.execute(query)
        raw_records = list(res.scalars().all())

        records, next_cursor, has_more = process_keyset_results(
            raw_records, limit, timestamp_col_name="created_at"
        )
        return records, total, next_cursor, has_more

    @classmethod
    async def get_by_trace(
        cls,
        session: AsyncSession,
        trace_id: str,
        tenant_id: Optional[str] = None,
    ) -> List[FindingRecord]:
        stmt = select(FindingRecord).where(FindingRecord.trace_id == trace_id)
        if tenant_id:
            stmt = stmt.where(FindingRecord.tenant_id == tenant_id)
        stmt = stmt.order_by(FindingRecord.created_at.desc())
        res = await session.execute(stmt)
        return list(res.scalars().all())

    @classmethod
    async def get_by_id(
        cls,
        session: AsyncSession,
        finding_id: str,
        tenant_id: Optional[str] = None,
    ) -> Optional[FindingRecord]:
        stmt = select(FindingRecord).where(FindingRecord.id == finding_id)
        if tenant_id:
            stmt = stmt.where(FindingRecord.tenant_id == tenant_id)
        res = await session.execute(stmt)
        return res.scalar_one_or_none()

    @classmethod
    async def upsert_findings(
        cls,
        session: AsyncSession,
        findings: List[ForensicFinding],
        tenant_id: str = DEFAULT_TENANT_ID,
        district_id: str = DEFAULT_DISTRICT_ID,
        police_station_id: str = DEFAULT_POLICE_STATION_ID,
    ) -> List[FindingRecord]:
        """
        Persist generated findings while strictly preserving any existing investigator review state.
        """
        results: List[FindingRecord] = []
        now = datetime.now(timezone.utc)

        for f in findings:
            existing = await cls.get_by_id(session, f.finding_id, tenant_id=tenant_id)
            ev_refs_json = [ref.model_dump() for ref in f.evidence_refs]

            if existing:
                existing.title = f.title
                existing.description = f.description
                existing.severity = f.severity.value
                existing.confidence = Decimal(str(round(f.confidence, 4))) if f.confidence is not None else None
                existing.related_address = f.related_address
                existing.related_tx_hash = f.related_tx_hash
                existing.related_vasp = f.related_vasp
                existing.evidence_refs = ev_refs_json
                existing.graph_node_id = f.graph_node_id
                existing.graph_edge_id = f.graph_edge_id
                existing.updated_at = now

                f.status = FindingStatus(existing.status)
                f.reviewed_by = existing.reviewed_by
                f.reviewed_at = existing.reviewed_at
                f.review_notes = existing.review_notes
                results.append(existing)
            else:
                record = FindingRecord(
                    id=f.finding_id,
                    case_id=f.case_id,
                    trace_id=f.trace_id,
                    tenant_id=tenant_id,
                    district_id=district_id,
                    police_station_id=police_station_id,
                    finding_type=f.finding_type.value,
                    severity=f.severity.value,
                    title=f.title,
                    description=f.description,
                    source_signal=f.source_signal,
                    confidence=Decimal(str(round(f.confidence, 4))) if f.confidence is not None else None,
                    related_address=f.related_address,
                    related_tx_hash=f.related_tx_hash,
                    related_vasp=f.related_vasp,
                    evidence_refs=ev_refs_json,
                    status=f.status.value,
                    reviewed_by=f.reviewed_by,
                    reviewed_at=f.reviewed_at,
                    review_notes=f.review_notes,
                    graph_node_id=f.graph_node_id,
                    graph_edge_id=f.graph_edge_id,
                    created_at=f.timestamp,
                    updated_at=now,
                )
                session.add(record)
                results.append(record)

        await session.commit()
        return results

    @classmethod
    async def update_review_status(
        cls,
        session: AsyncSession,
        finding_id: str,
        case_id: str,
        status: FindingStatus,
        reviewed_by: str = "investigator",
        review_notes: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> Optional[FindingRecord]:
        """
        Record investigator review status transition (OPEN -> REVIEWED or DISMISSED).
        """
        existing = await cls.get_by_id(session, finding_id, tenant_id=tenant_id)
        if not existing or existing.case_id != case_id:
            return None

        now = datetime.now(timezone.utc)
        existing.status = status.value
        existing.reviewed_by = reviewed_by
        existing.reviewed_at = now
        if review_notes is not None:
            existing.review_notes = review_notes
        existing.updated_at = now

        await session.commit()
        await session.refresh(existing)
        return existing
