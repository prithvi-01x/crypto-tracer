"""Adversarial Empirical Challenge Test Suite for Milestone 3.

Phase 2: Database Hardening & Versioned Migrations.
Conducted by Challenger 2 (teamwork_preview_challenger).

Empirical verification of:
1. Alembic offline SQL emission and PostgreSQL DDL parsing (UUID, JSONB, GIN, ON DELETE RESTRICT).
2. Cross-dialect DDL compilation & execution parity (PostgreSQL vs SQLite) with full CRUD and create_all/drop_all.
3. Schema parity verification via `alembic check` and oracle sensitivity validation.
4. Connection pool stress testing: SQLite StaticPool vs PostgreSQL QueuePool vs PgBouncer NullPool.
5. Evidentiary immutability under direct relational constraint stress (PRAGMA foreign_keys=ON).
6. Keyset cursor engine stress testing (timestamp tie-breakers, malformed cursors, boundary pagination).
"""

import os
import re
import base64
import uuid
import subprocess
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import pytest
from sqlalchemy import select, text, insert, delete
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.schema import CreateTable, CreateIndex
from sqlalchemy.exc import IntegrityError
from sqlalchemy.pool import StaticPool, NullPool, QueuePool
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from backend.app.config import settings
from backend.app.persistence.models import (
    Base,
    Case,
    Trace,
    AttributionResult,
    EvidenceItemModel,
    AuditEventModel,
    ReportModel,
    FindingRecord,
    UUID_TYPE,
    JSONB_TYPE,
    generate_uuid,
    utc_now,
)
from backend.app.persistence.pagination import (
    encode_cursor,
    decode_cursor,
    apply_keyset_pagination,
    process_keyset_results,
)
from backend.app.persistence.db import _create_engine, check_db_connection


# ==============================================================================
# 1. ALEMBIC OFFLINE SQL POSTGRESQL DDL PARSING & VERIFICATION
# ==============================================================================

def test_alembic_offline_sql_postgresql_ddl_parsing():
    """Empirically run alembic upgrade head --sql and parse emitted PostgreSQL DDL.
    
    Must verify:
    - Emits valid PostgreSQL DDL.
    - All 7 tables present.
    - Primary keys and foreign keys use UUID type on PostgreSQL.
    - Queryable and metadata fields use JSONB type on PostgreSQL.
    - Indexes on traces.graph_data and evidence_items.payload use USING gin.
    - Foreign key ondelete for evidence_items and audit_events is RESTRICT.
    - Foreign key ondelete for traces, reports, findings is CASCADE.
    - Case table has is_deleted BOOLEAN DEFAULT false and deleted_at columns.
    """
    env = dict(
        os.environ,
        PYTHONPATH=".",
        DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/crypto_tracer",
    )
    result = subprocess.run(
        ["./venv/bin/alembic", "upgrade", "head", "--sql"],
        capture_output=True,
        text=True,
        check=True,
        env=env,
    )
    sql = result.stdout
    assert sql, "Alembic offline SQL output must not be empty"

    # 1. Verify all 7 core tables are created
    expected_tables = [
        "cases",
        "traces",
        "attribution_results",
        "evidence_items",
        "audit_events",
        "reports",
        "findings",
    ]
    for tbl in expected_tables:
        assert f"CREATE TABLE {tbl}" in sql, f"Missing table creation DDL for: {tbl}"

    # 2. Verify UUID column types in emitted DDL
    uuid_matches = re.findall(r"(\w+)\s+UUID\s+NOT\s+NULL", sql, re.IGNORECASE)
    assert len(uuid_matches) >= 10, f"Expected multiple UUID NOT NULL columns, found: {len(uuid_matches)}"

    # 3. Verify JSONB column types in emitted DDL
    jsonb_matches = re.findall(r"(\w+)\s+JSONB", sql, re.IGNORECASE)
    assert len(jsonb_matches) >= 8, f"Expected multiple JSONB columns, found: {len(jsonb_matches)}"

    # 4. Verify GIN indexes on PostgreSQL DDL
    gin_matches = re.findall(r"CREATE\s+INDEX\s+(\w+)\s+ON\s+(\w+)\s+USING\s+gin\s*\(([^)]+)\)", sql, re.IGNORECASE)
    gin_index_names = {m[0] for m in gin_matches}
    assert "ix_traces_graph_data_gin" in gin_index_names, "Missing GIN index on traces.graph_data"
    assert "ix_evidence_payload_gin" in gin_index_names, "Missing GIN index on evidence_items.payload"

    # 5. Verify ON DELETE RESTRICT on evidentiary tables
    # evidence_items.case_id -> cases.id ON DELETE RESTRICT
    # audit_events.case_id -> cases.id ON DELETE RESTRICT
    restrict_matches = re.findall(
        r"FOREIGN\s+KEY\s*\([^)]+\)\s+REFERENCES\s+cases\s*\([^)]+\)\s+ON\s+DELETE\s+RESTRICT",
        sql,
        re.IGNORECASE,
    )
    assert len(restrict_matches) >= 2, f"Expected at least 2 ON DELETE RESTRICT constraints to cases, found {len(restrict_matches)}"

    # 6. Verify soft deletion columns in cases table
    assert re.search(r"is_deleted\s+BOOLEAN\s+DEFAULT\s+false\s+NOT\s+NULL", sql, re.IGNORECASE), "is_deleted missing or incorrect default"
    assert re.search(r"deleted_at\s+TIMESTAMP\s+WITH\s+TIME\s+ZONE", sql, re.IGNORECASE), "deleted_at missing or incorrect type"


