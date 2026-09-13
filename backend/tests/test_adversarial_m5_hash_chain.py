"""
Adversarial Test Suite for Milestone 5: Cryptographic Hash Chains & Forensic Integrity Verification.
Covers aggressive failure injection, cryptographic stress testing, and tenant isolation:
1. Single-bit / single-byte payload tampering (audit & evidence).
2. Timestamp tampering (microsecond alterations & timezone shifts).
3. Actor ID spoofing.
4. Sequence number manipulation (gaps, duplicate sequence, reordering).
5. Chain link breaking (modifying prev_hash in middle of chain).
6. Genesis block anchor corruption (altering case_id binding).
7. Cross-case transposition attack (reassigning valid blocks from Case A to Case B).
8. Empty chain verification (returns EMPTY status).
9. Tenant isolation attack: Cross-tenant lookup returns 404 IDOR defense.
10. Deep chain integrity stress test (50-block scale).
"""
import uuid
import hashlib
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import List, Tuple
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
from sqlalchemy import update, delete

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
    AuditEventModel,
    EvidenceItemModel,
)
from backend.app.persistence.audit_repository import AuditRepository
from backend.app.persistence.evidence_repository import EvidenceRepository
from backend.app.core.auth import create_access_token, Role


# ---------------------------------------------------------------------------
# Test Helpers & Fixtures
# ---------------------------------------------------------------------------

async def _create_test_case(
    db: AsyncSession,
    tenant_id: str = "TN-STATE",
    district_id: str = "CHENNAI",
    station_id: str = "PS-CENTRAL",
) -> Case:
    """Helper to persist a test case with tenant scoping."""
    case = Case(
        id=str(uuid.uuid4()),
        fir_number=f"FIR/2026/{tenant_id[:2]}/{uuid.uuid4().hex[:6].upper()}",
        tenant_id=tenant_id,
        district_id=district_id,
        police_station_id=station_id,
        victim_reference="Adversarial Test Target",
        loss_amount_inr=Decimal("250000.00"),
        status="INVESTIGATING",
    )
    db.add(case)
    await db.commit()
    await db.refresh(case)
    return case


async def _create_audit_chain(
    db: AsyncSession,
    case_id: str,
    count: int = 3,
    tenant_id: str = "TN-STATE",
) -> List[AuditEventModel]:
    """Helper to create a valid cryptographic audit chain of length `count`."""
    base_time = datetime(2026, 9, 13, 10, 0, 0, tzinfo=timezone.utc)
    records = []
    for i in range(1, count + 1):
        ev = AuditEvent(
            id=str(uuid.uuid4()),
            case_id=case_id,
            actor_id=f"IO-Investigator-{i}",
            event_type=AuditEventType.TRACE_STARTED if i % 2 == 0 else AuditEventType.CASE_OPENED,
            action_summary=f"Legitimate forensic action step {i} on blockchain trace",
            metadata={"step": i, "target_asset": "TRC20:USDT", "hop": i},
            content_hash="init",
            created_at=base_time + timedelta(seconds=i * 15),
        )
        rec = await AuditRepository.record_event(db, ev, tenant_id=tenant_id)
        records.append(rec)
    return records


async def _create_evidence_chain(
    db: AsyncSession,
    case_id: str,
    count: int = 3,
    tenant_id: str = "TN-STATE",
) -> List[EvidenceItemModel]:
    """Helper to create a valid cryptographic evidence items chain of length `count`."""
    base_time = datetime(2026, 9, 13, 10, 0, 0, tzinfo=timezone.utc)
    items = []
    trace_id = str(uuid.uuid4())
    for i in range(1, count + 1):
        it = EvidenceItem(
            id=f"ev_adv_{i}_{uuid.uuid4().hex[:8]}",
            case_id=case_id,
            trace_id=trace_id,
            evidence_type=EvidenceType.TRANSACTION_RECORD,
            classification=EvidenceClassification.OBSERVED,
            title=f"Blockchain transaction observed at sequence {i}",
            source="trongrid",
            payload={"tx_id": f"tx_{i}_{uuid.uuid4().hex[:6]}", "amount": 1000.0 * i, "seq": i},
            content_hash="init",
            collected_at=base_time + timedelta(seconds=i * 10),
        )
        items.append(it)
    saved = await EvidenceRepository.save_evidence_items(db, items, tenant_id=tenant_id)
    return saved


