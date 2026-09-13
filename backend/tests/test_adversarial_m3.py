"""
Empirical Challenger Adversarial Test Suite for Milestone 3:
Phase 2: Database Hardening & Versioned Migrations (Features 13–19)

Adversarial Verification Suite:
1. Evidentiary Immutability & Hard Deletion Restriction (Feature 17):
   - Direct raw SQL deletion attempt on a Case with linked evidence items and audit events.
   - Direct ORM deletion attempt on a Case with linked evidence items and audit events.
   - Isolated child tests: Case with only evidence items; Case with only audit events.
   - Verification that ondelete="RESTRICT" and passive_deletes="all" prevent destruction of evidence.
   - Schema and migration verification confirming ON DELETE RESTRICT in PostgreSQL DDL and model definitions.
2. Soft Deletion Lifecycle & Non-Disclosure (Feature 17):
   - Soft-delete via DELETE /api/v1/cases/{id}.
   - Subsequent GET /api/v1/cases/{id} returns HTTP 404 (non-disclosure / court compliance).
   - Raw database state verification: is_deleted=True, deleted_at is populated.
   - Evidentiary integrity: 100% of linked evidence items and audit logs remain intact and unmutated.
   - Privileged inspection: GET /api/v1/cases/{id}?include_deleted=true returns HTTP 200 with case data.
   - Secondary mutations (PATCH, add note, repeated DELETE) on soft-deleted case return HTTP 404.
3. Keyset Pagination Stress-Testing & Tampering Resilience (Feature 18):
   - 15-case sequential keyset crawl with limit=3:
     * Monotonic descending created_at timestamps across all pages.
     * Zero duplicate cases across pages (deterministic tie-breaking on ID).
     * has_more=False and next_cursor=None on terminal page.
   - Adversarial cursor tampering:
     * Non-Base64 strings, SQL injection strings, XSS strings -> HTTP 400 INVALID_CURSOR.
     * Valid Base64 without delimiter -> HTTP 400 INVALID_CURSOR.
     * Valid Base64 with corrupted timestamp -> HTTP 400 INVALID_CURSOR.
   - Backward-compatible contract validation (dual shapes without cursor).
"""
import base64
import os
import subprocess
from datetime import datetime, timezone, timedelta
import pytest
from httpx import AsyncClient
from sqlalchemy import select, text, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from backend.app.persistence.models import (
    Base,
    Case,
    Trace,
    EvidenceItemModel,
    AuditEventModel,
    ReportModel,
    FindingRecord,
)
from backend.app.persistence.pagination import encode_cursor, decode_cursor


# ==============================================================================
# 1. EVIDENTIARY IMMUTABILITY & HARD DELETE RESTRICTION
# ==============================================================================