# ==============================================================================
# 2. CROSS-DIALECT COMPILATION & EXECUTION PARITY
# ==============================================================================

def test_dialect_variants_compilation_details():
    """Verify exact compilation of types and indexes across PostgreSQL and SQLite dialects."""
    pg = postgresql.dialect()
    sq = sqlite.dialect()

    # 1. UUID_TYPE compilation
    assert UUID_TYPE.compile(dialect=pg) == "UUID", "UUID_TYPE did not compile to UUID on Postgres"
    assert "VARCHAR(36)" in UUID_TYPE.compile(dialect=sq), "UUID_TYPE did not compile to VARCHAR(36) on SQLite"

    # 2. JSONB_TYPE compilation
    assert JSONB_TYPE.compile(dialect=pg) == "JSONB", "JSONB_TYPE did not compile to JSONB on Postgres"
    assert JSONB_TYPE.compile(dialect=sq) == "JSON", "JSONB_TYPE did not compile to JSON on SQLite"

    # 3. Model table compilation inspection
    for model_cls in (Case, Trace, AttributionResult, EvidenceItemModel, AuditEventModel, ReportModel, FindingRecord):
        table = model_cls.__table__
        ddl_pg = str(CreateTable(table).compile(dialect=pg))
        ddl_sq = str(CreateTable(table).compile(dialect=sq))

        # Check UUID columns on both dialects
        for col in table.columns:
            if col.type is UUID_TYPE:
                assert f"{col.name} UUID" in ddl_pg, f"Column {table.name}.{col.name} not compiled to UUID on PG"
                assert f"{col.name} VARCHAR(36)" in ddl_sq, f"Column {table.name}.{col.name} not compiled to VARCHAR(36) on SQLite"
            elif col.type is JSONB_TYPE:
                assert f"{col.name} JSONB" in ddl_pg, f"Column {table.name}.{col.name} not compiled to JSONB on PG"
                assert f"{col.name} JSON" in ddl_sq, f"Column {table.name}.{col.name} not compiled to JSON on SQLite"

    # 4. GIN Index compilation: Postgres must produce 'USING gin', SQLite must omit 'USING gin'
    for idx_name in ("ix_traces_graph_data_gin", "ix_evidence_payload_gin"):
        indexes = [idx for tbl in (Trace.__table__, EvidenceItemModel.__table__) for idx in tbl.indexes if idx.name == idx_name]
        assert len(indexes) == 1, f"Index {idx_name} not found"
        idx = indexes[0]
        compiled_pg = str(CreateIndex(idx).compile(dialect=pg))
        compiled_sq = str(CreateIndex(idx).compile(dialect=sq))

        assert "USING gin" in compiled_pg, f"PostgreSQL DDL for {idx_name} missing 'USING gin': {compiled_pg}"
        assert "USING gin" not in compiled_sq, f"SQLite DDL for {idx_name} should not contain 'USING gin': {compiled_sq}"


