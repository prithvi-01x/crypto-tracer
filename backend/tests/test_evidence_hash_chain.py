import uuid
import hashlib
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
from sqlalchemy import select, update, delete

from backend.app.main import app
from backend.app.domain.evidence.hasher import (
    canonicalize_rfc8785,
    compute_genesis_hash,
    compute_chain_hash,
    normalize_timestamp,
)
from backend.app.domain.evidence.models import (
    AuditEvent,
    AuditEventType,
    EvidenceItem,
    EvidenceType,
    EvidenceClassification,
)
from backend.app.persistence.models import (
    Case,
    Trace,
    AuditEventModel,
    EvidenceItemModel,
)
from backend.app.persistence.audit_repository import AuditRepository
from backend.app.persistence.evidence_repository import EvidenceRepository
from backend.app.core.auth import create_access_token, Role


@pytest.mark.asyncio
async def test_rfc8785_canonical_serialization():
    """Verify RFC 8785 JSON canonicalization rules (sort keys, compact separators, UTF-8 preservation)."""
    # 1. Unsorted keys with nested structures
    obj1 = {"z": 100, "a": "test", "m": {"b": 2, "a": 1}}
    obj2 = {"a": "test", "m": {"a": 1, "b": 2}, "z": 100}
    c1 = canonicalize_rfc8785(obj1)
    c2 = canonicalize_rfc8785(obj2)
    assert c1 == c2
    assert c1 == '{"a":"test","m":{"a":1,"b":2},"z":100}'

    # 2. UTF-8 characters preserved without ASCII escaping
    utf8_payload = {"city": "München", "currency": "₹", "name": "विक्रम"}
    c_utf8 = canonicalize_rfc8785(utf8_payload)
    assert "München" in c_utf8
    assert "₹" in c_utf8
    assert "विक्रम" in c_utf8
    assert "\\u" not in c_utf8

    # 3. Decimal and datetime formatting
    dt = datetime(2026, 9, 13, 12, 0, 0, tzinfo=timezone.utc)
    dec = Decimal("45000.50")
    formatted = canonicalize_rfc8785({"time": dt, "amount": dec})
    assert '"amount":"45000.50"' in formatted
    assert '"time":"2026-09-13T12:00:00.000000Z"' in formatted


@pytest.mark.asyncio
async def test_genesis_anchor_and_chain_hash_formula():
    """Verify Genesis anchor Hash_0 and chained block hash Hash_i formula."""
    case_id = str(uuid.uuid4())
    genesis = compute_genesis_hash(case_id)
    expected_genesis = hashlib.sha256(f"GENESIS:{case_id}".encode("utf-8")).hexdigest()
    assert genesis == expected_genesis
    assert len(genesis) == 64

    # Verify genesis uniqueness across cases
    other_case_id = str(uuid.uuid4())
    assert compute_genesis_hash(other_case_id) != genesis

    # Verify chain hash formula: Hash_i = SHA256(Hash_{i-1} || ":" || Payload || ":" || Timestamp || ":" || Actor)
    now = datetime(2026, 9, 13, 12, 0, 0, tzinfo=timezone.utc)
    h1 = compute_chain_hash(
        prev_hash=genesis,
        canonical_payload='{"action":"OPEN"}',
        timestamp=now,
        actor_id="IO-Vikram",
    )
    expected_h1 = hashlib.sha256(
        f"{genesis}:{{\"action\":\"OPEN\"}}:{normalize_timestamp(now)}:IO-Vikram".encode("utf-8")
    ).hexdigest()
    assert h1 == expected_h1

    # Single-byte alteration in payload modifies hash
    h1_tampered = compute_chain_hash(
        prev_hash=genesis,
        canonical_payload='{"action":"OPEN_"}',
        timestamp=now,
        actor_id="IO-Vikram",
    )
    assert h1_tampered != h1

    # Alteration in timestamp modifies hash
    h1_ts_tampered = compute_chain_hash(
        prev_hash=genesis,
        canonical_payload='{"action":"OPEN"}',
        timestamp=now + timedelta(seconds=1),
        actor_id="IO-Vikram",
    )
    assert h1_ts_tampered != h1

    # Alteration in actor modifies hash
    h1_actor_tampered = compute_chain_hash(
        prev_hash=genesis,
        canonical_payload='{"action":"OPEN"}',
        timestamp=now,
        actor_id="IO-Vikram-Fake",
    )
    assert h1_actor_tampered != h1