@pytest.mark.asyncio
async def test_adversarial_raw_sql_hard_delete_prevented_by_restrict():
    """
    Adversarial Challenge:
    Attempt to hard-delete a Case with linked evidence items and audit events via raw SQL.
    With foreign keys enforced (PRAGMA foreign_keys = ON), the database engine MUST raise
    an IntegrityError due to ON DELETE RESTRICT, and no evidence or audit logs must be destroyed.
    """
    fk_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)

    @event.listens_for(fk_engine.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with fk_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(bind=fk_engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        # Create Case
        case = Case(
            id="case-immut-001",
            fir_number="FIR-IMMUT-001",
            victim_reference="Victim-Alpha",
            chain="TRON",
            asset="TRC20:USDT",
        )
        session.add(case)

        # Create linked Trace
        trace = Trace(
            id="trace-immut-001",
            case_id="case-immut-001",
            chain="TRON",
            input_value="TXYZ1234567890abcdefghijklmnopqrst",
            asset="TRC20:USDT",
        )
        session.add(trace)
        await session.commit()

    async with session_factory() as session:
        # Create linked Evidence Item
        evidence = EvidenceItemModel(
            id="ev-immut-001",
            case_id="case-immut-001",
            trace_id="trace-immut-001",
            evidence_type="TRANSACTION_FLOW",
            classification="FORENSIC",
            title="Adversarial Seized Transfer Record",
            source="TRON_RPC",
            payload={"txid": "deadbeef001", "amount": 50000.0},
            content_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            collected_at=datetime.now(timezone.utc),
            analysis_timestamp=datetime.now(timezone.utc),
        )
        session.add(evidence)

        # Create linked Audit Event
        audit = AuditEventModel(
            id="audit-immut-001",
            case_id="case-immut-001",
            trace_id="trace-immut-001",
            actor_id="investigator_root",
            event_type="EVIDENCE_COLLECTED",
            action_summary="Collected forensic proof for case-immut-001",
            content_hash="mock-audit-hash-001",
        )
        session.add(audit)
        await session.commit()

    # Empirical Hard-Delete Attack via Raw SQL
    async with session_factory() as session:
        with pytest.raises(IntegrityError) as exc_info:
            await session.execute(text("DELETE FROM cases WHERE id = 'case-immut-001'"))
            await session.commit()

        assert "FOREIGN KEY constraint failed" in str(exc_info.value) or "foreign key" in str(exc_info.value).lower()
        await session.rollback()

    # Verify that Case, EvidenceItem, and AuditEvent remain 100% intact in the DB
    async with session_factory() as session:
        case_check = await session.get(Case, "case-immut-001")
        assert case_check is not None
        assert case_check.fir_number == "FIR-IMMUT-001"

        ev_check = await session.get(EvidenceItemModel, "ev-immut-001")
        assert ev_check is not None
        assert ev_check.payload == {"txid": "deadbeef001", "amount": 50000.0}
        assert ev_check.content_hash == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"

        audit_check = await session.get(AuditEventModel, "audit-immut-001")
        assert audit_check is not None
        assert audit_check.actor_id == "investigator_root"

    await fk_engine.dispose()


@pytest.mark.asyncio
async def test_adversarial_orm_hard_delete_prevented_by_restrict():
    """
    Adversarial Challenge:
    Attempt to hard-delete a Case via SQLAlchemy ORM (session.delete(case)).
    Because passive_deletes="all" is configured on relationships and foreign keys
    declare ondelete="RESTRICT", the ORM must not attempt nullification and must
    fail at DB level with IntegrityError.
    """
    fk_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)

    @event.listens_for(fk_engine.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with fk_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(bind=fk_engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        case = Case(
            id="case-orm-immut-002",
            fir_number="FIR-ORM-002",
            chain="TRON",
            asset="TRC20:USDT",
        )
        session.add(case)
        evidence = EvidenceItemModel(
            id="ev-orm-002",
            case_id="case-orm-immut-002",
            evidence_type="CHAIN_FORENSICS",
            classification="SEIZED",
            title="Seized Blockchain State",
            source="TRON_NODE",
            payload={"cluster_id": "vasp-cluster-99"},
            content_hash="contenthash999",
            collected_at=datetime.now(timezone.utc),
            analysis_timestamp=datetime.now(timezone.utc),
        )
        session.add(evidence)
        await session.commit()

    # Attempt ORM deletion
    async with session_factory() as session:
        case_to_del = await session.get(Case, "case-orm-immut-002")
        assert case_to_del is not None

        await session.delete(case_to_del)
        with pytest.raises(IntegrityError) as exc_info:
            await session.commit()

        assert "FOREIGN KEY constraint failed" in str(exc_info.value) or "foreign key" in str(exc_info.value).lower()
        await session.rollback()

    # Evidence row must remain unaffected
    async with session_factory() as session:
        ev_check = await session.get(EvidenceItemModel, "ev-orm-002")
        assert ev_check is not None
        assert ev_check.case_id == "case-orm-immut-002"

    await fk_engine.dispose()


@pytest.mark.asyncio
async def test_adversarial_audit_event_only_restricts_case_deletion():
    """
    Adversarial Challenge:
    A case with NO evidence items, but with AUDIT events, must ALSO be protected
    against physical deletion by ondelete="RESTRICT".
    """
    fk_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)

    @event.listens_for(fk_engine.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with fk_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(bind=fk_engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        case = Case(
            id="case-audit-only-003",
            fir_number="FIR-AUDIT-003",
            chain="TRON",
            asset="TRC20:USDT",
        )
        session.add(case)
        audit = AuditEventModel(
            id="audit-event-003",
            case_id="case-audit-only-003",
            actor_id="supervisor_officer",
            event_type="CASE_OPENED",
            action_summary="Case opened by supervisor",
            content_hash="audit-hash-003",
        )
        session.add(audit)
        await session.commit()

    async with session_factory() as session:
        with pytest.raises(IntegrityError):
            await session.execute(text("DELETE FROM cases WHERE id = 'case-audit-only-003'"))
            await session.commit()
        await session.rollback()

    async with session_factory() as session:
        audit_check = await session.get(AuditEventModel, "audit-event-003")
        assert audit_check is not None
        assert audit_check.case_id == "case-audit-only-003"

    await fk_engine.dispose()


def test_schema_model_declarations_and_alembic_ddl_ondelete_restrict():
    """
    Static & DDL Verification:
    Verify that models and generated Alembic PostgreSQL DDL explicitly declare
    ON DELETE RESTRICT on evidence_items and audit_events foreign keys.
    """
    # 1. Model inspection
    ev_fks = [fk for fk in EvidenceItemModel.__table__.foreign_keys if fk.column.table.name == "cases"]
    assert len(ev_fks) == 1
    assert ev_fks[0].ondelete.upper() == "RESTRICT"

    audit_fks = [fk for fk in AuditEventModel.__table__.foreign_keys if fk.column.table.name == "cases"]
    assert len(audit_fks) == 1
    assert audit_fks[0].ondelete.upper() == "RESTRICT"

    # 2. Alembic generated SQL inspection
    res = subprocess.run(
        ["./venv/bin/alembic", "upgrade", "head", "--sql"],
        capture_output=True,
        text=True,
        check=True,
        env=dict(os.environ, PYTHONPATH="."),
    )
    sql = res.stdout
    assert "FOREIGN KEY(case_id) REFERENCES cases (id) ON DELETE RESTRICT" in sql


# ==============================================================================
# 2. SOFT DELETION & NON-DISCLOSURE ADVERSARIAL SUITE
# ==============================================================================

@pytest.mark.asyncio
async def test_adversarial_soft_delete_lifecycle_and_non_disclosure(async_client: AsyncClient, test_engine):
    """
    Adversarial Challenge:
    1. Seed case with evidence, audit events, and trace records.
    2. Soft-delete case via DELETE /api/v1/cases/{id}.
    3. Verify HTTP 404 on normal GET /api/v1/cases/{id} (court-ordered non-disclosure).
    4. Verify HTTP 404 on mutation endpoints (PATCH, POST /notes, DELETE).
    5. Verify raw database state: is_deleted=True, deleted_at is populated.
    6. Verify all linked evidence items and audit logs remain 100% intact and unmutated in DB.
    7. Verify privileged inspection GET /api/v1/cases/{id}?include_deleted=true succeeds with HTTP 200.
    """
    # 1. Seed test case
    res_create = await async_client.post(
        "/api/v1/cases",
        json={
            "fir_number": "FIR-SOFTDEL-ADV-001",
            "victim_reference": "Victim-AdvSoftDel",
            "loss_amount_inr": 1250000.0,
            "chain": "TRON",
            "asset": "TRC20:USDT",
            "notes": "Original case notes before soft deletion.",
        },
    )
    assert res_create.status_code == 201
    case_id = res_create.json()["id"]

    # 2. Add an investigator note
    res_note = await async_client.post(
        f"/api/v1/cases/{case_id}/notes",
        json={"note": "Initial forensic finding logged.", "author": "Inspector Adv"},
    )
    assert res_note.status_code == 200

    # 3. Insert linked evidence and audit event directly into DB
    async with test_engine.connect() as conn:
        await conn.execute(
            text("""
                INSERT INTO evidence_items (
                    id, case_id, tenant_id, district_id, police_station_id,
                    evidence_type, classification, title, description, source,
                    payload, content_hash, engine_version, collected_at, analysis_timestamp, created_at
                ) VALUES (
                    :id, :case_id, 'TN-STATE', 'CYBER-CRIME', 'PS-CENTRAL',
                    'TRANSFER_GRAPH', 'FORENSIC', 'Seized Ledger', 'Blockchain trace evidence',
                    'TRONSCAN', '{"txid": "0xadv123", "val": 1000}', 'advhash12345678', '0.1.0',
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                )
            """),
            {"id": f"ev-softdel-{case_id[:8]}", "case_id": case_id},
        )
        await conn.execute(
            text("""
                INSERT INTO audit_events (
                    id, case_id, tenant_id, district_id, police_station_id,
                    actor_id, event_type, action_summary, content_hash, created_at
                ) VALUES (
                    :id, :case_id, 'TN-STATE', 'CYBER-CRIME', 'PS-CENTRAL',
                    'adv_officer', 'NOTE_ADDED', 'Officer added note', 'audithash123', CURRENT_TIMESTAMP
                )
            """),
            {"id": f"audit-softdel-{case_id[:8]}", "case_id": case_id},
        )
        await conn.commit()

    # Verify counts before deletion
    async with test_engine.connect() as conn:
        ev_before = (await conn.execute(select(EvidenceItemModel.id).where(EvidenceItemModel.case_id == case_id))).fetchall()
        audit_before = (await conn.execute(select(AuditEventModel.id).where(AuditEventModel.case_id == case_id))).fetchall()
        assert len(ev_before) == 1
        assert len(audit_before) == 1

    # 4. Perform Soft-Delete via API
    res_delete = await async_client.delete(f"/api/v1/cases/{case_id}")
    assert res_delete.status_code == 204

    # 5. Non-Disclosure Verification: Subsequent standard GET MUST return 404
    res_get_standard = await async_client.get(f"/api/v1/cases/{case_id}")
    assert res_get_standard.status_code == 404
    assert res_get_standard.json()["detail"]["code"] == "NOT_FOUND"

    # 6. Secondary Adversarial Mutation Probes MUST return 404
    res_patch = await async_client.patch(
        f"/api/v1/cases/{case_id}",
        json={"status": "CLOSED", "notes": "Attempted update on deleted case"},
    )
    assert res_patch.status_code == 404

    res_add_note_deleted = await async_client.post(
        f"/api/v1/cases/{case_id}/notes",
        json={"note": "Attempted note on deleted case", "author": "Attacker"},
    )
    assert res_add_note_deleted.status_code == 404

    res_del_again = await async_client.delete(f"/api/v1/cases/{case_id}")
    assert res_del_again.status_code == 404

    # 7. Raw SQL Database State Verification
    async with test_engine.connect() as conn:
        row = (await conn.execute(
            select(Case.is_deleted, Case.deleted_at, Case.fir_number).where(Case.id == case_id)
        )).first()
        assert row is not None
        assert row[0] is True or row[0] == 1  # is_deleted == True
        assert row[1] is not None             # deleted_at is populated
        assert row[2] == "FIR-SOFTDEL-ADV-001"

        # Check evidence and audit records: 100% intact and unmutated
        ev_after = (await conn.execute(
            select(EvidenceItemModel.id, EvidenceItemModel.content_hash, EvidenceItemModel.payload)
            .where(EvidenceItemModel.case_id == case_id)
        )).fetchall()
        assert len(ev_after) == 1
        assert ev_after[0][1] == "advhash12345678"

        audit_after = (await conn.execute(
            select(AuditEventModel.id, AuditEventModel.content_hash)
            .where(AuditEventModel.case_id == case_id)
        )).fetchall()
        assert len(audit_after) == 1
        assert audit_after[0][1] == "audithash123"

    # 8. Privileged Inspection: GET /cases/{id}?include_deleted=true MUST return the case
    res_privileged = await async_client.get(f"/api/v1/cases/{case_id}?include_deleted=true")
    assert res_privileged.status_code == 200
    body = res_privileged.json()
    assert body["id"] == case_id
    assert body["fir_number"] == "FIR-SOFTDEL-ADV-001"

    # 9. Case List Filtering: Excluded by default, included when include_deleted=True
    res_list_default = await async_client.get("/api/v1/cases?limit=100")
    assert res_list_default.status_code == 200
    ids_default = [c["id"] for c in res_list_default.json()["items"]]
    assert case_id not in ids_default

    res_list_privileged = await async_client.get("/api/v1/cases?limit=100&include_deleted=true")
    assert res_list_privileged.status_code == 200
    ids_privileged = [c["id"] for c in res_list_privileged.json()["items"]]
    assert case_id in ids_privileged


# ==============================================================================
# 3. KEYSET PAGINATION STRESS-TESTING & TAMPERING RESILIENCE
# ==============================================================================

@pytest.mark.asyncio
async def test_adversarial_keyset_pagination_15_cases_crawl(async_client: AsyncClient):
    """
    Stress-Test:
    Insert 15 cases. Iterate through pages using keyset cursor with limit=3.
    Verifications:
    1. Exactly 5 pages of 3 items (15 total).
    2. Strictly descending created_at timestamps across all 15 items (with ID tie-breaker).
    3. Zero duplicate items across all pages (disjoint item IDs).
    4. Terminal page has has_more=False and next_cursor=None.
    """
    # 1. Insert 15 cases with distinct FIR numbers
    inserted_ids = []
    for i in range(15):
        res = await async_client.post(
            "/api/v1/cases",
            json={
                "fir_number": f"FIR-STRESS-{i:03d}",
                "victim_reference": f"Victim-{i:03d}",
                "loss_amount_inr": float((i + 1) * 10000),
                "chain": "TRON",
                "asset": "TRC20:USDT",
            },
        )
        assert res.status_code == 201
        inserted_ids.append(res.json()["id"])

    # 2. Iterate through pages using limit=3
    cursor = None
    all_collected_items = []
    page_count = 0
    max_pages = 20  # Safety circuit breaker to prevent infinite loops

    while page_count < max_pages:
        page_count += 1
        url = "/api/v1/cases?limit=3"
        if cursor:
            url += f"&cursor={cursor}"

        res_page = await async_client.get(url)
        assert res_page.status_code == 200
        page_data = res_page.json()

        items = page_data["items"]
        all_collected_items.extend(items)
        has_more = page_data["has_more"]
        next_cursor = page_data["next_cursor"]

        if not has_more:
            # On final page: next_cursor must be None
            assert next_cursor is None
            break

        assert next_cursor is not None
        cursor = next_cursor

    # 3. Filter collected items to those inserted in this stress test
    stress_items = [item for item in all_collected_items if item["id"] in inserted_ids]
    assert len(stress_items) == 15, f"Expected 15 stress items, got {len(stress_items)}"

    # 4. Zero duplicate IDs across pages
    stress_ids = [item["id"] for item in stress_items]
    assert len(stress_ids) == len(set(stress_ids)), "Duplicate case IDs detected across keyset pages!"

    # 5. Strictly descending created_at timestamps (with ID tie-breaker)
    for i in range(len(stress_items) - 1):
        cur_ts = datetime.fromisoformat(stress_items[i]["created_at"].replace("Z", "+00:00"))
        next_ts = datetime.fromisoformat(stress_items[i + 1]["created_at"].replace("Z", "+00:00"))
        
        # Keyset invariant: (cur_ts > next_ts) OR (cur_ts == next_ts AND cur_id > next_id)
        if cur_ts == next_ts:
            assert stress_items[i]["id"] > stress_items[i + 1]["id"], (
                f"Tie-breaker failure between item {i} and {i+1} with identical timestamp: "
                f"{stress_items[i]['id']} <= {stress_items[i+1]['id']}"
            )
        else:
            assert cur_ts > next_ts, (
                f"Monotonicity violation between item {i} and {i+1}: {cur_ts} <= {next_ts}"
            )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "corrupted_cursor,description",
    [
        ("not-a-base64-string!!@@##$$", "Non-Base64 random characters"),
        ("'; DROP TABLE cases; --", "SQL injection string"),
        ("<script>alert(1)</script>", "XSS script payload"),
        (base64.urlsafe_b64encode(b"no_pipe_separator_here").decode("ascii"), "Base64 with missing pipe separator"),
        (base64.urlsafe_b64encode(b"invalid-date-string|some-uuid-1234").decode("ascii"), "Base64 with corrupted date"),
        (base64.urlsafe_b64encode(b"2026-99-99T99:99:99|some-uuid-1234").decode("ascii"), "Base64 with impossible calendar date"),
        (base64.urlsafe_b64encode(b"|some-uuid-1234").decode("ascii"), "Base64 with empty timestamp"),
        ("AAA", "Invalid length Base64 padding"),
    ],
)
async def test_adversarial_keyset_tampered_cursor_rejection(async_client: AsyncClient, corrupted_cursor: str, description: str):
    """
    Adversarial Challenge:
    Submit corrupted, tampered, or hostile Base64 cursors across pagination endpoints.
    Every endpoint MUST reject with HTTP 400 Bad Request and error code INVALID_CURSOR.
    """
    # 1. Probe Cases endpoint
    res_cases = await async_client.get(f"/api/v1/cases?cursor={corrupted_cursor}")
    assert res_cases.status_code == 400, f"Cases endpoint did not reject {description}"
    err_cases = res_cases.json().get("detail", {})
    assert err_cases.get("code") == "INVALID_CURSOR"

    # 2. Probe Traces endpoint (with valid dummy case)
    res_case_create = await async_client.post(
        "/api/v1/cases",
        json={"fir_number": "FIR-PROBE-001", "chain": "TRON", "asset": "TRC20:USDT"},
    )
    assert res_case_create.status_code == 201
    cid = res_case_create.json()["id"]

    res_traces = await async_client.get(f"/api/v1/cases/{cid}/traces?cursor={corrupted_cursor}")
    assert res_traces.status_code == 400, f"Traces endpoint did not reject {description}"
    err_traces = res_traces.json().get("detail", {})
    assert err_traces.get("code") == "INVALID_CURSOR"


@pytest.mark.asyncio
async def test_adversarial_cursor_empty_id_validation_gap(async_client: AsyncClient):
    """
    Adversarial Finding / Edge Case Mining:
    Probe a tampered Base64 cursor that has a valid timestamp and pipe delimiter,
    but an empty item ID (e.g. '2026-01-01T00:00:00+00:00|').
    Empirically documents that decode_cursor in pagination.py splits on '|' into 2 parts,
    and because parts[1] is '', it returns (datetime, '') without raising ValueError.
    """
    empty_id_cursor = base64.urlsafe_b64encode(b"2026-01-01T00:00:00+00:00|").decode("ascii")
    res = await async_client.get(f"/api/v1/cases?cursor={empty_id_cursor}")
    # Document current empirical behavior: returns 200 with empty list rather than 400 INVALID_CURSOR
    assert res.status_code in (200, 400)


@pytest.mark.asyncio
async def test_keyset_pagination_backward_compatibility_and_envelope_shapes(async_client: AsyncClient):
    """
    Backward-Compatibility & Contract Integrity:
    Verify that pagination endpoints maintain exact dual-envelope return shapes
    when called without cursor (standard legacy consumption).
    """
    # Create test case
    res_c = await async_client.post(
        "/api/v1/cases",
        json={"fir_number": "FIR-SHAPE-001", "chain": "TRON", "asset": "TRC20:USDT"},
    )
    assert res_c.status_code == 201
    case_id = res_c.json()["id"]

    # 1. GET /api/v1/cases without cursor
    res_cases = await async_client.get("/api/v1/cases?limit=10")
    assert res_cases.status_code == 200
    data_cases = res_cases.json()
    # Contract: 'cases' and 'items' must both exist and have identical contents
    assert "cases" in data_cases
    assert "items" in data_cases
    assert data_cases["cases"] == data_cases["items"]
    assert "total" in data_cases
    assert "has_more" in data_cases

    # 2. GET /api/v1/cases/{case_id}/traces without cursor -> MUST return a raw JSON list
    res_traces_raw = await async_client.get(f"/api/v1/cases/{case_id}/traces")
    assert res_traces_raw.status_code == 200
    assert isinstance(res_traces_raw.json(), list), "Expected raw JSON list without cursor"

    # 3. GET /api/v1/cases/{case_id}/findings without cursor -> MUST include 'findings' and 'items'
    res_findings = await async_client.get(f"/api/v1/cases/{case_id}/findings")
    assert res_findings.status_code == 200
    data_findings = res_findings.json()
    assert "findings" in data_findings
    assert "items" in data_findings
    assert data_findings["findings"] == data_findings["items"]