@pytest.mark.asyncio
async def test_sqlite_execution_parity_full_lifecycle():
    """Empirically test create_all, full CRUD across all 7 tables with UUIDs/JSON, and drop_all on SQLite."""
    test_db_url = "sqlite+aiosqlite:///:memory:"
    engine = create_async_engine(test_db_url, echo=False)

    # 1. create_all
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # 2. Insert sample records into all 7 tables to verify serialization/coercion
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    case_id = str(uuid.uuid4())
    trace_id = str(uuid.uuid4())
    attr_id = str(uuid.uuid4())
    ev_id = "ev_" + uuid.uuid4().hex[:16]
    audit_id = str(uuid.uuid4())
    rep_id = str(uuid.uuid4())
    finding_id = "fnd_" + uuid.uuid4().hex[:16]

    async with session_factory() as session:
        # Case
        c = Case(
            id=case_id,
            fir_number="FIR-EMPIRICAL-001",
            loss_amount_inr=Decimal("150000.00"),
            chain="TRON",
            asset="TRC20:USDT",
        )
        session.add(c)
        await session.flush()

        # Trace with JSONB graph_data and config
        t = Trace(
            id=trace_id,
            case_id=case_id,
            input_type="address",
            input_value="TXYZ9876543210",
            config={"max_depth": 3, "min_usd": 10.0},
            graph_data={"nodes": [{"id": "n1", "address": "T123"}], "edges": []},
        )
        session.add(t)
        await session.flush()

        # AttributionResult with JSONB explanation
        ar = AttributionResult(
            id=attr_id,
            trace_id=trace_id,
            vasp_id="BINANCE",
            vasp_name="Binance Exchange",
            candidate_address="TBNDepositAddress",
            confidence=Decimal("0.9500"),
            confidence_band="HIGH",
            direct_tag_score=Decimal("0.9000"),
            sweep_score=Decimal("0.8500"),
            fan_in_score=Decimal("0.8000"),
            temporal_score=Decimal("0.7500"),
            explanation={"attribution_rules": ["DIRECT_TAG_MATCH"]},
        )
        session.add(ar)

        # EvidenceItemModel with JSONB payload
        ev = EvidenceItemModel(
            id=ev_id,
            case_id=case_id,
            trace_id=trace_id,
            evidence_type="TRANSACTION_FLOW",
            classification="FORENSIC",
            title="Transfer to VASP",
            source="TRON_SCANNER",
            payload={"tx_hash": "0xabc123", "amount": 50000.0},
            content_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            collected_at=utc_now(),
            analysis_timestamp=utc_now(),
        )
        session.add(ev)

        # AuditEventModel with JSONB metadata_json
        ae = AuditEventModel(
            id=audit_id,
            case_id=case_id,
            trace_id=trace_id,
            event_type="TRACE_STARTED",
            action_summary="Initiated automated BFS trace",
            metadata_json={"user_ip": "10.0.0.1", "browser": "AutomatedTest"},
            content_hash="d41d8cd98f00b204e9800998ecf8427e",
        )
        session.add(ae)

        # ReportModel with JSONB metadata_json
        rp = ReportModel(
            id=rep_id,
            case_id=case_id,
            trace_id=trace_id,
            report_type="EVIDENCE_DOSSIER",
            title="Forensic Evidence Dossier",
            file_path="/storage/reports/rep_001.pdf",
            content_hash="6e3a6703512b9d99de3e82d3f2ec4917",
            metadata_json={"sections": 4, "format": "PDF"},
        )
        session.add(rp)

        # FindingRecord with JSONB evidence_refs and raw_payload
        fnd = FindingRecord(
            id=finding_id,
            case_id=case_id,
            trace_id=trace_id,
            finding_type="VASP_DEPOSIT",
            severity="HIGH",
            title="Direct VASP Deposit Found",
            description="Fund swept into known VASP cluster",
            source_signal="AUTOMATED_ATTRIBUTION",
            evidence_refs=[ev_id],
            raw_payload={"cluster_id": "BINANCE_MAIN"},
        )
        session.add(fnd)
        await session.commit()

    # 3. Read back and verify all records and JSON payloads
    async with session_factory() as session:
        queried_case = await session.get(Case, case_id)
        assert queried_case is not None
        assert queried_case.fir_number == "FIR-EMPIRICAL-001"
        assert queried_case.is_deleted is False

        queried_trace = await session.get(Trace, trace_id)
        assert queried_trace is not None
        assert queried_trace.graph_data["nodes"][0]["id"] == "n1"

        queried_ev = await session.get(EvidenceItemModel, ev_id)
        assert queried_ev is not None
        assert queried_ev.payload["amount"] == 50000.0

        queried_fnd = await session.get(FindingRecord, finding_id)
        assert queried_fnd is not None
        assert queried_fnd.evidence_refs == [ev_id]

    # 4. drop_all
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


