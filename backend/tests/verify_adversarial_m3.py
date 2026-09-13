#!/usr/bin/env python3
"""
Standalone Empirical Verification Script for Milestone 3 (Challenger 1).
Phase 2: Database Hardening & Versioned Migrations.

Executes direct empirical probes:
1. Hard delete prevention via ondelete="RESTRICT" on raw SQL & ORM.
2. Soft deletion lifecycle, court non-disclosure (404), raw SQL row verification, evidence unmutated state, and privileged inspection (200).
3. Keyset pagination 15-case crawl, cursor tampering rejection, and backward compatibility.
"""
import sys
import asyncio
import base64
from datetime import datetime, timezone
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select, text, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from backend.app.main import app
from backend.app.persistence.db import get_db
from backend.app.persistence.models import (
    Base,
    Case,
    Trace,
    EvidenceItemModel,
    AuditEventModel,
)
from backend.app.persistence.pagination import decode_cursor, encode_cursor


async def run_adversarial_verification():
    print("=" * 70)
    print("STARTING EMPIRICAL ADVERSARIAL VERIFICATION SUITE — MILESTONE 3")
    print("=" * 70)

    # --------------------------------------------------------------------------
    # Part 1: Hard-Delete Prevention via RESTRICT (Raw SQL & ORM)
    # --------------------------------------------------------------------------
    print("\n[PROBE 1] Hard-Delete Prevention via ondelete='RESTRICT' (Raw SQL & ORM)...")
    fk_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)

    @event.listens_for(fk_engine.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with fk_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(bind=fk_engine, class_=AsyncSession, expire_on_commit=False)

    # Seed Case, Trace, EvidenceItem, and AuditEvent
    case_id = "test-restrict-case-001"
    async with session_factory() as session:
        case = Case(id=case_id, fir_number="FIR-RESTRICT-001", chain="TRON", asset="TRC20:USDT")
        session.add(case)
        trace = Trace(id="test-trace-001", case_id=case_id, chain="TRON", input_value="TXYZ123456", asset="TRC20:USDT")
        session.add(trace)
        await session.commit()

    async with session_factory() as session:
        ev = EvidenceItemModel(
            id="test-ev-001",
            case_id=case_id,
            trace_id="test-trace-001",
            evidence_type="TRANSFER",
            classification="FORENSIC",
            title="Seized Transfer",
            source="TRON_RPC",
            payload={"txid": "0xabc", "amount": 1000.0},
            content_hash="hash001",
            collected_at=datetime.now(timezone.utc),
            analysis_timestamp=datetime.now(timezone.utc),
        )
        audit = AuditEventModel(
            id="test-audit-001",
            case_id=case_id,
            trace_id="test-trace-001",
            actor_id="officer_1",
            event_type="EVIDENCE_COLLECTED",
            action_summary="Audit summary",
            content_hash="audithash001",
        )
        session.add(ev)
        session.add(audit)
        await session.commit()

    # Attempt Raw SQL Hard Delete
    raw_delete_prevented = False
    async with session_factory() as session:
        try:
            await session.execute(text(f"DELETE FROM cases WHERE id = '{case_id}'"))
            await session.commit()
        except IntegrityError as e:
            raw_delete_prevented = True
            await session.rollback()
            assert "FOREIGN KEY" in str(e) or "foreign key" in str(e).lower()

    assert raw_delete_prevented, "CRITICAL: Raw SQL DELETE FROM cases succeeded despite linked evidence!"
    print("  ✓ Raw SQL DELETE prevented by RESTRICT: IntegrityError raised.")

    # Attempt ORM Hard Delete
    orm_delete_prevented = False
    async with session_factory() as session:
        case_to_del = await session.get(Case, case_id)
        await session.delete(case_to_del)
        try:
            await session.commit()
        except IntegrityError as e:
            orm_delete_prevented = True
            await session.rollback()
            assert "FOREIGN KEY" in str(e) or "foreign key" in str(e).lower()

    assert orm_delete_prevented, "CRITICAL: ORM session.delete(case) succeeded despite linked evidence!"
    print("  ✓ ORM session.delete(case) prevented by RESTRICT & passive_deletes='all'.")

    # Verify that evidence and audit logs are 100% intact
    async with session_factory() as session:
        ev_check = await session.get(EvidenceItemModel, "test-ev-001")
        audit_check = await session.get(AuditEventModel, "test-audit-001")
        assert ev_check is not None and ev_check.payload == {"txid": "0xabc", "amount": 1000.0}
        assert audit_check is not None and audit_check.actor_id == "officer_1"
    print("  ✓ Evidentiary and audit records verified 100% intact and unmutated.")
    await fk_engine.dispose()

    # --------------------------------------------------------------------------
    # Part 2: Soft Deletion Lifecycle, Non-Disclosure & Privileged Inspection
    # --------------------------------------------------------------------------
    print("\n[PROBE 2] Soft Deletion Lifecycle, Non-Disclosure & Privileged Access...")
    test_db_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with test_db_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    api_session_factory = async_sessionmaker(bind=test_db_engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with api_session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Create Case
        res_create = await client.post(
            "/api/v1/cases",
            json={
                "fir_number": "FIR-PROBE2-001",
                "victim_reference": "Victim-Probe2",
                "loss_amount_inr": 500000.0,
                "chain": "TRON",
                "asset": "TRC20:USDT",
            },
        )
        assert res_create.status_code == 201
        case_id = res_create.json()["id"]

        # Insert linked evidence directly in DB
        async with test_db_engine.connect() as conn:
            await conn.execute(
                text("""
                    INSERT INTO evidence_items (
                        id, case_id, tenant_id, district_id, police_station_id,
                        evidence_type, classification, title, description, source,
                        payload, content_hash, engine_version, collected_at, analysis_timestamp, created_at
                    ) VALUES (
                        'ev-probe2-001', :case_id, 'TN-STATE', 'CYBER-CRIME', 'PS-CENTRAL',
                        'TRANSACTION_FLOW', 'FORENSIC', 'Proof', 'Desc', 'TRON',
                        '{"flow": "ok"}', 'hash-probe2', '0.1.0',
                        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                    )
                """),
                {"case_id": case_id},
            )
            await conn.execute(
                text("""
                    INSERT INTO audit_events (
                        id, case_id, tenant_id, district_id, police_station_id,
                        actor_id, event_type, action_summary, content_hash, created_at
                    ) VALUES (
                        'audit-probe2-001', :case_id, 'TN-STATE', 'CYBER-CRIME', 'PS-CENTRAL',
                        'investigator_1', 'CASE_CREATED', 'Created case', 'hash-audit-2', CURRENT_TIMESTAMP
                    )
                """),
                {"case_id": case_id},
            )
            await conn.commit()

        # Perform Soft Delete via API
        res_del = await client.delete(f"/api/v1/cases/{case_id}")
        assert res_del.status_code == 204
        print("  ✓ DELETE /api/v1/cases/{id} returned HTTP 204 No Content.")

        # Non-Disclosure: subsequent GET returns 404
        res_get = await client.get(f"/api/v1/cases/{case_id}")
        assert res_get.status_code == 404
        print("  ✓ Subsequent GET /api/v1/cases/{id} returned HTTP 404 (non-disclosure enforced).")

        # Secondary mutations return 404
        res_patch = await client.patch(f"/api/v1/cases/{case_id}", json={"status": "CLOSED"})
        assert res_patch.status_code == 404
        res_note = await client.post(f"/api/v1/cases/{case_id}/notes", json={"note": "Test note"})
        assert res_note.status_code == 404
        res_del2 = await client.delete(f"/api/v1/cases/{case_id}")
        assert res_del2.status_code == 404
        print("  ✓ Secondary mutation probes (PATCH, note, re-delete) strictly rejected with 404.")

        # Raw SQL verification of is_deleted and deleted_at
        async with test_db_engine.connect() as conn:
            row = (await conn.execute(select(Case.is_deleted, Case.deleted_at).where(Case.id == case_id))).first()
            assert row is not None
            assert row[0] is True or row[0] == 1
            assert row[1] is not None
            # Check evidence count
            ev_count = len((await conn.execute(select(EvidenceItemModel.id).where(EvidenceItemModel.case_id == case_id))).fetchall())
            audit_count = len((await conn.execute(select(AuditEventModel.id).where(AuditEventModel.case_id == case_id))).fetchall())
            assert ev_count == 1
            assert audit_count == 1
        print("  ✓ Raw SQL confirms is_deleted=True, deleted_at populated, evidence/audit records 100% retained.")

        # Privileged inspection returns case
        res_priv = await client.get(f"/api/v1/cases/{case_id}?include_deleted=true")
        assert res_priv.status_code == 200
        assert res_priv.json()["id"] == case_id
        print("  ✓ Privileged inspection GET /api/v1/cases/{id}?include_deleted=true returned HTTP 200.")

        # ----------------------------------------------------------------------
        # Part 3: Keyset Pagination Stress-Test (15 Cases, Limit 3)
        # ----------------------------------------------------------------------
        print("\n[PROBE 3] Keyset Pagination Stress-Test (15 Cases, Limit 3)...")
        inserted_case_ids = []
        for i in range(15):
            res_c = await client.post(
                "/api/v1/cases",
                json={
                    "fir_number": f"FIR-KSTRESS-{i:03d}",
                    "victim_reference": f"Victim-{i}",
                    "loss_amount_inr": float((i + 1) * 20000),
                    "chain": "TRON",
                    "asset": "TRC20:USDT",
                },
            )
            assert res_c.status_code == 201
            inserted_case_ids.append(res_c.json()["id"])

        cursor = None
        collected_cases = []
        page_idx = 0
        while True:
            page_idx += 1
            url = f"/api/v1/cases?limit=3"
            if cursor:
                url += f"&cursor={cursor}"
            res_p = await client.get(url)
            assert res_p.status_code == 200
            data = res_p.json()
            items = data["items"]
            collected_cases.extend(items)
            has_more = data["has_more"]
            cursor = data["next_cursor"]
            if not has_more:
                assert cursor is None
                break

        stress_collected = [c for c in collected_cases if c["id"] in inserted_case_ids]
        assert len(stress_collected) == 15, f"Expected 15 items, collected {len(stress_collected)}"
        collected_ids = [c["id"] for c in stress_collected]
        assert len(collected_ids) == len(set(collected_ids)), "Duplicate case IDs detected across keyset pages!"
        print(f"  ✓ 15 cases collected across {page_idx} pages with zero duplicates.")

        # Check strictly descending timestamps
        for i in range(len(stress_collected) - 1):
            ts1 = datetime.fromisoformat(stress_collected[i]["created_at"].replace("Z", "+00:00"))
            ts2 = datetime.fromisoformat(stress_collected[i + 1]["created_at"].replace("Z", "+00:00"))
            if ts1 == ts2:
                assert stress_collected[i]["id"] > stress_collected[i + 1]["id"]
            else:
                assert ts1 > ts2
        print("  ✓ Keyset order strictly descending across created_at timestamps with ID tie-breaker.")

        # ----------------------------------------------------------------------
        # Part 4: Cursor Tampering Rejection
        # ----------------------------------------------------------------------
        print("\n[PROBE 4] Cursor Tampering Rejection...")
        tampered_samples = [
            "invalid_base64_string!!!",
            base64.urlsafe_b64encode(b"no_pipe_separator").decode("ascii"),
            base64.urlsafe_b64encode(b"not-a-valid-timestamp|case-uuid-1234").decode("ascii"),
            base64.urlsafe_b64encode(b"2026-13-45T99:99:99|case-uuid-1234").decode("ascii"),
            base64.urlsafe_b64encode(b"|case-uuid-1234").decode("ascii"),
        ]
        for bad_cursor in tampered_samples:
            res_bad = await client.get(f"/api/v1/cases?cursor={bad_cursor}")
            assert res_bad.status_code == 400
            assert res_bad.json()["detail"]["code"] == "INVALID_CURSOR"
        print("  ✓ All corrupted/tampered Base64 cursors strictly rejected with 400 INVALID_CURSOR.")

        # ----------------------------------------------------------------------
        # Part 5: Backward Compatibility
        # ----------------------------------------------------------------------
        print("\n[PROBE 5] Backward Compatibility (Without Cursor)...")
        res_compat = await client.get("/api/v1/cases?limit=5")
        assert res_compat.status_code == 200
        compat_body = res_compat.json()
        assert "cases" in compat_body and "items" in compat_body
        assert compat_body["cases"] == compat_body["items"]
        assert "total" in compat_body and "has_more" in compat_body
        print("  ✓ Legacy return shape preserved: 'cases' and 'items' populated with identical items.")

    app.dependency_overrides.clear()
    await test_db_engine.dispose()

    print("\n" + "=" * 70)
    print("ALL EMPIRICAL ADVERSARIAL VERIFICATIONS PASSED SUCCESSFULLY (100%)")
    print("=" * 70)
    return True


if __name__ == "__main__":
    success = asyncio.run(run_adversarial_verification())
    sys.exit(0 if success else 1)