def _auth_headers(role: str = Role.INVESTIGATING_OFFICER.value, tenant_id: str = "TN-STATE") -> dict:
    """Helper to generate Bearer authorization headers with specified role and tenant."""
    token = create_access_token({
        "sub": f"OFFICER-{tenant_id}",
        "role": role,
        "tenant_id": tenant_id,
        "district_id": "DISTRICT-1",
        "police_station_id": "STATION-1",
    })
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# 1. Single-Bit / Single-Byte Payload Tampering
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_scenario_1_single_byte_payload_tampering(test_engine, async_client: AsyncClient):
    """
    Scenario 1: Adversary modifies a single character or byte in an audit event
    or evidence payload. Verifier must detect tampering, pinpoint corrupted sequence,
    and report TAMPERED with failure_reason PAYLOAD_TAMPERED or HASH_MISMATCH.
    """
    session_factory = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as db:
        case = await _create_test_case(db, tenant_id="TN-STATE")
        audit_recs = await _create_audit_chain(db, case.id, count=3, tenant_id="TN-STATE")
        ev_recs = await _create_evidence_chain(db, case.id, count=3, tenant_id="TN-STATE")

        # Confirm initial validity
        v_init_audit = await AuditRepository.verify_integrity(db, case.id, tenant_id="TN-STATE")
        assert v_init_audit.status == "VALID"
        v_init_ev = await EvidenceRepository.verify_integrity(db, case.id, tenant_id="TN-STATE")
        assert v_init_ev.status == "VALID"

        # 1a. Single-character tampering in Audit action_summary (Record 2)
        original_summary = audit_recs[1].action_summary
        tampered_summary = original_summary[:-1] + "X"  # Flip last byte
        await db.execute(
            update(AuditEventModel)
            .where(AuditEventModel.id == audit_recs[1].id)
            .values(action_summary=tampered_summary)
        )
        await db.commit()

        v_audit = await AuditRepository.verify_integrity(db, case.id, tenant_id="TN-STATE")
        assert v_audit.status == "TAMPERED"
        assert v_audit.corrupted_sequence == 2
        assert v_audit.corrupted_record_id == str(audit_recs[1].id)
        assert v_audit.details is not None
        assert v_audit.details.failure_reason == "PAYLOAD_TAMPERED"

        # Verify via HTTP API endpoint
        res = await async_client.get(
            f"/api/v1/cases/{case.id}/audit/verify-integrity",
            headers=_auth_headers(tenant_id="TN-STATE"),
        )
        assert res.status_code == 200
        body = res.json()
        assert body["status"] == "TAMPERED"
        assert body["corrupted_sequence"] == 2
        assert body["details"]["failure_reason"] == "PAYLOAD_TAMPERED"

        # 1b. Single-byte tampering in Evidence payload dictionary (Item 2)
        tampered_payload = dict(ev_recs[1].payload)
        tampered_payload["amount"] = 2000.01  # Alter amount by 1 cent
        await db.execute(
            update(EvidenceItemModel)
            .where(EvidenceItemModel.id == ev_recs[1].id)
            .values(payload=tampered_payload)
        )
        await db.commit()

        v_ev = await EvidenceRepository.verify_integrity(db, case.id, tenant_id="TN-STATE")
        assert v_ev.status == "TAMPERED"
        assert v_ev.corrupted_sequence == 2
        assert v_ev.corrupted_record_id == ev_recs[1].id
        assert v_ev.details.failure_reason == "PAYLOAD_TAMPERED"

        # Verify via HTTP API endpoint
        res_ev = await async_client.get(
            f"/api/v1/cases/{case.id}/evidence/verify-integrity",
            headers=_auth_headers(tenant_id="TN-STATE"),
        )
        assert res_ev.status_code == 200
        body_ev = res_ev.json()
        assert body_ev["status"] == "TAMPERED"
        assert body_ev["corrupted_sequence"] == 2
        assert body_ev["details"]["failure_reason"] == "PAYLOAD_TAMPERED"

        # 1c. Sophisticated tampering: Attacker modifies payload AND updates canonical_payload_hash,
        # but fails to forge current_hash (SHA-256 second preimage resistance).
        new_payload = {"tx_id": "tx_forged_999", "amount": 999999.0, "seq": 2}
        canonical_new = canonicalize_rfc8785(new_payload)
        new_payload_hash = hashlib.sha256(canonical_new.encode("utf-8")).hexdigest()
        await db.execute(
            update(EvidenceItemModel)
            .where(EvidenceItemModel.id == ev_recs[1].id)
            .values(payload=new_payload, canonical_payload_hash=new_payload_hash)
        )
        await db.commit()

        v_ev_sophisticated = await EvidenceRepository.verify_integrity(db, case.id, tenant_id="TN-STATE")
        assert v_ev_sophisticated.status == "TAMPERED"
        assert v_ev_sophisticated.corrupted_sequence == 2
        # Payload hash matched, but step 4 current_hash check caught the tampering!
        assert v_ev_sophisticated.details.failure_reason == "HASH_MISMATCH"


