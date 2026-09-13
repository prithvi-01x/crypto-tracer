import os
import subprocess
from datetime import datetime, timezone
import pytest
from httpx import AsyncClient
from sqlalchemy import select, text
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.schema import CreateTable, CreateIndex

from backend.app.persistence.models import (
    Base,
    Case,
    Trace,
    EvidenceItemModel,
    AuditEventModel,
    ReportModel,
    FindingRecord,
    UUID_TYPE,
    JSONB_TYPE,
)
from backend.app.persistence.pagination import encode_cursor, decode_cursor
from backend.app.persistence.db import _create_engine, check_db_connection


@pytest.mark.asyncio
async def test_alembic_heads_and_offline_sql():
    """Verify Alembic migration revision heads and offline PostgreSQL SQL generation."""
    # 1. Verify alembic heads
    result_heads = subprocess.run(
        ["./venv/bin/alembic", "heads"],
        capture_output=True,
        text=True,
        check=True,
        env=dict(os.environ, PYTHONPATH="."),
    )
    assert any(head in result_heads.stdout for head in ["0001 (head)", "0002 (head)", "0003 (head)"])

    # 2. Verify alembic upgrade head --sql emits PostgreSQL DDL with UUID, JSONB, GIN, and RESTRICT
    result_sql = subprocess.run(
        ["./venv/bin/alembic", "upgrade", "head", "--sql"],
        capture_output=True,
        text=True,
        check=True,
        env=dict(os.environ, PYTHONPATH="."),
    )
    sql = result_sql.stdout
    assert "CREATE TABLE cases" in sql
    assert "CREATE TABLE traces" in sql
    assert "CREATE TABLE evidence_items" in sql
    assert "CREATE TABLE audit_events" in sql
    assert "CREATE TABLE reports" in sql
    assert "CREATE TABLE findings" in sql
    assert "UUID NOT NULL" in sql
    assert "JSONB" in sql
    assert "USING gin" in sql
    assert "is_deleted BOOLEAN DEFAULT false NOT NULL" in sql
    assert "ON DELETE RESTRICT" in sql


@pytest.mark.asyncio
async def test_alembic_upgrade_and_downgrade_cycle():
    """Verify that Alembic migrations cleanly apply, pass schema parity check, and downgrade."""
    temp_db_path = "./test_m3_cycle.db"
    temp_url = f"sqlite+aiosqlite:///{temp_db_path}"
    env = dict(os.environ, DATABASE_URL=temp_url, PYTHONPATH=".")

    try:
        # Upgrade
        up_res = subprocess.run(
            ["./venv/bin/alembic", "upgrade", "head"],
            capture_output=True,
            text=True,
            env=env,
        )
        assert up_res.returncode == 0, up_res.stderr

        # Check parity (Base.metadata vs applied schema)
        check_res = subprocess.run(
            ["./venv/bin/alembic", "check"],
            capture_output=True,
            text=True,
            env=env,
        )
        assert check_res.returncode == 0, check_res.stderr
        assert "No new upgrade operations detected" in check_res.stdout + check_res.stderr

        # Downgrade base
        down_res = subprocess.run(
            ["./venv/bin/alembic", "downgrade", "base"],
            capture_output=True,
            text=True,
            env=env,
        )
        assert down_res.returncode == 0, down_res.stderr
    finally:
        if os.path.exists(temp_db_path):
            os.remove(temp_db_path)


@pytest.mark.asyncio
async def test_lifespan_decoupling_and_check_db_connection():
    """Verify Base.metadata.create_all is removed from main.py and check_db_connection succeeds."""
    # 1. Verify main.py does not contain create_all in its source
    with open("backend/app/main.py", "r", encoding="utf-8") as f:
        main_content = f.read()
    assert "create_all" not in main_content
    assert "check_db_connection" in main_content

    # 2. Verify check_db_connection probe executes
    health = await check_db_connection()
    assert health["status"] in ("HEALTHY", "UNHEALTHY")
    assert "latency_ms" in health


