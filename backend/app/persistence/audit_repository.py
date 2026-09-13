import hashlib
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.app.config import (
    DEFAULT_TENANT_ID,
    DEFAULT_DISTRICT_ID,
    DEFAULT_POLICE_STATION_ID,
)
from backend.app.persistence.models import AuditEventModel
from backend.app.domain.evidence.models import AuditEvent
from backend.app.domain.evidence.hasher import (
    canonicalize_rfc8785,
    compute_genesis_hash,
    compute_chain_hash,
)
from backend.app.domain.evidence.verifier import ForensicIntegrityVerifier
from backend.app.api.v1.schemas.evidence import ChainVerificationResponse


class AuditRepository:
    """
    Append-only repository for forensic investigator action logs and provenance audit trail,
    anchored by a tamper-evident cryptographic hash chain.
    """

    @staticmethod
    async def record_event(
        session: AsyncSession,
        event: AuditEvent,
        tenant_id: str = DEFAULT_TENANT_ID,
        district_id: str = DEFAULT_DISTRICT_ID,
        police_station_id: str = DEFAULT_POLICE_STATION_ID,
    ) -> AuditEventModel:
        # 1. Fetch latest record for sequence & prev_hash
        stmt = (
            select(AuditEventModel.sequence_number, AuditEventModel.current_hash)
            .where(AuditEventModel.case_id == event.case_id)
            .order_by(AuditEventModel.sequence_number.desc())
            .limit(1)
        )
        res = await session.execute(stmt)
        last_row = res.first()
        if last_row is None or last_row[0] is None or last_row[0] == 0:
            seq = 1
            prev_hash = compute_genesis_hash(event.case_id)
        else:
            seq = last_row[0] + 1
            prev_hash = last_row[1]

        # 2. Canonical payload & hash
        event_type_str = event.event_type.value if hasattr(event.event_type, "value") else str(event.event_type)
        payload_dict = {
            "action_summary": event.action_summary,
            "event_type": event_type_str,
            "metadata": event.metadata or {},
            "trace_id": event.trace_id,
        }
        canonical_payload = canonicalize_rfc8785(payload_dict)
        canonical_payload_hash = hashlib.sha256(canonical_payload.encode("utf-8")).hexdigest()

        # 3. Cryptographic hash chain computation
        current_hash = compute_chain_hash(
            prev_hash=prev_hash,
            canonical_payload=canonical_payload,
            timestamp=event.created_at,
            actor_id=event.actor_id,
        )

        record = AuditEventModel(
            id=event.id,
            case_id=event.case_id,
            trace_id=event.trace_id,
            tenant_id=tenant_id,
            district_id=district_id,
            police_station_id=police_station_id,
            actor_id=event.actor_id,
            event_type=event_type_str,
            action_summary=event.action_summary,
            metadata_json=event.metadata,
            content_hash=event.content_hash or canonical_payload_hash,
            sequence_number=seq,
            prev_hash=prev_hash,
            current_hash=current_hash,
            canonical_payload_hash=canonical_payload_hash,
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
        tenant_id: Optional[str] = None,
    ) -> List[AuditEventModel]:
        query = (
            select(AuditEventModel)
            .where(AuditEventModel.case_id == case_id)
        )
        if tenant_id:
            query = query.where(AuditEventModel.tenant_id == tenant_id)
        query = query.order_by(AuditEventModel.sequence_number.asc(), AuditEventModel.created_at.asc())
        result = await session.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def get_by_trace_id(
        session: AsyncSession,
        trace_id: str,
        tenant_id: Optional[str] = None,
    ) -> List[AuditEventModel]:
        query = (
            select(AuditEventModel)
            .where(AuditEventModel.trace_id == trace_id)
        )
        if tenant_id:
            query = query.where(AuditEventModel.tenant_id == tenant_id)
        query = query.order_by(AuditEventModel.sequence_number.asc(), AuditEventModel.created_at.asc())
        result = await session.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def verify_integrity(
        session: AsyncSession,
        case_id: str,
        tenant_id: Optional[str] = None,
    ) -> ChainVerificationResponse:
        query = (
            select(AuditEventModel)
            .where(AuditEventModel.case_id == case_id)
        )
        if tenant_id:
            query = query.where(AuditEventModel.tenant_id == tenant_id)
        query = query.order_by(AuditEventModel.sequence_number.asc(), AuditEventModel.created_at.asc())
        result = await session.execute(query)
        events = list(result.scalars().all())
        return ForensicIntegrityVerifier.verify_audit_chain(case_id, events)