# ---------------------------------------------------------------------------
# 2. Timestamp Tampering
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_scenario_2_timestamp_tampering(test_engine, async_client: AsyncClient):
    """
    Scenario 2: Adversary alters microsecond, second, or timezone designator on a record.
    The hash chain binds created_at / timestamp; any perturbation must be caught as HASH_MISMATCH.
    """
    session_factory = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as db:
        case = await _create_test_case(db, tenant_id="TN-STATE")
        audit_recs = await _create_audit_chain(db, case.id, count=3, tenant_id="TN-STATE")
        ev_recs = await _create_evidence_chain(db, case.id, count=3, tenant_id="TN-STATE")

        # 2a. Audit record: Perturb timestamp by exactly +1 microsecond
        target_rec = audit_recs[1]
        tampered_ts = target_rec.created_at + timedelta(microseconds=1)
        await db.execute(
            update(AuditEventModel)
            .where(AuditEventModel.id == target_rec.id)
            .values(created_at=tampered_ts)
        )
        await db.commit()

        v_audit = await AuditRepository.verify_integrity(db, case.id, tenant_id="TN-STATE")
        assert v_audit.status == "TAMPERED"
        assert v_audit.corrupted_sequence == 2
        assert v_audit.corrupted_record_id == str(target_rec.id)
        assert v_audit.details.failure_reason == "HASH_MISMATCH"

        # Check API
        res = await async_client.get(
            f"/api/v1/cases/{case.id}/audit/verify-integrity",
            headers=_auth_headers(tenant_id="TN-STATE"),
        )
        assert res.status_code == 200
        assert res.json()["status"] == "TAMPERED"
        assert res.json()["details"]["failure_reason"] == "HASH_MISMATCH"

        # 2b. Evidence item: Perturb timestamp by +10 seconds
        target_ev = ev_recs[2]
        tampered_ev_ts = target_ev.created_at + timedelta(seconds=10)
        await db.execute(
            update(EvidenceItemModel)
            .where(EvidenceItemModel.id == target_ev.id)
            .values(created_at=tampered_ev_ts)
        )
        await db.commit()

        v_ev = await EvidenceRepository.verify_integrity(db, case.id, tenant_id="TN-STATE")
        assert v_ev.status == "TAMPERED"
        assert v_ev.corrupted_sequence == 3
        assert v_ev.corrupted_record_id == target_ev.id
        assert v_ev.details.failure_reason == "HASH_MISMATCH"