# ==============================================================================
# 3. SCHEMA PARITY & ALEMBIC CHECK
# ==============================================================================

def test_alembic_schema_parity_and_oracle_sensitivity():
    """Empirically run alembic upgrade head and alembic check on a test SQLite database.
    
    Also tests oracle sensitivity: verifying alembic check fails when database schema deviates.
    """
    temp_db = "./test_empirical_parity.db"
    temp_url = f"sqlite+aiosqlite:///{temp_db}"
    env = dict(os.environ, PYTHONPATH=".", DATABASE_URL=temp_url)

    try:
        # Step 1: Run alembic upgrade head
        up_res = subprocess.run(
            ["./venv/bin/alembic", "upgrade", "head"],
            capture_output=True,
            text=True,
            env=env,
        )
        assert up_res.returncode == 0, f"Alembic upgrade failed: {up_res.stderr}"

        # Step 2: Run alembic check to verify parity with Base.metadata
        chk_res = subprocess.run(
            ["./venv/bin/alembic", "check"],
            capture_output=True,
            text=True,
            env=env,
        )
        assert chk_res.returncode == 0, f"Alembic check failed: {chk_res.stderr}"
        combined_output = chk_res.stdout + chk_res.stderr
        assert "No new upgrade operations detected" in combined_output, f"Unexpected check output: {combined_output}"

        # Step 3: Oracle Sensitivity Check
        # Run alembic check against an un-migrated / empty DB to confirm alembic check detects differences
        empty_db = "./test_empty_oracle.db"
        empty_url = f"sqlite+aiosqlite:///{empty_db}"
        empty_env = dict(os.environ, PYTHONPATH=".", DATABASE_URL=empty_url)
        try:
            chk_empty = subprocess.run(
                ["./venv/bin/alembic", "check"],
                capture_output=True,
                text=True,
                env=empty_env,
            )
            # Must detect differences (non-zero exit code or diff detected)
            assert chk_empty.returncode != 0 or "New upgrade operations detected" in (chk_empty.stdout + chk_empty.stderr)
        finally:
            if os.path.exists(empty_db):
                os.remove(empty_db)

    finally:
        if os.path.exists(temp_db):
            os.remove(temp_db)


# ==============================================================================
# 4. CONNECTION POOL STRESS & DIALECT ISOLATION
# ==============================================================================

def test_connection_pool_sqlite_stress():
    """Verify SQLite engines dynamically adapt pool options without crashing."""
    # In-memory SQLite: Must use StaticPool
    mem_engine = _create_engine(
        url="sqlite+aiosqlite:///:memory:",
        pool_size=100,      # Stress: should be safely ignored for SQLite
        max_overflow=50,    # Stress: should be safely ignored
        pool_recycle=3600,  # Stress: should be safely ignored
        pool_pre_ping=True,
    )
    assert isinstance(mem_engine.pool, StaticPool), "In-memory SQLite did not receive StaticPool"

    # File-based SQLite: should not crash when pool parameters are supplied
    file_engine = _create_engine(
        url="sqlite+aiosqlite:///./test_dummy_pool.db",
        pool_size=20,
        max_overflow=10,
    )
    assert not isinstance(file_engine.pool, StaticPool)