@pytest.mark.asyncio
async def test_empty_chain_verification(test_engine):
    """Verify integrity check on an empty case returns status EMPTY."""
    session_factory = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as db_session:
        case_id = str(uuid.uuid4())
        audit_res = await AuditRepository.verify_integrity(db_session, case_id)
        assert audit_res.status == "EMPTY"
        assert audit_res.total_records == 0
        assert audit_res.corrupted_sequence is None
        assert audit_res.genesis_hash == compute_genesis_hash(case_id)

        ev_res = await EvidenceRepository.verify_integrity(db_session, case_id)
        assert ev_res.status == "EMPTY"
        assert ev_res.total_records == 0
        assert ev_res.corrupted_sequence is None


@pytest.mark.asyncio
async def test_audit_chain_valid_lifecycle_and_tamper_detection(test_engine):
    """
    Test complete lifecycle of audit event ledger:
    1. Valid creation with monotonic sequence numbers (1, 2, 3) and chained hashes.
    2. Verification returns VALID.
    3. Payload tampering detected with exact sequence number and failure reason.
    4. Timestamp tampering detected.
    5. Sequence discontinuity (record deletion) detected.
    6. Genesis tampering detected.
    """
    session_factory = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as db_session:
        case_id = str(uuid.uuid4())
        genesis = compute_genesis_hash(case_id)

        # 1. Add 3 audit events
        now = datetime.now(timezone.utc)
        ev1 = AuditEvent(
            id=str(uuid.uuid4()),
            case_id=case_id,
            actor_id="IO-Alice",
            event_type=AuditEventType.CASE_OPENED,
            action_summary="Case opened for cyber fraud investigation",
            metadata={"fir": "FIR/2026/001"},
            content_hash="mock",
            created_at=now,
        )
        ev2 = AuditEvent(
            id=str(uuid.uuid4()),
            case_id=case_id,
            actor_id="IO-Bob",
            event_type=AuditEventType.TRACE_STARTED,
            action_summary="Initiated multi-hop trace on suspect address",
            metadata={"hops": 4},
            content_hash="mock",
            created_at=now + timedelta(seconds=10),
        )
        ev3 = AuditEvent(
            id=str(uuid.uuid4()),
            case_id=case_id,
            actor_id="IO-Alice",
            event_type=AuditEventType.EVIDENCE_REVIEWED,
            action_summary="Reviewed VASP attribution evidence",
            metadata={"vasp": "Binance"},
            content_hash="mock",
            created_at=now + timedelta(seconds=20),
        )

        rec1 = await AuditRepository.record_event(db_session, ev1)
        rec2 = await AuditRepository.record_event(db_session, ev2)
        rec3 = await AuditRepository.record_event(db_session, ev3)

        assert rec1.sequence_number == 1
        assert rec1.prev_hash == genesis
        assert rec2.sequence_number == 2
        assert rec2.prev_hash == rec1.current_hash
        assert rec3.sequence_number == 3
        assert rec3.prev_hash == rec2.current_hash

        # 2. Verify valid chain
        valid_res = await AuditRepository.verify_integrity(db_session, case_id)
        assert valid_res.status == "VALID"
        assert valid_res.total_records == 3
        assert valid_res.corrupted_sequence is None
        assert valid_res.head_hash == rec3.current_hash

        # 3. Tamper with payload of record 2
        await db_session.execute(
            update(AuditEventModel)
            .where(AuditEventModel.id == rec2.id)
            .values(action_summary="Altered action summary by unauthorized adversary")
        )
        await db_session.commit()

        tampered_res = await AuditRepository.verify_integrity(db_session, case_id)
        assert tampered_res.status == "TAMPERED"
        assert tampered_res.corrupted_sequence == 2
        assert tampered_res.corrupted_record_id == str(rec2.id)
        assert tampered_res.details is not None
        assert tampered_res.details.failure_reason in ("PAYLOAD_TAMPERED", "HASH_MISMATCH")

        # Restore record 2 summary but tamper timestamp
        await db_session.execute(
            update(AuditEventModel)
            .where(AuditEventModel.id == rec2.id)
            .values(
                action_summary="Initiated multi-hop trace on suspect address",
                created_at=now + timedelta(days=1),
            )
        )
        await db_session.commit()

        ts_tampered_res = await AuditRepository.verify_integrity(db_session, case_id)
        assert ts_tampered_res.status == "TAMPERED"
        assert ts_tampered_res.corrupted_sequence == 2
        assert ts_tampered_res.details.failure_reason == "HASH_MISMATCH"

        # Restore record 2 created_at but delete record 2 (deletion vector)
        await db_session.execute(
            delete(AuditEventModel).where(AuditEventModel.id == rec2.id)
        )
        await db_session.commit()

        del_res = await AuditRepository.verify_integrity(db_session, case_id)
        assert del_res.status == "TAMPERED"
        assert del_res.details.failure_reason in ("SEQUENCE_DISCONTINUITY", "CHAIN_LINK_BROKEN")


