import os
import uuid
import time
import tempfile
import hashlib
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from backend.app.persistence.models import Case, Trace, ReportModel
from backend.app.domain.models import InvestigationGraph, GraphNode, GraphEdge
from backend.app.domain.attribution.models import AttributionReport, VASPCandidate, FactorScores, FactorExplanations
from backend.app.domain.evidence.models import EvidenceItem, EvidenceType, EvidenceClassification
from backend.app.domain.evidence.hasher import compute_genesis_hash, compute_chain_hash
from backend.app.persistence.evidence_repository import EvidenceRepository
from backend.app.domain.reports.bsa63_generator import Section63BSAGenerator
from backend.app.services.storage import (
    MemoryStorageProvider,
    LocalStorageProvider,
    get_storage_service,
)
from backend.app.worker.queue import get_report_queue
from backend.app.worker.fleet import ReportWorker
from backend.app.core.auth import create_access_token, Role


@pytest.mark.asyncio
async def test_bsa63_pdf_generator_statutory_admissibility():
    """
    Verify Section 63 BSA certificate generator:
    - Produces valid PDF document adhering to Section 63(4) Bharatiya Sakshya Adhiniyam, 2023.
    - Includes Schedule Part A (device particulars and SHA-256 evidence item hash anchors).
    - Includes Schedule Part B (statutory declaration of lawful control and computer integrity).
    - Strict wording guardrails: no 'conclusive attribution', proper electronic evidence terminology.
    """
    case_id = str(uuid.uuid4())
    trace_id = str(uuid.uuid4())
    genesis = compute_genesis_hash(case_id)
    now = datetime.now(timezone.utc)

    case = Case(
        id=case_id,
        fir_number="FIR/2026/BSA/101",
        tenant_id="TN-STATE",
        district_id="CHENNAI",
        police_station_id="PS-CENTRAL",
        victim_reference="S. Ramachandran",
        loss_amount_inr=Decimal("750000.00"),
        suspect_wallet="TSuspectBsa63Wallet1111111111111",
        chain="TRON",
        asset="TRC20:USDT",
        status="INVESTIGATING",
    )
    trace = Trace(
        id=trace_id,
        case_id=case_id,
        chain="TRON",
        input_value="TSuspectBsa63Wallet1111111111111",
        asset="TRC20:USDT",
    )

    h1 = compute_chain_hash(
        prev_hash=genesis,
        canonical_payload='{"amount":50000.0,"tx":"tx1"}',
        timestamp=now,
        actor_id="IO-Vikram",
    )
    ev_item1 = EvidenceItem(
        id="ev_bsa_001",
        case_id=case_id,
        trace_id=trace_id,
        evidence_type=EvidenceType.TRANSACTION_RECORD,
        classification=EvidenceClassification.OBSERVED,
        title="Observed TRC20 USDT Transfer",
        source="trongrid",
        source_reference="tx1",
        payload={"amount": 50000.0, "tx": "tx1"},
        content_hash=h1,
        collected_at=now,
    )

    pdf_bytes, report_hash, meta = Section63BSAGenerator.generate_pdf(
        case=case,
        trace=trace,
        evidence_items=[ev_item1],
        investigator_name="Inspector V. Raman",
        investigator_rank="Inspector of Police",
        police_station="Cyber Crime Police Station, Central District",
        technical_examiner="Dr. S. Mukherjee, Forensic Scientist",
        notes="Certificate prepared for judicial submission under Section 63(4) BSA 2023.",
    )

    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 5000
    assert pdf_bytes.startswith(b"%PDF-")
    assert len(report_hash) == 64
    assert meta["statutory_section"] == "Section 63(4)"
    assert meta["evidence_count"] == 1
    assert meta["genesis_hash"] == genesis

    pdf_text = pdf_bytes.decode("latin1", errors="ignore")
    # Verify statutory headings and legal terminology
    assert "Section 63" in pdf_text or "SECTION 63" in pdf_text
    assert "Part A" in pdf_text or "PART A" in pdf_text
    assert "Part B" in pdf_text or "PART B" in pdf_text
    assert "Bharatiya Sakshya Adhiniyam" in pdf_text or "BSA" in pdf_text
    assert "lawful control" in pdf_text.lower()
    # Guardrail check
    assert "conclusive attribution" not in pdf_text.lower()