# ---------------------------------------------------------------------------
# 3. Actor ID Spoofing
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_scenario_3_actor_id_spoofing(test_engine, async_client: AsyncClient):
    """
    Scenario 3: Adversary modifies the author/actor ID of an event or evidence item
    to attribute unauthorized actions to another officer or cover an identity.
    Verifier recalculates current_hash and detects HASH_MISMATCH.
    """
    session_factory = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as db:
        case = await _create_test_case(db, tenant_id="TN-STATE")
        audit_recs = await _create_audit_chain(db, case.id, count=3, tenant_id="TN-STATE")
        ev_recs = await _create_evidence_chain(db, case.id, count=3, tenant_id="TN-STATE")

        # 3a. Audit event: Change actor_id from IO-Investigator-2 to IO-SuperAdmin-Attacker
        target_audit = audit_recs[1]
        await db.execute(
            update(AuditEventModel)
            .where(AuditEventModel.id == target_audit.id)
            .values(actor_id="IO-SuperAdmin-Attacker")
        )
        await db.commit()

        v_audit = await AuditRepository.verify_integrity(db, case.id, tenant_id="TN-STATE")
        assert v_audit.status == "TAMPERED"
        assert v_audit.corrupted_sequence == 2
        assert v_audit.corrupted_record_id == str(target_audit.id)
        assert v_audit.details.failure_reason == "HASH_MISMATCH"

        # 3b. Evidence item: Change actor_id on record 3
        target_ev = ev_recs[2]
        await db.execute(
            update(EvidenceItemModel)
            .where(EvidenceItemModel.id == target_ev.id)
            .values(actor_id="rogue_collector_spoof")
        )
        await db.commit()

        v_ev = await EvidenceRepository.verify_integrity(db, case.id, tenant_id="TN-STATE")
        assert v_ev.status == "TAMPERED"
        assert v_ev.corrupted_sequence == 3
        assert v_ev.corrupted_record_id == target_ev.id
        assert v_ev.details.failure_reason == "HASH_MISMATCH"


# ---------------------------------------------------------------------------
# 4. Sequence Number Manipulation (Gaps, Duplicates, Reordering)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_scenario_4_sequence_number_manipulation(test_engine, async_client: AsyncClient):
    """
    Scenario 4: Sequence number manipulation vectors:
    4a. Gap in middle: deleting record 2 creates gap 1 -> 3. Detected as SEQUENCE_DISCONTINUITY.
    4b. Gap at head: deleting record 1 creates sequence starting at 2. Detected as SEQUENCE_DISCONTINUITY.
    4c. Duplicate sequence numbers: two records with sequence 2. Detected as SEQUENCE_DISCONTINUITY.
    4d. Reordering: swapping sequence numbers causes cryptographic link check or hash failure.
    """
    session_factory = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    # 4a. Gap in middle (Audit)
    async with session_factory() as db:
        case = await _create_test_case(db, tenant_id="TN-STATE")
        recs = await _create_audit_chain(db, case.id, count=3, tenant_id="TN-STATE")

        # Delete sequence 2
        await db.execute(delete(AuditEventModel).where(AuditEventModel.id == recs[1].id))
        await db.commit()

        v_audit = await AuditRepository.verify_integrity(db, case.id, tenant_id="TN-STATE")
        assert v_audit.status == "TAMPERED"
        assert v_audit.corrupted_sequence == 3
        assert v_audit.details.failure_reason == "SEQUENCE_DISCONTINUITY"
        assert v_audit.details.expected_sequence == 2
        assert v_audit.details.actual_sequence == 3

    # 4b. Head deletion / sequence starting at > 1 (Evidence)
    async with session_factory() as db:
        case = await _create_test_case(db, tenant_id="TN-STATE")
        evs = await _create_evidence_chain(db, case.id, count=3, tenant_id="TN-STATE")

        # Delete sequence 1
        await db.execute(delete(EvidenceItemModel).where(EvidenceItemModel.id == evs[0].id))
        await db.commit()

        v_ev = await EvidenceRepository.verify_integrity(db, case.id, tenant_id="TN-STATE")
        assert v_ev.status == "TAMPERED"
        assert v_ev.corrupted_sequence == 2
        assert v_ev.details.failure_reason == "SEQUENCE_DISCONTINUITY"
        assert v_ev.details.expected_sequence == 1
        assert v_ev.details.actual_sequence == 2

    # 4c. Duplicate sequence number injection (Audit)
    async with session_factory() as db:
        case = await _create_test_case(db, tenant_id="TN-STATE")
        recs = await _create_audit_chain(db, case.id, count=3, tenant_id="TN-STATE")

        # Alter record 3's sequence number to 2 (creating duplicate sequence 2)
        await db.execute(
            update(AuditEventModel)
            .where(AuditEventModel.id == recs[2].id)
            .values(sequence_number=2)
        )
        await db.commit()

        v_dup = await AuditRepository.verify_integrity(db, case.id, tenant_id="TN-STATE")
        assert v_dup.status == "TAMPERED"
        assert v_dup.corrupted_sequence == 2
        assert v_dup.details.failure_reason == "SEQUENCE_DISCONTINUITY"

    # 4d. Sequence reordering / swap (Evidence)
    async with session_factory() as db:
        case = await _create_test_case(db, tenant_id="TN-STATE")
        evs = await _create_evidence_chain(db, case.id, count=3, tenant_id="TN-STATE")

        # Swap sequence numbers of item 2 and item 3
        await db.execute(
            update(EvidenceItemModel)
            .where(EvidenceItemModel.id == evs[1].id)
            .values(sequence_number=3)
        )
        await db.execute(
            update(EvidenceItemModel)
            .where(EvidenceItemModel.id == evs[2].id)
            .values(sequence_number=2)
        )
        await db.commit()

        v_swap = await EvidenceRepository.verify_integrity(db, case.id, tenant_id="TN-STATE")
        assert v_swap.status == "TAMPERED"
        assert v_swap.details.failure_reason in ("CHAIN_LINK_BROKEN", "HASH_MISMATCH")