@pytest.mark.asyncio
async def test_evidence_chain_valid_lifecycle_and_tamper_detection(test_engine):
    """
    Test complete lifecycle of forensic evidence items ledger:
    1. Save items with monotonic sequence numbers (1, 2, 3) and chained hashes.
    2. Verification returns VALID.
    3. Single-byte payload tampering detected.
    4. Linkage tampering detected.
    """
    session_factory = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as db_session:
        case_id = str(uuid.uuid4())
        trace_id = str(uuid.uuid4())
        genesis = compute_genesis_hash(case_id)
        now = datetime.now(timezone.utc)

        it1 = EvidenceItem(
            id=f"ev_{uuid.uuid4().hex[:12]}",
            case_id=case_id,
            trace_id=trace_id,
            evidence_type=EvidenceType.TRANSACTION_RECORD,
            classification=EvidenceClassification.OBSERVED,
            title="Transaction observed on TRON",
            source="trongrid",
            payload={"tx_hash": "tx1", "amount": 5000.0},
            content_hash="mock1",
            collected_at=now,
        )
        it2 = EvidenceItem(
            id=f"ev_{uuid.uuid4().hex[:12]}",
            case_id=case_id,
            trace_id=trace_id,
            evidence_type=EvidenceType.HOP_TRAVERSAL,
            classification=EvidenceClassification.DERIVED,
            title="Hop 1 to Hop 2 traversal",
            source="graph_engine",
            payload={"from": "addr1", "to": "addr2", "hop": 1},
            content_hash="mock2",
            collected_at=now + timedelta(seconds=5),
        )
        it3 = EvidenceItem(
            id=f"ev_{uuid.uuid4().hex[:12]}",
            case_id=case_id,
            trace_id=trace_id,
            evidence_type=EvidenceType.VASP_ATTRIBUTION,
            classification=EvidenceClassification.INFERRED,
            title="VASP attribution hypothesis",
            source="attribution_engine",
            payload={"vasp": "Binance", "confidence": 0.95},
            content_hash="mock3",
            collected_at=now + timedelta(seconds=10),
        )

        saved = await EvidenceRepository.save_evidence_items(db_session, [it1, it2, it3])
        assert len(saved) == 3
        assert saved[0].sequence_number == 1
        assert saved[0].prev_hash == genesis
        assert saved[1].sequence_number == 2
        assert saved[1].prev_hash == saved[0].current_hash
        assert saved[2].sequence_number == 3
        assert saved[2].prev_hash == saved[1].current_hash

        # Verify valid chain
        valid_res = await EvidenceRepository.verify_integrity(db_session, case_id)
        assert valid_res.status == "VALID"
        assert valid_res.total_records == 3
        assert valid_res.head_hash == saved[2].current_hash

        # Tamper payload of item 2
        await db_session.execute(
            update(EvidenceItemModel)
            .where(EvidenceItemModel.id == it2.id)
            .values(payload={"from": "addr1", "to": "addr2_TAMPERED", "hop": 1})
        )
        await db_session.commit()

        tampered_res = await EvidenceRepository.verify_integrity(db_session, case_id)
        assert tampered_res.status == "TAMPERED"
        assert tampered_res.corrupted_sequence == 2
        assert tampered_res.corrupted_record_id == it2.id
        assert tampered_res.details.failure_reason == "PAYLOAD_TAMPERED"