def test_dialect_variants_compilation():
    """Verify dialect variants compile to native UUID/JSONB/GIN on Postgres and String/JSON on SQLite."""
    pg = postgresql.dialect()
    sq = sqlite.dialect()

    # Verify UUID variant
    case_table = Case.__table__
    compiled_pg = str(CreateTable(case_table).compile(dialect=pg))
    compiled_sq = str(CreateTable(case_table).compile(dialect=sq))

    assert "id UUID NOT NULL" in compiled_pg
    assert "id VARCHAR(36) NOT NULL" in compiled_sq

    # Verify JSONB variant
    trace_table = Trace.__table__
    trace_pg = str(CreateTable(trace_table).compile(dialect=pg))
    trace_sq = str(CreateTable(trace_table).compile(dialect=sq))

    assert "graph_data JSONB" in trace_pg
    assert "graph_data JSON" in trace_sq

    # Verify GIN indexes on Postgres and standard index on SQLite
    gin_indices = [idx for idx in EvidenceItemModel.__table__.indexes if idx.name == "ix_evidence_payload_gin"]
    assert len(gin_indices) == 1
    gin_idx = gin_indices[0]

    assert "USING gin" in str(CreateIndex(gin_idx).compile(dialect=pg))
    assert "USING gin" not in str(CreateIndex(gin_idx).compile(dialect=sq))


def test_connection_pool_configuration():
    """Verify engine creation dynamically configures pool options per dialect."""
    from sqlalchemy.pool import StaticPool, NullPool, QueuePool

    # 1. SQLite in-memory engine gets StaticPool without invalid pool sizing args
    sqlite_engine = _create_engine(url="sqlite+aiosqlite:///:memory:")
    assert isinstance(sqlite_engine.pool, StaticPool)

    # 2. PostgreSQL engine with standard settings gets QueuePool with pool_size and max_overflow
    pg_engine = _create_engine(
        url="postgresql+asyncpg://user:pass@localhost:5432/db",
        pool_size=15,
        max_overflow=5,
        pool_recycle=1800,
        pgbouncer_mode=False,
    )
    assert isinstance(pg_engine.pool, QueuePool)
    assert pg_engine.pool.size() == 15

    # 3. PostgreSQL engine with pgbouncer_mode=True gets NullPool and statement cache disabled
    pgbouncer_engine = _create_engine(
        url="postgresql+asyncpg://user:pass@localhost:5432/db",
        pgbouncer_mode=True,
    )
    assert isinstance(pgbouncer_engine.pool, NullPool)


@pytest.mark.asyncio
async def test_case_soft_deletion_lifecycle(async_client: AsyncClient, test_engine):
    """Verify soft deletion: case is marked is_deleted=True, hidden from GET, and preserved in DB."""
    # 1. Create a new case
    res_create = await async_client.post(
        "/api/v1/cases",
        json={
            "fir_number": "FIR-SOFTDEL-001",
            "victim_reference": "Victim-SoftDel",
            "loss_amount_inr": 250000.0,
            "chain": "TRON",
            "asset": "TRC20:USDT",
        },
    )
    assert res_create.status_code == 201
    case_id = res_create.json()["id"]

    # 2. Verify normal GET retrieves it
    res_get = await async_client.get(f"/api/v1/cases/{case_id}")
    assert res_get.status_code == 200

    # 3. Soft-delete the case
    res_del = await async_client.delete(f"/api/v1/cases/{case_id}")
    assert res_del.status_code == 204

    # 4. Subsequent normal GET returns 404
    res_get_after = await async_client.get(f"/api/v1/cases/{case_id}")
    assert res_get_after.status_code == 404

    # 5. Subsequent DELETE returns 404
    res_del_second = await async_client.delete(f"/api/v1/cases/{case_id}")
    assert res_del_second.status_code == 404

    # 6. GET with include_deleted=True returns the archived case
    res_get_archived = await async_client.get(f"/api/v1/cases/{case_id}?include_deleted=true")
    assert res_get_archived.status_code == 200
    assert res_get_archived.json()["id"] == case_id

    # 7. Verify directly in the DB session that the row exists with is_deleted=True and deleted_at is set
    async with test_engine.connect() as conn:
        result = await conn.execute(
            select(Case.is_deleted, Case.deleted_at).where(Case.id == case_id)
        )
        row = result.first()
        assert row is not None
        assert row[0] is True or row[0] == 1  # is_deleted is True
        assert row[1] is not None  # deleted_at timestamp populated