# ---------------------------------------------------------------------------
# 5. Chain Link Breaking (modifying prev_hash in middle of chain)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_scenario_5_chain_link_breaking(test_engine, async_client: AsyncClient):
    """
    Scenario 5: Adversary modifies prev_hash in the middle of a chain (e.g. sequence 2 or 3).
    Verifier must catch CHAIN_LINK_BROKEN and pinpoint predecessor mismatch.
    """
    session_factory = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as db:
        case = await _create_test_case(db, tenant_id="TN-STATE")
        audit_recs = await _create_audit_chain(db, case.id, count=4, tenant_id="TN-STATE")
        ev_recs = await _create_evidence_chain(db, case.id, count=4, tenant_id="TN-STATE")

        # 5a. Audit record 3: modify prev_hash to random 64-character hex
        bogus_hash = hashlib.sha256(b"injected_broken_link").hexdigest()
        await db.execute(
            update(AuditEventModel)
            .where(AuditEventModel.id == audit_recs[2].id)
            .values(prev_hash=bogus_hash)
        )
        await db.commit()

        v_audit = await AuditRepository.verify_integrity(db, case.id, tenant_id="TN-STATE")
        assert v_audit.status == "TAMPERED"
        assert v_audit.corrupted_sequence == 3
        assert v_audit.corrupted_record_id == str(audit_recs[2].id)
        assert v_audit.details.failure_reason == "CHAIN_LINK_BROKEN"
        assert v_audit.details.expected_hash == audit_recs[1].current_hash
        assert v_audit.details.actual_hash == bogus_hash

        # 5b. Evidence item 2: modify prev_hash to all zeros
        zero_hash = "0" * 64
        await db.execute(
            update(EvidenceItemModel)
            .where(EvidenceItemModel.id == ev_recs[1].id)
            .values(prev_hash=zero_hash)
        )
        await db.commit()

        v_ev = await EvidenceRepository.verify_integrity(db, case.id, tenant_id="TN-STATE")
        assert v_ev.status == "TAMPERED"
        assert v_ev.corrupted_sequence == 2
        assert v_ev.corrupted_record_id == ev_recs[1].id
        assert v_ev.details.failure_reason == "CHAIN_LINK_BROKEN"
        assert v_ev.details.expected_hash == ev_recs[0].current_hash
        assert v_ev.details.actual_hash == zero_hash