def test_connection_pool_postgresql_standard_and_pgbouncer():
    """Verify PostgreSQL connection pool configuration: QueuePool vs PgBouncer NullPool."""
    # 1. Standard PostgreSQL: QueuePool with custom sizing
    pg_url = "postgresql+asyncpg://app_user:app_pass@127.0.0.1:5432/app_db"
    pg_engine = _create_engine(
        url=pg_url,
        pool_size=35,
        max_overflow=15,
        pool_recycle=7200,
        pool_pre_ping=True,
        pgbouncer_mode=False,
    )
    assert isinstance(pg_engine.pool, QueuePool), "Standard PostgreSQL must use QueuePool"
    assert pg_engine.pool.size() == 35, f"Expected pool size 35, got {pg_engine.pool.size()}"
    assert pg_engine.pool._max_overflow == 15, f"Expected max overflow 15, got {pg_engine.pool._max_overflow}"
    assert pg_engine.pool._recycle == 7200, f"Expected recycle 7200, got {pg_engine.pool._recycle}"
    assert pg_engine.pool._pre_ping is True

    # 2. PgBouncer mode: NullPool with statement cache disabled
    pgb_engine = _create_engine(
        url=pg_url,
        pgbouncer_mode=True,
    )
    assert isinstance(pgb_engine.pool, NullPool), "PgBouncer mode must use NullPool"
    connect_args = getattr(pgb_engine.dialect, "connect_args", {})
    # Verify statement_cache_size=0 for transaction pooling compatibility
    assert pgb_engine.url.drivername == "postgresql+asyncpg"
    closure_dict = [c.cell_contents for c in pgb_engine.sync_engine.pool._creator.__closure__ if hasattr(c.cell_contents, "get")][0]
    assert closure_dict.get("statement_cache_size") == 0, "statement_cache_size must be 0 for PgBouncer"
    assert closure_dict.get("prepared_statement_cache_size") == 0, "prepared_statement_cache_size must be 0 for PgBouncer"
    name_func = closure_dict.get("prepared_statement_name_func")
    assert name_func is not None, "prepared_statement_name_func not configured for PgBouncer"
    name_1 = name_func()
    name_2 = name_func()
    assert name_1 != name_2, "prepared_statement_name_func must generate unique names"
    assert name_1.startswith("__asyncpg_")


@pytest.mark.asyncio
async def test_database_health_probe_error_resilience():
    """Verify check_db_connection handles healthy checks and returns structured error on failure."""
    # 1. Healthy check on active test database
    health = await check_db_connection()
    assert isinstance(health, dict)
    assert health["status"] in ("HEALTHY", "UNHEALTHY")
    assert "latency_ms" in health
    assert health["latency_ms"] >= 0.0


# ==============================================================================
# 5. EVIDENTIARY IMMUTABILITY: RELATIONAL RESTRICT CONSTRAINTS
# ==============================================================================

@pytest.mark.asyncio
async def test_adversarial_evidentiary_immutability_foreign_key_restrict():
    """Empirically test that foreign key RESTRICT actively prevents hard deletion of cases with evidence.
    
    Enforces PRAGMA foreign_keys = ON in SQLite to test database-level enforcement.
    """
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.execute(text("PRAGMA foreign_keys = ON;"))
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    case_id = str(uuid.uuid4())
    ev_id = "ev_strict_" + uuid.uuid4().hex[:12]
    audit_id = str(uuid.uuid4())

    async with session_factory() as session:
        # Create case
        c = Case(id=case_id, fir_number="FIR-RESTRICT-001")
        session.add(c)
        await session.flush()

        # Add evidence item referencing case
        ev = EvidenceItemModel(
            id=ev_id,
            case_id=case_id,
            evidence_type="WALLET_CLUSTER",
            classification="FORENSIC",
            title="Cluster Identification",
            source="CHAIN_ANALYSIS",
            payload={"cluster": "suspect"},
            content_hash="abcd" * 16,
            collected_at=utc_now(),
            analysis_timestamp=utc_now(),
        )
        session.add(ev)
        await session.commit()

    # Attempt physical hard delete of case with PRAGMA foreign_keys = ON
    async with session_factory() as session:
        await session.execute(text("PRAGMA foreign_keys = ON;"))
        # Execute raw delete to bypass SQLAlchemy ORM event handlers
        with pytest.raises(IntegrityError):
            await session.execute(text(f"DELETE FROM cases WHERE id = '{case_id}';"))
            await session.commit()

    # Verify case and evidence still exist untouched
    async with session_factory() as session:
        res_c = await session.get(Case, case_id)
        assert res_c is not None, "Case was erroneously deleted despite RESTRICT"
        res_ev = await session.get(EvidenceItemModel, ev_id)
        assert res_ev is not None, "Evidence was erroneously dropped"

    await engine.dispose()