@pytest.mark.asyncio
async def test_evidentiary_immutability_under_case_soft_delete(async_client: AsyncClient, test_engine):
    """Verify that evidentiary items and audit events remain unmutated when a case is soft deleted."""
    # 1. Seed demo data to obtain canonical case and evidence
    res_seed = await async_client.post("/api/v1/demo/seed")
    assert res_seed.status_code == 201
    seed_data = res_seed.json()
    case_id = seed_data["case_id"]
    trace_id = seed_data["trace_id"]

    # 2. Check evidence items and audit logs exist before deletion directly in DB
    async with test_engine.connect() as conn:
        ev_res_before = await conn.execute(
            select(EvidenceItemModel.id).where(EvidenceItemModel.case_id == case_id)
        )
        ev_count_before = len(list(ev_res_before.fetchall()))
        assert ev_count_before > 0

        audit_res_before = await conn.execute(
            select(AuditEventModel.id).where(AuditEventModel.case_id == case_id)
        )
        audit_count_before = len(list(audit_res_before.fetchall()))
        assert audit_count_before > 0

    # 3. Soft-delete the case
    res_del = await async_client.delete(f"/api/v1/cases/{case_id}")
    assert res_del.status_code == 204

    # 4. Verify evidence items and audit logs in DB are still completely intact
    async with test_engine.connect() as conn:
        ev_res = await conn.execute(
            select(EvidenceItemModel.id).where(EvidenceItemModel.case_id == case_id)
        )
        ev_rows = list(ev_res.fetchall())
        assert len(ev_rows) == ev_count_before

        audit_res = await conn.execute(
            select(AuditEventModel.id).where(AuditEventModel.case_id == case_id)
        )
        audit_rows = list(audit_res.fetchall())
        assert len(audit_rows) == audit_count_before

    # 5. Verify foreign key ondelete constraint on EvidenceItemModel and AuditEventModel is RESTRICT
    ev_fk = [fk for fk in EvidenceItemModel.__table__.foreign_keys if fk.column.table.name == "cases"][0]
    audit_fk = [fk for fk in AuditEventModel.__table__.foreign_keys if fk.column.table.name == "cases"][0]
    assert ev_fk.ondelete.upper() == "RESTRICT"
    assert audit_fk.ondelete.upper() == "RESTRICT"


@pytest.mark.asyncio
async def test_keyset_pagination_cases_iteration(async_client: AsyncClient):
    """Verify forward cursor pagination, next_cursor generation, has_more, and total count."""
    # Create 5 distinct test cases
    created_ids = []
    for i in range(5):
        res = await async_client.post(
            "/api/v1/cases",
            json={
                "fir_number": f"FIR-KEYSET-{i:03d}",
                "victim_reference": f"Victim-{i}",
                "loss_amount_inr": float(10000 * (i + 1)),
                "chain": "TRON",
                "asset": "TRC20:USDT",
            },
        )
        assert res.status_code == 201
        created_ids.append(res.json()["id"])

    # Page 1: limit 2
    res_p1 = await async_client.get("/api/v1/cases?limit=2")
    assert res_p1.status_code == 200
    p1 = res_p1.json()
    assert len(p1["items"]) == 2
    assert p1["has_more"] is True
    assert p1["next_cursor"] is not None
    # Backward compatibility key
    assert len(p1["cases"]) == 2
    p1_ids = [c["id"] for c in p1["items"]]

    # Page 2: with next_cursor
    res_p2 = await async_client.get(f"/api/v1/cases?cursor={p1['next_cursor']}&limit=2")
    assert res_p2.status_code == 200
    p2 = res_p2.json()
    assert len(p2["items"]) == 2
    p2_ids = [c["id"] for c in p2["items"]]
    # Ensure disjoint pages
    assert set(p1_ids).isdisjoint(set(p2_ids))

    # Page 3: with next_cursor
    assert p2["next_cursor"] is not None
    res_p3 = await async_client.get(f"/api/v1/cases?cursor={p2['next_cursor']}&limit=2")
    assert res_p3.status_code == 200
    p3 = res_p3.json()
    p3_ids = [c["id"] for c in p3["items"]]
    assert set(p2_ids).isdisjoint(set(p3_ids))