# ---------------------------------------------------------------------------
# 6. Genesis Block Anchor Corruption (altering case_id binding)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_scenario_6_genesis_block_anchor_corruption(test_engine, async_client: AsyncClient):
    """
    Scenario 6: Adversary corrupts block 1's prev_hash (genesis anchor):
    6a. Corrupting block 1's prev_hash to an arbitrary hash triggers GENESIS_HASH_MISMATCH.
    6b. Binding block 1's prev_hash to another case's genesis hash triggers GENESIS_HASH_MISMATCH.
    """
    session_factory = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as db:
        case = await _create_test_case(db, tenant_id="TN-STATE")
        audit_recs = await _create_audit_chain(db, case.id, count=3, tenant_id="TN-STATE")
        ev_recs = await _create_evidence_chain(db, case.id, count=3, tenant_id="TN-STATE")

        true_genesis = compute_genesis_hash(case.id)

        # 6a. Audit block 1: corrupt prev_hash to arbitrary hash
        bogus_genesis = hashlib.sha256(b"fake_genesis").hexdigest()
        await db.execute(
            update(AuditEventModel)
            .where(AuditEventModel.id == audit_recs[0].id)
            .values(prev_hash=bogus_genesis)
        )
        await db.commit()

        v_audit = await AuditRepository.verify_integrity(db, case.id, tenant_id="TN-STATE")
        assert v_audit.status == "TAMPERED"
        assert v_audit.corrupted_sequence == 1
        assert v_audit.corrupted_record_id == str(audit_recs[0].id)
        assert v_audit.details.failure_reason == "GENESIS_HASH_MISMATCH"
        assert v_audit.details.expected_hash == true_genesis
        assert v_audit.details.actual_hash == bogus_genesis

        # 6b. Evidence block 1: bind prev_hash to another case's genesis hash
        other_case_id = str(uuid.uuid4())
        other_genesis = compute_genesis_hash(other_case_id)
        await db.execute(
            update(EvidenceItemModel)
            .where(EvidenceItemModel.id == ev_recs[0].id)
            .values(prev_hash=other_genesis)
        )
        await db.commit()

        v_ev = await EvidenceRepository.verify_integrity(db, case.id, tenant_id="TN-STATE")
        assert v_ev.status == "TAMPERED"
        assert v_ev.corrupted_sequence == 1
        assert v_ev.corrupted_record_id == ev_recs[0].id
        assert v_ev.details.failure_reason == "GENESIS_HASH_MISMATCH"
        assert v_ev.details.expected_hash == true_genesis
        assert v_ev.details.actual_hash == other_genesis


# ---------------------------------------------------------------------------
# 7. Cross-Case Transposition Attack
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_scenario_7_cross_case_transposition_attack(test_engine, async_client: AsyncClient):
    """
    Scenario 7: Adversary copies valid, uncorrupted blocks from Case A into Case B:
    7a. Transposing Block 1 of Case A into Case B as Block 1: Fails immediately with
        GENESIS_HASH_MISMATCH because Block 1 is bound to SHA256("GENESIS:" + case_A).
    7b. Transposing Block 2 of Case A into Case B at Sequence 2: Fails with
        CHAIN_LINK_BROKEN because Case A's Block 2 points to Case A's Block 1.
    7c. Transposing the entire chain of Case A into Case B: Fails at Sequence 1.
    """
    session_factory = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as db:
        case_a = await _create_test_case(db, tenant_id="TN-STATE")
        case_b = await _create_test_case(db, tenant_id="TN-STATE")

        chain_a = await _create_audit_chain(db, case_a.id, count=3, tenant_id="TN-STATE")
        chain_b = await _create_audit_chain(db, case_b.id, count=3, tenant_id="TN-STATE")

        # 7a. Transpose Block 1 of Case A into Case B as its Block 1
        # (Reassign Case A's Block 1 to Case B and delete Case B's original Block 1)
        await db.execute(delete(AuditEventModel).where(AuditEventModel.id == chain_b[0].id))
        await db.execute(
            update(AuditEventModel)
            .where(AuditEventModel.id == chain_a[0].id)
            .values(case_id=case_b.id)
        )
        await db.commit()

        v_transposed_1 = await AuditRepository.verify_integrity(db, case_b.id, tenant_id="TN-STATE")
        assert v_transposed_1.status == "TAMPERED"
        assert v_transposed_1.corrupted_sequence == 1
        assert v_transposed_1.details.failure_reason == "GENESIS_HASH_MISMATCH"
        assert v_transposed_1.details.expected_hash == compute_genesis_hash(case_b.id)
        assert v_transposed_1.details.actual_hash == compute_genesis_hash(case_a.id)

    # 7b. Transpose Block 2 of Case A into Case B at sequence 2
    async with session_factory() as db:
        case_c = await _create_test_case(db, tenant_id="TN-STATE")
        case_d = await _create_test_case(db, tenant_id="TN-STATE")

        ev_c = await _create_evidence_chain(db, case_c.id, count=3, tenant_id="TN-STATE")
        ev_d = await _create_evidence_chain(db, case_d.id, count=3, tenant_id="TN-STATE")

        # Replace Case D's Block 2 with Case C's Block 2
        await db.execute(delete(EvidenceItemModel).where(EvidenceItemModel.id == ev_d[1].id))
        await db.execute(
            update(EvidenceItemModel)
            .where(EvidenceItemModel.id == ev_c[1].id)
            .values(case_id=case_d.id)
        )
        await db.commit()

        v_transposed_2 = await EvidenceRepository.verify_integrity(db, case_d.id, tenant_id="TN-STATE")
        assert v_transposed_2.status == "TAMPERED"
        assert v_transposed_2.corrupted_sequence == 2
        assert v_transposed_2.details.failure_reason == "CHAIN_LINK_BROKEN"
        assert v_transposed_2.details.expected_hash == ev_d[0].current_hash
        assert v_transposed_2.details.actual_hash == ev_c[0].current_hash