@pytest.mark.asyncio
async def test_memory_storage_provider():
    """Verify MemoryStorageProvider CRUD and integrity checking."""
    provider = MemoryStorageProvider()
    key = "reports/TN-STATE/case-101/dossier.pdf"
    content = b"%PDF-1.4 test document content for memory storage"

    # Put
    stored = await provider.put_object(key=key, data=content, content_type="application/pdf")
    assert stored.key == key
    assert stored.size_bytes == len(content)
    assert stored.content_hash == hashlib.sha256(content).hexdigest()
    assert await provider.exists(key) is True

    # Get
    retrieved_bytes, doc = await provider.get_object(key)
    assert retrieved_bytes == content
    assert doc.content_hash == stored.content_hash

    # Delete
    deleted = await provider.delete_object(key)
    assert deleted is True
    assert await provider.exists(key) is False


@pytest.mark.asyncio
async def test_local_storage_provider_encryption_and_path_traversal():
    """
    Verify LocalStorageProvider:
    - Encrypts files at rest with AES-256-GCM.
    - Decrypts on retrieve, verifying content integrity.
    - Detects and strictly prevents path traversal attempts (e.g. '../').
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        provider = LocalStorageProvider(base_dir=tmpdir, encrypt_at_rest=True)
        key = "vault/case-202/evidence_certificate.pdf"
        plaintext = b"%PDF-1.4 statutory certificate secret content"

        # 1. Put object
        stored = await provider.put_object(key=key, data=plaintext)
        assert stored.key == key
        assert stored.size_bytes == len(plaintext)
        assert stored.encryption_mode == "client-aes-gcm"

        # Verify on-disk ciphertext does NOT equal plaintext
        disk_path = provider._resolve_path(key)
        assert os.path.exists(disk_path)
        with open(disk_path, "rb") as f:
            on_disk_bytes = f.read()
        assert on_disk_bytes != plaintext
        # AES-GCM adds nonce (12 bytes) and tag (16 bytes)
        assert len(on_disk_bytes) >= len(plaintext) + 12 + 16

        # 2. Get object decrypts to plaintext
        retrieved_data, meta = await provider.get_object(key)
        assert retrieved_data == plaintext
        assert meta.content_hash == stored.content_hash

        # 3. Path traversal attacks are rejected
        with pytest.raises(ValueError, match="Path traversal detected"):
            await provider.put_object(key="../../etc/passwd", data=b"evil")

        with pytest.raises(ValueError, match="Path traversal detected"):
            await provider.get_object(key="../../../root/secret.key")


@pytest.mark.asyncio
async def test_sync_and_async_report_compilation_lifecycle(test_engine, async_client: AsyncClient):
    """
    Test dual-mode sync and async statutory report compilation:
    1. Sync mode (?sync=true) returns 201 Created immediately with report payload.
    2. Async mode (?sync=false) returns 202 Accepted with job_id and poll URL.
    3. Worker executes background compilation job.
    4. Job polling endpoint returns 200 OK with COMPLETED status.
    5. Download endpoint streams completed PDF document.
    """
    session_factory = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    case_id = str(uuid.uuid4())
    trace_id = str(uuid.uuid4())
    suspect = "TSuspectSyncAsync111111111111111111"
    deposit = "TDepositSyncAsync22222222222222222"
    now = datetime.now(timezone.utc)

    graph_data = {
        "nodes": [
            {"id": suspect, "address": suspect, "chain": "TRON", "node_type": "suspect", "hop": 0, "total_received": "0", "total_sent": "5000", "transaction_count": 1},
            {"id": deposit, "address": deposit, "chain": "TRON", "node_type": "intermediate", "hop": 1, "total_received": "5000", "total_sent": "0", "transaction_count": 1},
        ],
        "edges": [
            {"id": "e1", "tx_hash": "tx_rep_async_1", "from_address": suspect, "to_address": deposit, "amount": "5000.00", "amount_raw": 5000000000, "asset": "TRC20:USDT", "timestamp": now.isoformat(), "hop": 1, "source": "trongrid", "relevance_score": "1.0", "pruned": False},
        ],
        "pruned_records": [],
        "meta": {"root_address": suspect, "max_hops": 1},
    }

    async with session_factory() as session:
        case = Case(
            id=case_id,
            fir_number="FIR/2026/TN/999",
            tenant_id="TN-STATE",
            district_id="CHENNAI",
            police_station_id="PS-CENTRAL",
            victim_reference="K. Natarajan",
            loss_amount_inr=Decimal("500000.00"),
            suspect_wallet=suspect,
            chain="TRON",
            asset="TRC20:USDT",
            status="INVESTIGATING",
        )
        trace = Trace(
            id=trace_id,
            case_id=case_id,
            chain="TRON",
            input_type="address",
            input_value=suspect,
            asset="USDT",
            status="completed",
            node_count=2,
            edge_count=1,
            graph_data=graph_data,
        )
        session.add(case)
        session.add(trace)
        await session.commit()

    token_io_tn = create_access_token({
        "sub": "IO-TN-01",
        "role": Role.INVESTIGATING_OFFICER.value,
        "tenant_id": "TN-STATE",
        "district_id": "CHENNAI",
        "police_station_id": "PS-CENTRAL",
    })

    # 1. Sync compilation test: POST /cases/{case_id}/reports/bsa63?sync=true
    sync_res = await async_client.post(
        f"/api/v1/cases/{case_id}/reports/bsa63?sync=true",
        json={
            "trace_id": trace_id,
            "investigator_name": "IO-Natarajan",
            "investigator_rank": "Inspector of Police",
            "police_station": "Cyber Crime PS Chennai",
            "technical_examiner": "Forensic Unit",
            "notes": "Sync test certificate",
        },
        headers={"Authorization": f"Bearer {token_io_tn}"},
    )
    assert sync_res.status_code == 201
    sync_data = sync_res.json()
    assert sync_data["report_type"] == "SECTION_63_BSA"
    assert sync_data["case_id"] == case_id
    assert len(sync_data["content_hash"]) == 64
    sync_report_id = sync_data["id"]

    # Download sync report
    sync_dl = await async_client.get(
        f"/api/v1/reports/{sync_report_id}/download",
        headers={"Authorization": f"Bearer {token_io_tn}"},
    )
    assert sync_dl.status_code == 200
    assert sync_dl.headers["content-type"] == "application/pdf"
    assert sync_dl.content.startswith(b"%PDF-")

    # 2. Async compilation test: POST /cases/{case_id}/reports/bsa63?sync=false
    async_res = await async_client.post(
        f"/api/v1/cases/{case_id}/reports/bsa63?sync=false",
        json={
            "trace_id": trace_id,
            "investigator_name": "IO-Natarajan",
            "investigator_rank": "Inspector of Police",
            "police_station": "Cyber Crime PS Chennai",
            "technical_examiner": "Forensic Unit",
            "notes": "Async test certificate",
        },
        headers={"Authorization": f"Bearer {token_io_tn}"},
    )
    assert async_res.status_code == 202
    async_data = async_res.json()
    assert async_data["status"] in ("QUEUED", "PENDING")
    job_id = async_data["job_id"]
    async_report_id = async_data["report_id"]
    assert job_id is not None
    assert async_data["poll_url"] == f"/api/v1/reports/jobs/{job_id}"

    # Poll status before worker processes: should be QUEUED or PENDING
    poll_initial = await async_client.get(
        f"/api/v1/reports/jobs/{job_id}",
        headers={"Authorization": f"Bearer {token_io_tn}"},
    )
    assert poll_initial.status_code == 200
    assert poll_initial.json()["status"] in ("QUEUED", "PENDING", "PROCESSING")

    # 3. Background worker executes job
    queue = get_report_queue(None)
    job_payload = await queue.pop(timeout_seconds=0.5)
    assert job_payload is not None
    assert job_payload.job_id == job_id

    worker = ReportWorker(db_session_factory=session_factory, queue=queue)
    await worker.process_job(job_payload)

    # 4. Poll status after worker processes: should be COMPLETED
    poll_completed = await async_client.get(
        f"/api/v1/reports/jobs/{job_id}",
        headers={"Authorization": f"Bearer {token_io_tn}"},
    )
    assert poll_completed.status_code == 200
    completed_data = poll_completed.json()
    assert completed_data["status"] == "COMPLETED"
    assert completed_data["report_id"] == async_report_id
    assert completed_data["error_message"] is None

    # 5. Download compiled async report
    async_dl = await async_client.get(
        f"/api/v1/reports/{async_report_id}/download",
        headers={"Authorization": f"Bearer {token_io_tn}"},
    )
    assert async_dl.status_code == 200
    assert async_dl.headers["content-type"] == "application/pdf"
    assert async_dl.content.startswith(b"%PDF-")


@pytest.mark.asyncio
async def test_presigned_url_issuance_and_download(test_engine, async_client: AsyncClient):
    """
    Test authenticated pre-signed URL workflow:
    - Issue pre-signed download URL for a completed report.
    - Download PDF without Authorization header using pre-signed token -> 200 OK.
    - Tampered token -> 403 Forbidden (INVALID_TOKEN).
    - Expired token -> 403 Forbidden (EXPIRED_TOKEN).
    """
    session_factory = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    case_id = str(uuid.uuid4())
    report_id = str(uuid.uuid4())
    pdf_content = b"%PDF-1.4 Presigned URL test certificate content bytes"
    pdf_hash = hashlib.sha256(pdf_content).hexdigest()

    # Put object into storage vault
    storage = get_storage_service()
    stored_doc = await storage.put_object(
        key=f"reports/TN-STATE/{case_id}/test_rep_{report_id[:8]}.pdf",
        data=pdf_content,
        content_type="application/pdf",
    )

    async with session_factory() as session:
        case = Case(
            id=case_id,
            fir_number="FIR/2026/TN/777",
            tenant_id="TN-STATE",
            district_id="CHENNAI",
            police_station_id="PS-CENTRAL",
            victim_reference="M. Sundaram",
            loss_amount_inr=Decimal("150000.00"),
            status="INVESTIGATING",
        )
        report = ReportModel(
            id=report_id,
            case_id=case_id,
            tenant_id="TN-STATE",
            district_id="CHENNAI",
            police_station_id="PS-CENTRAL",
            report_type="SECTION_63_BSA",
            title="Section 63 BSA Certificate",
            file_path=stored_doc.key,
            storage_path=stored_doc.key,
            file_size_bytes=len(pdf_content),
            content_hash=pdf_hash,
            file_hash=pdf_hash,
            status="COMPLETED",
            storage_backend="LOCAL",
        )
        session.add(case)
        session.add(report)
        await session.commit()

    token_io_tn = create_access_token({
        "sub": "IO-TN-01",
        "role": Role.INVESTIGATING_OFFICER.value,
        "tenant_id": "TN-STATE",
        "district_id": "CHENNAI",
        "police_station_id": "PS-CENTRAL",
    })

    # 1. Issue pre-signed URL
    presigned_res = await async_client.post(
        f"/api/v1/reports/{report_id}/presigned-url",
        json={"expires_in_seconds": 1800},
        headers={"Authorization": f"Bearer {token_io_tn}"},
    )
    assert presigned_res.status_code == 200
    presigned_data = presigned_res.json()
    assert presigned_data["report_id"] == report_id
    assert presigned_data["expires_in_seconds"] == 1800
    download_url = presigned_data["download_url"]
    assert "token=" in download_url
    assert "expires=" in download_url

    # 2. Download via pre-signed URL WITHOUT Authorization header
    dl_res = await async_client.get(download_url)
    assert dl_res.status_code == 200
    assert dl_res.headers["content-type"] == "application/pdf"
    assert dl_res.content == pdf_content

    # 3. Tampered token rejected with 403
    tampered_url = download_url.replace("token=", "token=tampered_sig_")
    tampered_res = await async_client.get(tampered_url)
    assert tampered_res.status_code == 403
    assert tampered_res.json()["detail"]["code"] == "INVALID_TOKEN"

    # 4. Expired token rejected with 403
    past_timestamp = int(time.time()) - 3600
    expired_url = download_url.split("expires=")[0] + f"expires={past_timestamp}"
    expired_res = await async_client.get(expired_url)
    assert expired_res.status_code == 403
    assert expired_res.json()["detail"]["code"] == "EXPIRED_TOKEN"


@pytest.mark.asyncio
async def test_statutory_reports_rbac_and_multitenant_idor(test_engine, async_client: AsyncClient):
    """
    Test multi-tenant isolation and 4-role RBAC for statutory reports:
    - DL officer (tenant DL-STATE) cannot create report for TN-STATE case -> 404.
    - DL officer cannot request pre-signed URL for TN-STATE report -> 404.
    - DL officer cannot download TN-STATE report via Bearer token -> 404.
    - Auditor role can verify and download reports.
    """
    session_factory = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    case_id = str(uuid.uuid4())
    report_id = str(uuid.uuid4())
    pdf_content = b"%PDF-1.4 Multitenant test report bytes"

    storage = get_storage_service()
    stored_doc = await storage.put_object(
        key=f"reports/TN-STATE/{case_id}/rep_{report_id[:8]}.pdf",
        data=pdf_content,
        content_type="application/pdf",
    )

    async with session_factory() as session:
        case = Case(
            id=case_id,
            fir_number="FIR/2026/TN/333",
            tenant_id="TN-STATE",
            district_id="CHENNAI",
            police_station_id="PS-CENTRAL",
            victim_reference="A. Selvam",
            loss_amount_inr=Decimal("300000.00"),
            status="INVESTIGATING",
        )
        report = ReportModel(
            id=report_id,
            case_id=case_id,
            tenant_id="TN-STATE",
            district_id="CHENNAI",
            police_station_id="PS-CENTRAL",
            report_type="SECTION_63_BSA",
            title="Section 63 BSA Certificate",
            file_path=stored_doc.key,
            storage_path=stored_doc.key,
            file_size_bytes=len(pdf_content),
            content_hash=hashlib.sha256(pdf_content).hexdigest(),
            file_hash=hashlib.sha256(pdf_content).hexdigest(),
            status="COMPLETED",
            storage_backend="LOCAL",
        )
        session.add(case)
        session.add(report)
        await session.commit()

    # Tenant Tokens
    token_dl_officer = create_access_token({
        "sub": "IO-DL-05",
        "role": Role.INVESTIGATING_OFFICER.value,
        "tenant_id": "DL-STATE",  # Adversary tenant
        "district_id": "DELHI-HQ",
        "police_station_id": "PS-NORTH",
    })
    token_tn_auditor = create_access_token({
        "sub": "AUD-TN-01",
        "role": Role.AUDITOR.value,
        "tenant_id": "TN-STATE",
        "district_id": "CHENNAI",
        "police_station_id": "PS-CENTRAL",
    })

    # 1. Cross-tenant report generation rejected with 404
    cross_gen = await async_client.post(
        f"/api/v1/cases/{case_id}/reports/bsa63?sync=true",
        json={
            "trace_id": str(uuid.uuid4()),
            "investigator_name": "IO-Hacker",
            "investigator_rank": "Inspector",
            "police_station": "PS-NORTH",
        },
        headers={"Authorization": f"Bearer {token_dl_officer}"},
    )
    assert cross_gen.status_code == 404

    # 2. Cross-tenant presigned-url request rejected with 404
    cross_url = await async_client.post(
        f"/api/v1/reports/{report_id}/presigned-url",
        json={"expires_in_seconds": 1800},
        headers={"Authorization": f"Bearer {token_dl_officer}"},
    )
    assert cross_url.status_code == 404

    # 3. Cross-tenant direct download rejected with 404
    cross_dl = await async_client.get(
        f"/api/v1/reports/{report_id}/download",
        headers={"Authorization": f"Bearer {token_dl_officer}"},
    )
    assert cross_dl.status_code == 404

    # 4. Legitimate tenant Auditor can generate pre-signed URL and download
    auditor_url = await async_client.post(
        f"/api/v1/reports/{report_id}/presigned-url",
        json={"expires_in_seconds": 1800},
        headers={"Authorization": f"Bearer {token_tn_auditor}"},
    )
    assert auditor_url.status_code == 200

    auditor_dl = await async_client.get(
        f"/api/v1/reports/{report_id}/download",
        headers={"Authorization": f"Bearer {token_tn_auditor}"},
    )
    assert auditor_dl.status_code == 200
    assert auditor_dl.content == pdf_content
