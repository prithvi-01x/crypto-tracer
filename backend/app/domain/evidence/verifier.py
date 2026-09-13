import hashlib
from datetime import datetime, timezone
from typing import List, Optional

from backend.app.persistence.models import AuditEventModel, EvidenceItemModel
from backend.app.domain.evidence.hasher import (
    canonicalize_rfc8785,
    compute_genesis_hash,
    compute_chain_hash,
)
from backend.app.api.v1.schemas.evidence import (
    ChainVerificationResponse,
    ChainVerificationStatus,
    ChainVerificationMismatch,
)


def extract_audit_payload(event: AuditEventModel) -> dict:
    event_type_str = event.event_type.value if hasattr(event.event_type, "value") else str(event.event_type)
    return {
        "action_summary": event.action_summary,
        "event_type": event_type_str,
        "metadata": event.metadata_json or {},
        "trace_id": event.trace_id,
    }


def extract_evidence_payload(item: EvidenceItemModel) -> dict:
    return item.payload or {}


class ForensicIntegrityVerifier:
    """Forensic verification engine for tamper-evident cryptographic hash chains."""

    @classmethod
    def verify_audit_chain(cls, case_id: str, events: List[AuditEventModel]) -> ChainVerificationResponse:
        now = datetime.now(timezone.utc)
        genesis = compute_genesis_hash(case_id)
        if not events:
            return ChainVerificationResponse(
                status=ChainVerificationStatus.EMPTY,
                case_id=case_id,
                chain_type="audit",
                total_records=0,
                corrupted_sequence=None,
                corrupted_record_id=None,
                genesis_hash=genesis,
                head_hash=None,
                details=None,
                verified_at=now,
            )

        expected_prev = genesis
        expected_seq = 1

        for ev in events:
            # 1. Sequence continuity check (detects deletions or out-of-order records)
            if ev.sequence_number != expected_seq:
                return ChainVerificationResponse(
                    status=ChainVerificationStatus.TAMPERED,
                    case_id=case_id,
                    chain_type="audit",
                    total_records=len(events),
                    corrupted_sequence=ev.sequence_number,
                    corrupted_record_id=str(ev.id),
                    genesis_hash=genesis,
                    head_hash=None,
                    details=ChainVerificationMismatch(
                        failure_reason="SEQUENCE_DISCONTINUITY",
                        expected_sequence=expected_seq,
                        actual_sequence=ev.sequence_number,
                        expected_hash=None,
                        actual_hash=None,
                        message=f"Sequence gap detected: expected sequence {expected_seq}, found {ev.sequence_number}. Records may have been deleted or inserted out of order.",
                    ),
                    verified_at=now,
                )

            # 2. Chain linkage check (detects broken links and genesis tampering)
            if ev.prev_hash != expected_prev:
                reason = "GENESIS_HASH_MISMATCH" if expected_seq == 1 else "CHAIN_LINK_BROKEN"
                return ChainVerificationResponse(
                    status=ChainVerificationStatus.TAMPERED,
                    case_id=case_id,
                    chain_type="audit",
                    total_records=len(events),
                    corrupted_sequence=ev.sequence_number,
                    corrupted_record_id=str(ev.id),
                    genesis_hash=genesis,
                    head_hash=None,
                    details=ChainVerificationMismatch(
                        failure_reason=reason,
                        expected_hash=expected_prev,
                        actual_hash=ev.prev_hash,
                        expected_sequence=expected_seq,
                        actual_sequence=ev.sequence_number,
                        message=f"Cryptographic linkage broken at sequence {ev.sequence_number}. Predecessor hash mismatch.",
                    ),
                    verified_at=now,
                )

            # 3. Payload integrity check (detects single-byte payload tampering)
            canonical_payload = canonicalize_rfc8785(extract_audit_payload(ev))
            computed_payload_hash = hashlib.sha256(canonical_payload.encode("utf-8")).hexdigest()
            if ev.canonical_payload_hash and computed_payload_hash != ev.canonical_payload_hash:
                return ChainVerificationResponse(
                    status=ChainVerificationStatus.TAMPERED,
                    case_id=case_id,
                    chain_type="audit",
                    total_records=len(events),
                    corrupted_sequence=ev.sequence_number,
                    corrupted_record_id=str(ev.id),
                    genesis_hash=genesis,
                    head_hash=None,
                    details=ChainVerificationMismatch(
                        failure_reason="PAYLOAD_TAMPERED",
                        expected_hash=computed_payload_hash,
                        actual_hash=ev.canonical_payload_hash,
                        expected_sequence=expected_seq,
                        actual_sequence=ev.sequence_number,
                        message=f"Audit event payload altered at sequence {ev.sequence_number}.",
                    ),
                    verified_at=now,
                )

            # 4. Current hash recalculation check (detects header, timestamp, or actor tampering)
            computed_current = compute_chain_hash(
                prev_hash=ev.prev_hash,
                canonical_payload=canonical_payload,
                timestamp=ev.created_at,
                actor_id=ev.actor_id,
            )
            if computed_current != ev.current_hash:
                return ChainVerificationResponse(
                    status=ChainVerificationStatus.TAMPERED,
                    case_id=case_id,
                    chain_type="audit",
                    total_records=len(events),
                    corrupted_sequence=ev.sequence_number,
                    corrupted_record_id=str(ev.id),
                    genesis_hash=genesis,
                    head_hash=None,
                    details=ChainVerificationMismatch(
                        failure_reason="HASH_MISMATCH",
                        expected_hash=computed_current,
                        actual_hash=ev.current_hash,
                        expected_sequence=expected_seq,
                        actual_sequence=ev.sequence_number,
                        message=f"Current hash mismatch at sequence {ev.sequence_number}. Content, timestamp, or actor was modified.",
                    ),
                    verified_at=now,
                )

            expected_prev = ev.current_hash
            expected_seq += 1

        return ChainVerificationResponse(
            status=ChainVerificationStatus.VALID,
            case_id=case_id,
            chain_type="audit",
            total_records=len(events),
            corrupted_sequence=None,
            corrupted_record_id=None,
            genesis_hash=genesis,
            head_hash=events[-1].current_hash,
            details=None,
            verified_at=now,
        )

    @classmethod
    def verify_evidence_chain(cls, case_id: str, items: List[EvidenceItemModel]) -> ChainVerificationResponse:
        now = datetime.now(timezone.utc)
        genesis = compute_genesis_hash(case_id)
        if not items:
            return ChainVerificationResponse(
                status=ChainVerificationStatus.EMPTY,
                case_id=case_id,
                chain_type="evidence",
                total_records=0,
                corrupted_sequence=None,
                corrupted_record_id=None,
                genesis_hash=genesis,
                head_hash=None,
                details=None,
                verified_at=now,
            )

        expected_prev = genesis
        expected_seq = 1

        for it in items:
            # 1. Sequence continuity check
            if it.sequence_number != expected_seq:
                return ChainVerificationResponse(
                    status=ChainVerificationStatus.TAMPERED,
                    case_id=case_id,
                    chain_type="evidence",
                    total_records=len(items),
                    corrupted_sequence=it.sequence_number,
                    corrupted_record_id=str(it.id),
                    genesis_hash=genesis,
                    head_hash=None,
                    details=ChainVerificationMismatch(
                        failure_reason="SEQUENCE_DISCONTINUITY",
                        expected_sequence=expected_seq,
                        actual_sequence=it.sequence_number,
                        expected_hash=None,
                        actual_hash=None,
                        message=f"Sequence discontinuity in evidence chain: expected {expected_seq}, found {it.sequence_number}.",
                    ),
                    verified_at=now,
                )

            # 2. Chain linkage check
            if it.prev_hash != expected_prev:
                reason = "GENESIS_HASH_MISMATCH" if expected_seq == 1 else "CHAIN_LINK_BROKEN"
                return ChainVerificationResponse(
                    status=ChainVerificationStatus.TAMPERED,
                    case_id=case_id,
                    chain_type="evidence",
                    total_records=len(items),
                    corrupted_sequence=it.sequence_number,
                    corrupted_record_id=str(it.id),
                    genesis_hash=genesis,
                    head_hash=None,
                    details=ChainVerificationMismatch(
                        failure_reason=reason,
                        expected_hash=expected_prev,
                        actual_hash=it.prev_hash,
                        expected_sequence=expected_seq,
                        actual_sequence=it.sequence_number,
                        message=f"Cryptographic linkage broken at sequence {it.sequence_number}. Predecessor hash mismatch.",
                    ),
                    verified_at=now,
                )

            # 3. Payload integrity check
            canonical_payload = canonicalize_rfc8785(extract_evidence_payload(it))
            computed_payload_hash = hashlib.sha256(canonical_payload.encode("utf-8")).hexdigest()
            if it.canonical_payload_hash and computed_payload_hash != it.canonical_payload_hash:
                return ChainVerificationResponse(
                    status=ChainVerificationStatus.TAMPERED,
                    case_id=case_id,
                    chain_type="evidence",
                    total_records=len(items),
                    corrupted_sequence=it.sequence_number,
                    corrupted_record_id=str(it.id),
                    genesis_hash=genesis,
                    head_hash=None,
                    details=ChainVerificationMismatch(
                        failure_reason="PAYLOAD_TAMPERED",
                        expected_hash=computed_payload_hash,
                        actual_hash=it.canonical_payload_hash,
                        expected_sequence=expected_seq,
                        actual_sequence=it.sequence_number,
                        message=f"Evidence payload tampered at sequence {it.sequence_number}.",
                    ),
                    verified_at=now,
                )

            # 4. Current hash recalculation check
            actor_id = getattr(it, "actor_id", None) or getattr(it, "source", None) or "system"
            timestamp = it.created_at if hasattr(it, "created_at") and it.created_at else it.collected_at
            computed_current = compute_chain_hash(
                prev_hash=it.prev_hash,
                canonical_payload=canonical_payload,
                timestamp=timestamp,
                actor_id=actor_id,
            )
            if computed_current != it.current_hash:
                return ChainVerificationResponse(
                    status=ChainVerificationStatus.TAMPERED,
                    case_id=case_id,
                    chain_type="evidence",
                    total_records=len(items),
                    corrupted_sequence=it.sequence_number,
                    corrupted_record_id=str(it.id),
                    genesis_hash=genesis,
                    head_hash=None,
                    details=ChainVerificationMismatch(
                        failure_reason="HASH_MISMATCH",
                        expected_hash=computed_current,
                        actual_hash=it.current_hash,
                        expected_sequence=expected_seq,
                        actual_sequence=it.sequence_number,
                        message=f"Hash mismatch at sequence {it.sequence_number}. Evidence item header, timestamp, or actor modified.",
                    ),
                    verified_at=now,
                )

            expected_prev = it.current_hash
            expected_seq += 1

        return ChainVerificationResponse(
            status=ChainVerificationStatus.VALID,
            case_id=case_id,
            chain_type="evidence",
            total_records=len(items),
            corrupted_sequence=None,
            corrupted_record_id=None,
            genesis_hash=genesis,
            head_hash=items[-1].current_hash,
            details=None,
            verified_at=now,
        )