# ---------------------------------------------------------------------------
# 8. Empty Chain Verification (returns EMPTY status)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_scenario_8_empty_chain_verification(test_engine, async_client: AsyncClient):
    """
    Scenario 8: Verifying an investigation case with zero audit records or evidence items
    must return status EMPTY with 0 total_records and no corrupted sequence.
    """
    session_factory = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as db:
        case = await _create_test_case(db, tenant_id="TN-STATE")

        # 8a. Direct repository checks
        v_audit = await AuditRepository.verify_integrity(db, case.id, tenant_id="TN-STATE")
        assert v_audit.status == "EMPTY"
        assert v_audit.total_records == 0
        assert v_audit.corrupted_sequence is None
        assert v_audit.corrupted_record_id is None
        assert v_audit.head_hash is None
        assert v_audit.genesis_hash == compute_genesis_hash(case.id)

        v_ev = await EvidenceRepository.verify_integrity(db, case.id, tenant_id="TN-STATE")
        assert v_ev.status == "EMPTY"
        assert v_ev.total_records == 0
        assert v_ev.corrupted_sequence is None
        assert v_ev.head_hash is None

        # 8b. API checks
        res_audit = await async_client.get(
            f"/api/v1/cases/{case.id}/audit/verify-integrity",
            headers=_auth_headers(tenant_id="TN-STATE"),
        )
        assert res_audit.status_code == 200
        data_audit = res_audit.json()
        assert data_audit["status"] == "EMPTY"
        assert data_audit["total_records"] == 0
        assert data_audit["genesis_hash"] == compute_genesis_hash(case.id)

        res_ev = await async_client.get(
            f"/api/v1/cases/{case.id}/evidence/verify-integrity",
            headers=_auth_headers(tenant_id="TN-STATE"),
        )
        assert res_ev.status_code == 200
        data_ev = res_ev.json()
        assert data_ev["status"] == "EMPTY"
        assert data_ev["total_records"] == 0


