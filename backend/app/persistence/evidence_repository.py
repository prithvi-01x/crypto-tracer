import hashlib
from typing import List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from backend.app.config import (
    DEFAULT_TENANT_ID,
    DEFAULT_DISTRICT_ID,
    DEFAULT_POLICE_STATION_ID,
)
from backend.app.persistence.models import EvidenceItemModel
from backend.app.persistence.pagination import apply_keyset_pagination, process_keyset_results
from backend.app.domain.evidence.models import EvidenceItem
from backend.app.domain.evidence.hasher import (
    canonicalize_rfc8785,
    compute_genesis_hash,
    compute_chain_hash,
)
from backend.app.domain.evidence.verifier import ForensicIntegrityVerifier
from backend.app.api.v1.schemas.evidence import ChainVerificationResponse


class EvidenceRepository:
    """
    Persistence layer for immutable forensic evidence records and provenance DAG,
    anchored by a tamper-evident cryptographic hash chain.
    """

    @staticmethod
    async def save_evidence_items(
        session: AsyncSession,
        items: List[EvidenceItem],
        tenant_id: str = DEFAULT_TENANT_ID,
        district_id: str = DEFAULT_DISTRICT_ID,
        police_station_id: str = DEFAULT_POLICE_STATION_ID,
    ) -> List[EvidenceItemModel]:
        """
        Persist a batch of evidence items atomically.
        Assigns monotonic 1-indexed sequence numbers per case and computes the cryptographic hash chain.
        Idempotent: skips already persisted evidence IDs preserving historical chain integrity.
        """
        if not items:
            return []

        item_ids = [item.id for item in items]
        existing_stmt = select(EvidenceItemModel).where(EvidenceItemModel.id.in_(item_ids))
        if tenant_id:
            existing_stmt = existing_stmt.where(EvidenceItemModel.tenant_id == tenant_id)
        existing_records = list((await session.execute(existing_stmt)).scalars().all())
        existing_map = {r.id: r for r in existing_records}

        new_items = [it for it in items if it.id not in existing_map]
        if not new_items:
            return [existing_map[it.id] for it in items if it.id in existing_map]

        case_id = new_items[0].case_id

        # Fetch latest sequence and hash anchor for the case
        stmt = (
            select(EvidenceItemModel.sequence_number, EvidenceItemModel.current_hash)
            .where(EvidenceItemModel.case_id == case_id)
            .order_by(EvidenceItemModel.sequence_number.desc())
            .limit(1)
        )
        res = await session.execute(stmt)
        last_row = res.first()
        if last_row is None or last_row[0] is None or last_row[0] == 0:
            curr_seq = 0
            curr_hash = compute_genesis_hash(case_id)
        else:
            curr_seq = last_row[0]
            curr_hash = last_row[1]

        db_records: List[EvidenceItemModel] = []
        for item in new_items:
            curr_seq += 1
            prev_hash = curr_hash
            canonical_payload = canonicalize_rfc8785(item.payload or {})
            canonical_payload_hash = hashlib.sha256(canonical_payload.encode("utf-8")).hexdigest()
            actor_id = getattr(item, "actor_id", None) or getattr(item, "source", None) or "system"
            timestamp = item.created_at if hasattr(item, "created_at") and item.created_at else item.collected_at

            current_hash = compute_chain_hash(
                prev_hash=prev_hash,
                canonical_payload=canonical_payload,
                timestamp=timestamp,
                actor_id=actor_id,
            )

            record = EvidenceItemModel(
                id=item.id,
                case_id=item.case_id,
                trace_id=item.trace_id,
                tenant_id=tenant_id,
                district_id=district_id,
                police_station_id=police_station_id,
                actor_id=actor_id,
                evidence_type=item.evidence_type.value if hasattr(item.evidence_type, "value") else str(item.evidence_type),
                classification=item.classification.value if hasattr(item.classification, "value") else str(item.classification),
                title=item.title,
                description=item.description,
                source=item.source,
                source_reference=item.source_reference,
                payload=item.payload,
                parent_evidence_ids=item.parent_evidence_ids,
                content_hash=item.content_hash or canonical_payload_hash,
                sequence_number=curr_seq,
                prev_hash=prev_hash,
                current_hash=current_hash,
                canonical_payload_hash=canonical_payload_hash,
                engine_version=item.engine_version,
                configuration_snapshot=item.configuration_snapshot,
                collected_at=item.collected_at,
                analysis_timestamp=item.analysis_timestamp,
                created_at=timestamp,
            )
            session.add(record)
            db_records.append(record)
            curr_hash = current_hash

        await session.commit()
        for r in db_records:
            await session.refresh(r)

        result_map = {**existing_map, **{r.id: r for r in db_records}}
        return [result_map[it.id] for it in items if it.id in result_map]

    @staticmethod
    async def get_by_trace_id(
        session: AsyncSession,
        trace_id: str,
        classification: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> List[EvidenceItemModel]:
        query = select(EvidenceItemModel).where(EvidenceItemModel.trace_id == trace_id)
        if tenant_id:
            query = query.where(EvidenceItemModel.tenant_id == tenant_id)
        if classification:
            query = query.where(EvidenceItemModel.classification == classification.upper())
        query = query.order_by(EvidenceItemModel.sequence_number.asc(), EvidenceItemModel.created_at.asc())
        result = await session.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def get_by_case_id(
        session: AsyncSession,
        case_id: str,
        classification: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> List[EvidenceItemModel]:
        query = select(EvidenceItemModel).where(EvidenceItemModel.case_id == case_id)
        if tenant_id:
            query = query.where(EvidenceItemModel.tenant_id == tenant_id)
        if classification:
            query = query.where(EvidenceItemModel.classification == classification.upper())
        query = query.order_by(EvidenceItemModel.sequence_number.asc(), EvidenceItemModel.created_at.asc())
        result = await session.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def get_by_id(
        session: AsyncSession,
        evidence_id: str,
        tenant_id: Optional[str] = None,
    ) -> Optional[EvidenceItemModel]:
        query = select(EvidenceItemModel).where(EvidenceItemModel.id == evidence_id)
        if tenant_id:
            query = query.where(EvidenceItemModel.tenant_id == tenant_id)
        result = await session.execute(query)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_trace_id_keyset(
        session: AsyncSession,
        trace_id: str,
        cursor: Optional[str] = None,
        limit: int = 50,
        classification: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> Tuple[List[EvidenceItemModel], int, Optional[str], bool]:
        query = select(EvidenceItemModel).where(EvidenceItemModel.trace_id == trace_id)
        count_query = select(func.count()).select_from(EvidenceItemModel).where(EvidenceItemModel.trace_id == trace_id)

        if tenant_id:
            query = query.where(EvidenceItemModel.tenant_id == tenant_id)
            count_query = count_query.where(EvidenceItemModel.tenant_id == tenant_id)
        if classification:
            query = query.where(EvidenceItemModel.classification == classification.upper())
            count_query = count_query.where(EvidenceItemModel.classification == classification.upper())

        total_res = await session.execute(count_query)
        total = total_res.scalar_one()

        query, _ = apply_keyset_pagination(
            query, EvidenceItemModel, cursor=cursor, limit=limit, timestamp_col_name="created_at", descending=False
        )
        res = await session.execute(query)
        raw_items = list(res.scalars().all())

        items, next_cursor, has_more = process_keyset_results(
            raw_items, limit, timestamp_col_name="created_at"
        )
        return items, total, next_cursor, has_more

    @staticmethod
    async def verify_integrity(
        session: AsyncSession,
        case_id: str,
        tenant_id: Optional[str] = None,
    ) -> ChainVerificationResponse:
        query = select(EvidenceItemModel).where(EvidenceItemModel.case_id == case_id)
        if tenant_id:
            query = query.where(EvidenceItemModel.tenant_id == tenant_id)
        query = query.order_by(EvidenceItemModel.sequence_number.asc(), EvidenceItemModel.created_at.asc())
        result = await session.execute(query)
        items = list(result.scalars().all())
        return ForensicIntegrityVerifier.verify_evidence_chain(case_id, items)

    get_by_trace = get_by_trace_id
    get_by_case = get_by_case_id