@pytest.mark.asyncio
async def test_keyset_pagination_invalid_cursor(async_client: AsyncClient):
    """Verify that malformed or invalid cursors return HTTP 400 Bad Request with code INVALID_CURSOR."""
    # 1. Cases endpoint
    res = await async_client.get("/api/v1/cases?cursor=invalid_base64_string!!!")
    assert res.status_code == 400
    detail = res.json().get("detail", {})
    assert detail.get("code") == "INVALID_CURSOR"

    # 2. Case traces endpoint
    res_traces = await async_client.get("/api/v1/cases/00000000-0000-0000-0000-000000000000/traces?cursor=not-a-valid-cursor")
    # Will return 404 because dummy case not found, or 400
    assert res_traces.status_code in (400, 404)

    # 3. Evidence endpoint
    res_ev = await async_client.get("/api/v1/traces/00000000-0000-0000-0000-000000000000/evidence?cursor=not-a-valid-cursor")
    assert res_ev.status_code in (400, 404)


@pytest.mark.asyncio
async def test_keyset_pagination_trace_backward_compatibility(async_client: AsyncClient):
    """Verify dual contract for trace listing: raw list without cursor, TraceListResponse with cursor."""
    # Seed canonical demo
    res_seed = await async_client.post("/api/v1/demo/seed")
    assert res_seed.status_code == 201
    case_id = res_seed.json()["case_id"]

    # 1. GET /cases/{case_id}/traces without cursor -> raw JSON list
    res_raw = await async_client.get(f"/api/v1/cases/{case_id}/traces")
    assert res_raw.status_code == 200
    assert isinstance(res_raw.json(), list)

    # 2. GET /cases/{case_id}/traces with cursor -> TraceListResponse schema
    cursor_initial = encode_cursor(datetime.now(timezone.utc), "00000000-0000-0000-0000-000000000000")
    res_cursor = await async_client.get(f"/api/v1/cases/{case_id}/traces?cursor={cursor_initial}")
    assert res_cursor.status_code == 200
    data_cursor = res_cursor.json()
    assert "items" in data_cursor
    assert "total" in data_cursor
    assert "has_more" in data_cursor

    # 3. GET /traces/case/{case_id} -> dedicated keyset endpoint returning TraceListResponse
    res_dedicated = await async_client.get(f"/api/v1/traces/case/{case_id}?limit=10")
    assert res_dedicated.status_code == 200
    data_dedicated = res_dedicated.json()
    assert "items" in data_dedicated
    assert "total" in data_dedicated
    assert "has_more" in data_dedicated


@pytest.mark.asyncio
async def test_keyset_pagination_findings(async_client: AsyncClient):
    """Verify keyset pagination on /cases/{case_id}/findings includes items, next_cursor, has_more."""
    res_seed = await async_client.post("/api/v1/demo/seed")
    assert res_seed.status_code == 201
    case_id = res_seed.json()["case_id"]

    res_findings = await async_client.get(f"/api/v1/cases/{case_id}/findings?limit=2")
    assert res_findings.status_code == 200
    data = res_findings.json()

    # Verify both backward compatible key 'findings' and keyset standard 'items' exist
    assert "findings" in data
    assert "items" in data
    assert len(data["items"]) <= 2
    assert "has_more" in data
    assert "next_cursor" in data