# ---------------------------------------------------------------------------
# 9. Tenant Isolation Attack (404 IDOR Defense)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_scenario_9_tenant_isolation_attack_idor_defense(test_engine, async_client: AsyncClient):
    """
    Scenario 9: Tenant isolation attack & Insecure Direct Object Reference (IDOR) defense.
    Attempting to verify the evidence or audit chain of another tenant must strictly return HTTP 404.
    Direct repository queries must return EMPTY status rather than leaking foreign records.
    """
    session_factory = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as db:
        # Case belongs to Tamil Nadu State Police (TN-STATE)
        case_tn = await _create_test_case(db, tenant_id="TN-STATE")
        await _create_audit_chain(db, case_tn.id, count=3, tenant_id="TN-STATE")
        await _create_evidence_chain(db, case_tn.id, count=3, tenant_id="TN-STATE")

    # Tokens for multiple agencies and roles
    tn_auditor_header = _auth_headers(role=Role.AUDITOR.value, tenant_id="TN-STATE")
    tn_io_header = _auth_headers(role=Role.INVESTIGATING_OFFICER.value, tenant_id="TN-STATE")
    tn_sup_header = _auth_headers(role=Role.SUPERVISOR.value, tenant_id="TN-STATE")
    tn_adm_header = _auth_headers(role=Role.ADMIN.value, tenant_id="TN-STATE")

    dl_io_header = _auth_headers(role=Role.INVESTIGATING_OFFICER.value, tenant_id="DL-STATE")
    ka_auditor_header = _auth_headers(role=Role.AUDITOR.value, tenant_id="KA-STATE")

    # 9a. Authorized officers within TN-STATE succeed
    for header in [tn_auditor_header, tn_io_header, tn_sup_header, tn_adm_header]:
        res_a = await async_client.get(f"/api/v1/cases/{case_tn.id}/audit/verify-integrity", headers=header)
        assert res_a.status_code == 200
        assert res_a.json()["status"] == "VALID"

        res_e = await async_client.get(f"/api/v1/cases/{case_tn.id}/evidence/verify-integrity", headers=header)
        assert res_e.status_code == 200
        assert res_e.json()["status"] == "VALID"

    # 9b. Cross-tenant IDOR attack: DL-STATE and KA-STATE officers attempt access
    res_idor_audit_dl = await async_client.get(
        f"/api/v1/cases/{case_tn.id}/audit/verify-integrity",
        headers=dl_io_header,
    )
    assert res_idor_audit_dl.status_code == 404
    assert res_idor_audit_dl.json()["detail"]["code"] == "NOT_FOUND"

    res_idor_ev_dl = await async_client.get(
        f"/api/v1/cases/{case_tn.id}/evidence/verify-integrity",
        headers=dl_io_header,
    )
    assert res_idor_ev_dl.status_code == 404

    res_idor_ka = await async_client.get(
        f"/api/v1/cases/{case_tn.id}/audit/verify-integrity",
        headers=ka_auditor_header,
    )
    assert res_idor_ka.status_code == 404

    # 9c. Non-existent Case ID returns 404
    non_existent = str(uuid.uuid4())
    res_non_existent = await async_client.get(
        f"/api/v1/cases/{non_existent}/audit/verify-integrity",
        headers=tn_io_header,
    )
    assert res_non_existent.status_code == 404

    # 9d. Direct repository level isolation: foreign tenant query yields EMPTY, zero leaks
    async with session_factory() as db:
        rep_audit = await AuditRepository.verify_integrity(db, case_tn.id, tenant_id="DL-STATE")
        assert rep_audit.status == "EMPTY"
        assert rep_audit.total_records == 0

        rep_ev = await EvidenceRepository.verify_integrity(db, case_tn.id, tenant_id="DL-STATE")
        assert rep_ev.status == "EMPTY"
        assert rep_ev.total_records == 0


# ---------------------------------------------------------------------------
# 10. Deep Chain Integrity Stress Test (50 Blocks)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_deep_chain_integrity_and_tail_tamper(test_engine, async_client: AsyncClient):
    """
    Stress test: Builds a 50-block cryptographic hash chain.
    - Confirms O(N) verification operates with zero false positives.
    - Injects single-byte corruption at sequence 49 (near tail).
    - Verifies instant detection of exact corrupted sequence.
    """
    session_factory = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as db:
        case = await _create_test_case(db, tenant_id="TN-STATE")
        recs = await _create_audit_chain(db, case.id, count=50, tenant_id="TN-STATE")
        assert len(recs) == 50

        # Verify entire 50-block chain
        v_full = await AuditRepository.verify_integrity(db, case.id, tenant_id="TN-STATE")
        assert v_full.status == "VALID"
        assert v_full.total_records == 50
        assert v_full.corrupted_sequence is None
        assert v_full.head_hash == recs[-1].current_hash

        # Tamper near the tail: Sequence 49
        tampered_summary = recs[48].action_summary + " [MALICIOUS_INJECTION]"
        await db.execute(
            update(AuditEventModel)
            .where(AuditEventModel.id == recs[48].id)
            .values(action_summary=tampered_summary)
        )
        await db.commit()

        v_tampered = await AuditRepository.verify_integrity(db, case.id, tenant_id="TN-STATE")
        assert v_tampered.status == "TAMPERED"
        assert v_tampered.corrupted_sequence == 49
        assert v_tampered.corrupted_record_id == str(recs[48].id)
        assert v_tampered.details.failure_reason == "PAYLOAD_TAMPERED"