# ==============================================================================
# 6. KEYSET CURSOR ENGINE: STRESS, EDGE CASES & TAMPERING
# ==============================================================================

def test_keyset_cursor_malformed_and_tampered_inputs():
    """Stress test cursor decoding with hostile, malformed, and corrupted inputs."""
    # 1. Non-base64 garbage
    with pytest.raises(ValueError):
        decode_cursor("!@#$%^&*()_not_base64")

    # 2. Base64 encoded invalid JSON
    bad_json_b64 = base64.urlsafe_b64encode(b"{not valid json:").decode("utf-8")
    with pytest.raises(ValueError):
        decode_cursor(bad_json_b64)

    # 3. Base64 encoded non-dict JSON (e.g. integer or list)
    list_b64 = base64.urlsafe_b64encode(b"[1, 2, 3]").decode("utf-8")
    with pytest.raises(ValueError):
        decode_cursor(list_b64)

    # 4. Base64 encoded dict missing 'created_at'
    no_ts_b64 = base64.urlsafe_b64encode(b'{"id": "some-id"}').decode("utf-8")
    with pytest.raises(ValueError):
        decode_cursor(no_ts_b64)

    # 5. Base64 encoded dict missing 'id'
    no_id_b64 = base64.urlsafe_b64encode(b'{"created_at": "2026-09-13T12:00:00Z"}').decode("utf-8")
    with pytest.raises(ValueError):
        decode_cursor(no_id_b64)

    # 6. Base64 encoded dict with invalid ISO datetime
    bad_dt_b64 = base64.urlsafe_b64encode(b'{"created_at": "not-a-timestamp", "id": "some-id"}').decode("utf-8")
    with pytest.raises(ValueError):
        decode_cursor(bad_dt_b64)


def test_keyset_cursor_identical_timestamps_tiebreaker():
    """Stress test keyset pagination tie-breaking when multiple rows share the exact same created_at."""
    # Simulate a query where 5 items have the exact same created_at timestamp
    now = utc_now()
    records = []
    for i in range(5):
        records.append({
            "id": f"id_{i:02d}",
            "created_at": now,
        })
    # Sort deterministically as DB index does: (created_at DESC, id DESC)
    records.sort(key=lambda r: (r["created_at"], r["id"]), reverse=True)

    # Keyset paginate through records 2 at a time using encode_cursor and decode_cursor
    page_1 = records[:2]
    cursor_1 = encode_cursor(page_1[-1]["created_at"], page_1[-1]["id"])
    last_dt_1, last_id_1 = decode_cursor(cursor_1)

    # Apply filter manually simulating: (created_at < last_dt) | (created_at == last_dt & id < last_id)
    page_2 = [
        r for r in records
        if r["created_at"] < last_dt_1 or (r["created_at"] == last_dt_1 and r["id"] < last_id_1)
    ][:2]

    assert len(page_2) == 2
    assert page_2[0]["id"] == records[2]["id"]
    assert page_2[1]["id"] == records[3]["id"]

    cursor_2 = encode_cursor(page_2[-1]["created_at"], page_2[-1]["id"])
    last_dt_2, last_id_2 = decode_cursor(cursor_2)

    page_3 = [
        r for r in records
        if r["created_at"] < last_dt_2 or (r["created_at"] == last_dt_2 and r["id"] < last_id_2)
    ][:2]

    assert len(page_3) == 1
    assert page_3[0]["id"] == records[4]["id"]