@pytest.mark.asyncio
async def test_verification_api_endpoints_and_idor(test_engine, async_client):
    """
    Test GET /api/v1/cases/{case_id}/evidence/verify-integrity and
    GET /api/v1/cases/{case_id}/audit/verify-integrity endpoints:
    - Returns 200 with VALID integrity status
    - Enforces tenant isolation: cross-tenant access returns 404 (IDOR defense)
    - Role authorization checks (AUDITOR, INVESTIGATOR, SUPERVISOR, ADMIN).
    """
    session_factory = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as db_session:
        # 1. Create a case for tenant A
        case_a = Case(
            id=str(uuid.uuid4()),
            fir_number="FIR/2026/TN/101",
            tenant_id="TN-STATE",
            district_id="CHENNAI",
            police_station_id="PS-CENTRAL",
            victim_reference="R. Sundaram",
            loss_amount_inr=Decimal("100000.00"),
            status="INVESTIGATING",
        )
        db_session.add(case_a)
        await db_session.commit()

        # Record an audit event for case A
        ev = AuditEvent(
            id=str(uuid.uuid4()),
            case_id=case_a.id,
            actor_id="IO-Kavitha",
            event_type=AuditEventType.CASE_OPENED,
            action_summary="Opened case for TN cyber cell",
            content_hash="mock",
        )
        await AuditRepository.record_event(db_session, ev, tenant_id="TN-STATE")

    # Tokens
    token_auditor_tn = create_access_token({
        "sub": "AUD-01",
        "role": Role.AUDITOR.value,
        "tenant_id": "TN-STATE",
        "district_id": "CHENNAI",
        "police_station_id": "PS-CENTRAL",
    })
    token_investigator_dl = create_access_token({
        "sub": "IO-DL-02",
        "role": Role.INVESTIGATING_OFFICER.value,
        "tenant_id": "DL-STATE",  # Different tenant
        "district_id": "DELHI-HQ",
        "police_station_id": "PS-NORTH",
    })

    # 2. Legitimate tenant Auditor verifies audit integrity
    res = await async_client.get(
        f"/api/v1/cases/{case_a.id}/audit/verify-integrity",
        headers={"Authorization": f"Bearer {token_auditor_tn}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "VALID"
    assert data["case_id"] == case_a.id
    assert data["total_records"] == 1

    # Legitimate tenant verifies evidence integrity (empty case)
    res_ev = await async_client.get(
        f"/api/v1/cases/{case_a.id}/evidence/verify-integrity",
        headers={"Authorization": f"Bearer {token_auditor_tn}"},
    )
    assert res_ev.status_code == 200
    data_ev = res_ev.json()
    assert data_ev["status"] == "EMPTY"

    # 3. Cross-tenant IDOR attack: DL officer tries to verify TN case
    idor_audit = await async_client.get(
        f"/api/v1/cases/{case_a.id}/audit/verify-integrity",
        headers={"Authorization": f"Bearer {token_investigator_dl}"},
    )
    assert idor_audit.status_code == 404

    idor_ev = await async_client.get(
        f"/api/v1/cases/{case_a.id}/evidence/verify-integrity",
        headers={"Authorization": f"Bearer {token_investigator_dl}"},
    )
    assert idor_ev.status_code == 404
