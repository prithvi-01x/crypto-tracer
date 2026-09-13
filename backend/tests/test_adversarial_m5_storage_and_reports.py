"""
Adversarial Test Suite for Milestone 5 (Features 32 & 33):
Empirical Challenger: teamwork_preview_challenger_m5_2

Coverage of Aggressive Failure Injection Scenarios:
1. Path traversal attacks on storage keys (e.g. ../../../etc/passwd, /etc/shadow, null bytes %00).
2. Pre-signed download URL tampering: modifying signature, modifying expiration, tampering with report ID or tenant ID.
3. Expired pre-signed URL tests: requesting with timestamp in the past.
4. IDOR attacks on pre-signed URLs and reports: Tenant B attempting to access Tenant A's reports.
5. Ciphertext corruption attacks: Modifying bytes of stored encrypted PDF binary (AEAD tag mismatch defense).
6. Async worker error resilience: Queue processing failure updates report status to FAILED with descriptive error.
7. Section 63 BSA & Section 94 BNSS statutory content assertions and legal guardrails.
"""
import os
import re
import zlib
import time
import uuid
import hmac
import hashlib
import tempfile
from decimal import Decimal
from datetime import datetime, timezone, timedelta
from typing import Optional, List

import pytest
from httpx import AsyncClient
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from backend.app.config import settings
from backend.app.core.crypto import get_encryption_key, NONCE_LENGTH_BYTES
from backend.app.core.auth import create_access_token, Role
from backend.app.persistence.models import Case, Trace, ReportModel, EvidenceItemModel
from backend.app.services.storage import (
    LocalStorageProvider,
    MemoryStorageProvider,
    get_storage_service,
    StoredDocument,
)
from backend.app.worker.queue import (
    InMemoryReportQueue,
    ReportJobPayload,
    get_report_queue,
)
from backend.app.worker.fleet import ReportWorker
from backend.app.domain.reports.bsa63_generator import Section63BSAGenerator
from backend.app.domain.reports.bnss94_generator import BNSS94DraftGenerator
from backend.app.domain.evidence.hasher import compute_genesis_hash, compute_chain_hash
from backend.app.domain.evidence.models import EvidenceItem, EvidenceType, EvidenceClassification
from backend.app.api.v1.endpoints.reports import _ensure_report_dir


def extract_pdf_text_streams(pdf_bytes: bytes) -> str:
    """Decompress and extract all text streams from raw PDF bytes."""
    streams = re.findall(rb"stream[\r\n]+(.*?)[\r\n]+endstream", pdf_bytes, re.DOTALL)
    combined = pdf_bytes.decode("latin1", errors="ignore")
    for s in streams:
        try:
            decompressed = zlib.decompress(s).decode("latin1", errors="ignore")
            combined += " " + decompressed
        except Exception:
            pass
    return combined


# ==============================================================================
# 1. PATH TRAVERSAL ATTACKS ON STORAGE KEYS
# ==============================================================================

@pytest.mark.asyncio
async def test_storage_vault_path_traversal_rejection_put_and_get():
    """
    Adversarial Challenge:
    Inject path traversal sequences (../../etc/passwd, ../../../etc/passwd, ../../../../etc/shadow)
    into LocalStorageProvider put_object and get_object calls.
    Must strictly raise ValueError with 'Path traversal detected' and prevent vault escaping.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        provider = LocalStorageProvider(base_dir=tmpdir, encrypt_at_rest=True)
        traversal_payloads = [
            "../../etc/passwd",
            "../../../etc/passwd",
            "../../../../etc/shadow",
            "safe_dir/../../../../etc/shadow",
            "vault/sub/../../../../../../etc/passwd",
        ]

        for hostile_key in traversal_payloads:
            # 1. Attack put_object
            with pytest.raises(ValueError, match="Path traversal detected"):
                await provider.put_object(key=hostile_key, data=b"malicious_overwrite_attempt")

            # 2. Attack get_object
            with pytest.raises(ValueError, match="Path traversal detected"):
                await provider.get_object(key=hostile_key)

            # 3. Attack exists check
            with pytest.raises(ValueError, match="Path traversal detected"):
                await provider.exists(key=hostile_key)

            # 4. Attack delete_object
            with pytest.raises(ValueError, match="Path traversal detected"):
                await provider.delete_object(key=hostile_key)


@pytest.mark.asyncio
async def test_storage_vault_null_byte_injection_rejection():
    """
    Adversarial Challenge:
    Inject embedded null bytes (%00, \\x00) into storage keys to poison filenames
    or truncate paths into arbitrary files. Must be rejected.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        provider = LocalStorageProvider(base_dir=tmpdir, encrypt_at_rest=True)
        null_byte_keys = [
            "test\x00file.pdf",
            "reports/sub\x00/test.pdf",
        ]

        for k in null_byte_keys:
            with pytest.raises(ValueError):
                await provider.put_object(key=k, data=b"null_byte_test")


@pytest.mark.asyncio
async def test_download_endpoint_local_file_path_traversal_rejection(test_engine, async_client: AsyncClient):
    """
    Adversarial Challenge:
    Simulate a compromised report record in the database where an attacker manipulated
    file_path to reference sensitive system files (/etc/passwd, /etc/shadow) or outside the vault.
    GET /api/v1/reports/{report_id}/download MUST intercept the path traversal and return 403 Forbidden.
    """
    session_factory = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    report_id = str(uuid.uuid4())
    case_id = str(uuid.uuid4())

    async with session_factory() as session:
        case = Case(
            id=case_id,
            fir_number="FIR/2026/TN/TRAVERSAL",
            tenant_id="TN-STATE",
            district_id="CHENNAI",
            police_station_id="PS-CENTRAL",
            status="INVESTIGATING",
        )
        # Malicious report pointing to /etc/passwd outside the allowed REPORTS_DIR
        report = ReportModel(
            id=report_id,
            case_id=case_id,
            tenant_id="TN-STATE",
            district_id="CHENNAI",
            police_station_id="PS-CENTRAL",
            report_type="SECTION_63_BSA",
            title="Malicious Traversal Report",
            file_path="/etc/passwd",  # Hostile file path traversal attempt pointing to existing host file
            storage_path=None,
            s3_key=None,
            file_size_bytes=100,
            content_hash="mock_hash_traversal",
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

    response = await async_client.get(
        f"/api/v1/reports/{report_id}/download",
        headers={"Authorization": f"Bearer {token_io_tn}"},
    )
    # Must be strictly rejected with HTTP 403 Forbidden
    assert response.status_code == 403
    data = response.json()
    assert data["detail"]["code"] == "FORBIDDEN"


def test_ensure_report_dir_traversal_rejection():
    """
    Adversarial Challenge:
    Inject path traversal into _ensure_report_dir(case_id) with hostile relative/absolute paths.
    """
    safe_dir = _ensure_report_dir("case-12345-valid")
    assert os.path.exists(safe_dir)

    # Relative path characters like '/' and '.' are stripped by safe_case_id sanitize
    escaped_dir = _ensure_report_dir("../../../etc/shadow")
    assert not escaped_dir.endswith("/etc/shadow")
    assert escaped_dir.startswith(os.path.abspath(settings.REPORTS_DIR))


# ==============================================================================
# 2. PRE-SIGNED DOWNLOAD URL TAMPERING DEFENSE
# ==============================================================================

@pytest.mark.asyncio
async def test_presigned_url_tampered_signature_rejection(test_engine, async_client: AsyncClient):
    """
    Adversarial Challenge:
    Generate a valid pre-signed URL, then tamper with the HMAC-SHA256 signature token.
    Must strictly return HTTP 403 Forbidden (INVALID_TOKEN).
    """
    session_factory = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    report_id = str(uuid.uuid4())
    case_id = str(uuid.uuid4())
    pdf_data = b"%PDF-1.4 Presigned Tamper Test Content"

    storage = get_storage_service()
    stored_doc = await storage.put_object(
        key=f"reports/TN-STATE/{case_id}/rep_{report_id[:8]}.pdf",
        data=pdf_data,
    )

    async with session_factory() as session:
        case = Case(
            id=case_id,
            fir_number="FIR/2026/TN/TAMPER",
            tenant_id="TN-STATE",
            district_id="CHENNAI",
            police_station_id="PS-CENTRAL",
            status="INVESTIGATING",
        )
        report = ReportModel(
            id=report_id,
            case_id=case_id,
            tenant_id="TN-STATE",
            district_id="CHENNAI",
            police_station_id="PS-CENTRAL",
            report_type="SECTION_63_BSA",
            title="Presigned Tamper Test",
            file_path=stored_doc.key,
            storage_path=stored_doc.key,
            file_size_bytes=len(pdf_data),
            content_hash=hashlib.sha256(pdf_data).hexdigest(),
            file_hash=hashlib.sha256(pdf_data).hexdigest(),
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

    # Issue valid pre-signed URL
    url_res = await async_client.post(
        f"/api/v1/reports/{report_id}/presigned-url",
        json={"expires_in_seconds": 900},
        headers={"Authorization": f"Bearer {token_io_tn}"},
    )
    assert url_res.status_code == 200
    valid_url = url_res.json()["download_url"]

    # 1. Flip bytes in signature token
    tampered_sig_url = re.sub(r"token=[0-9a-fA-F]+", "token=deadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef", valid_url)
    res_tampered_sig = await async_client.get(tampered_sig_url)
    assert res_tampered_sig.status_code == 403
    assert res_tampered_sig.json()["detail"]["code"] == "INVALID_TOKEN"

    # 2. Corrupt one character in signature
    corrupted_char_url = valid_url.replace("token=", "token=a")
    res_corrupted_char = await async_client.get(corrupted_char_url)
    assert res_corrupted_char.status_code == 403
    assert res_corrupted_char.json()["detail"]["code"] == "INVALID_TOKEN"


@pytest.mark.asyncio
async def test_presigned_url_tampered_expiration_rejection(test_engine, async_client: AsyncClient):
    """
    Adversarial Challenge:
    Attacker captures a valid pre-signed URL and attempts to extend its validity window
    into the future by tampering with the expires query parameter.
    HMAC signature must detect the parameter modification and return 403 Forbidden.
    """
    session_factory = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    report_id = str(uuid.uuid4())
    case_id = str(uuid.uuid4())
    pdf_data = b"%PDF-1.4 Presigned Expiration Tamper Test"

    storage = get_storage_service()
    stored_doc = await storage.put_object(
        key=f"reports/TN-STATE/{case_id}/rep_{report_id[:8]}.pdf",
        data=pdf_data,
    )

    async with session_factory() as session:
        case = Case(
            id=case_id,
            fir_number="FIR/2026/TN/EXP-TAMPER",
            tenant_id="TN-STATE",
            district_id="CHENNAI",
            police_station_id="PS-CENTRAL",
            status="INVESTIGATING",
        )
        report = ReportModel(
            id=report_id,
            case_id=case_id,
            tenant_id="TN-STATE",
            district_id="CHENNAI",
            police_station_id="PS-CENTRAL",
            report_type="SECTION_63_BSA",
            title="Presigned Expiration Tamper",
            file_path=stored_doc.key,
            storage_path=stored_doc.key,
            file_size_bytes=len(pdf_data),
            content_hash=hashlib.sha256(pdf_data).hexdigest(),
            file_hash=hashlib.sha256(pdf_data).hexdigest(),
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

    url_res = await async_client.post(
        f"/api/v1/reports/{report_id}/presigned-url",
        json={"expires_in_seconds": 600},
        headers={"Authorization": f"Bearer {token_io_tn}"},
    )
    valid_url = url_res.json()["download_url"]

    # Extract current expires and tamper by adding 7200 seconds
    m = re.search(r"expires=(\d+)", valid_url)
    assert m is not None
    orig_exp = int(m.group(1))
    tampered_exp = orig_exp + 7200

    tampered_exp_url = valid_url.replace(f"expires={orig_exp}", f"expires={tampered_exp}")
    res = await async_client.get(tampered_exp_url)
    assert res.status_code == 403
    assert res.json()["detail"]["code"] == "INVALID_TOKEN"


@pytest.mark.asyncio
async def test_presigned_url_tampered_report_id_and_tenant_rejection(test_engine, async_client: AsyncClient):
    """
    Adversarial Challenge:
    1. Attacker takes a valid pre-signed URL for Report A and substitutes Report B's ID in the path.
       Token signature must fail validation -> 403 Forbidden.
    2. Attacker modifies the tenant parameter to an unauthorized tenant.
       Tenant boundary lookup fails -> 404 Not Found (anti-enumeration) or 403 Forbidden.
    """
    session_factory = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    case_id = str(uuid.uuid4())
    report_id_a = str(uuid.uuid4())
    report_id_b = str(uuid.uuid4())
    pdf_data_a = b"%PDF-1.4 Report A Content"
    pdf_data_b = b"%PDF-1.4 Report B Content"

    storage = get_storage_service()
    doc_a = await storage.put_object(f"reports/TN-STATE/{case_id}/rep_{report_id_a[:8]}.pdf", pdf_data_a)
    doc_b = await storage.put_object(f"reports/TN-STATE/{case_id}/rep_{report_id_b[:8]}.pdf", pdf_data_b)

    async with session_factory() as session:
        case = Case(
            id=case_id,
            fir_number="FIR/2026/TN/ID-SWAP",
            tenant_id="TN-STATE",
            district_id="CHENNAI",
            police_station_id="PS-CENTRAL",
            status="INVESTIGATING",
        )
        rep_a = ReportModel(
            id=report_id_a,
            case_id=case_id,
            tenant_id="TN-STATE",
            district_id="CHENNAI",
            police_station_id="PS-CENTRAL",
            report_type="SECTION_63_BSA",
            title="Report A",
            file_path=doc_a.key,
            storage_path=doc_a.key,
            file_size_bytes=len(pdf_data_a),
            content_hash=hashlib.sha256(pdf_data_a).hexdigest(),
            file_hash=hashlib.sha256(pdf_data_a).hexdigest(),
            status="COMPLETED",
            storage_backend="LOCAL",
        )
        rep_b = ReportModel(
            id=report_id_b,
            case_id=case_id,
            tenant_id="TN-STATE",
            district_id="CHENNAI",
            police_station_id="PS-CENTRAL",
            report_type="SECTION_63_BSA",
            title="Report B",
            file_path=doc_b.key,
            storage_path=doc_b.key,
            file_size_bytes=len(pdf_data_b),
            content_hash=hashlib.sha256(pdf_data_b).hexdigest(),
            file_hash=hashlib.sha256(pdf_data_b).hexdigest(),
            status="COMPLETED",
            storage_backend="LOCAL",
        )
        session.add_all([case, rep_a, rep_b])
        await session.commit()

    token_io_tn = create_access_token({
        "sub": "IO-TN-01",
        "role": Role.INVESTIGATING_OFFICER.value,
        "tenant_id": "TN-STATE",
        "district_id": "CHENNAI",
        "police_station_id": "PS-CENTRAL",
    })

    # Issue pre-signed URL for Report A
    url_res = await async_client.post(
        f"/api/v1/reports/{report_id_a}/presigned-url",
        json={"expires_in_seconds": 900},
        headers={"Authorization": f"Bearer {token_io_tn}"},
    )
    assert url_res.status_code == 200
    url_a = url_res.json()["download_url"]

    # 1. Swap report ID to Report B in the URL path while keeping Token A
    url_swapped_id = url_a.replace(f"/reports/{report_id_a}/download", f"/reports/{report_id_b}/download")
    res_swapped_id = await async_client.get(url_swapped_id)
    assert res_swapped_id.status_code == 403
    assert res_swapped_id.json()["detail"]["code"] == "INVALID_TOKEN"

    # 2. Swap tenant parameter to a hostile tenant name
    url_swapped_tenant = re.sub(r"tenant=[^&]*", "tenant=HOSTILE-TENANT", url_a)
    res_swapped_tenant = await async_client.get(url_swapped_tenant)
    assert res_swapped_tenant.status_code in (403, 404)


# ==============================================================================
# 3. EXPIRED PRE-SIGNED URL TESTS
# ==============================================================================

@pytest.mark.asyncio
async def test_presigned_url_past_timestamp_rejection(test_engine, async_client: AsyncClient):
    """
    Adversarial Challenge:
    Attempt to use a pre-signed download URL whose expiration timestamp is in the past.
    Must strictly reject with HTTP 403 Forbidden (EXPIRED_TOKEN).
    """
    session_factory = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    report_id = str(uuid.uuid4())
    case_id = str(uuid.uuid4())
    pdf_data = b"%PDF-1.4 Expired Token Test"

    storage = get_storage_service()
    doc = await storage.put_object(f"reports/TN-STATE/{case_id}/rep_{report_id[:8]}.pdf", pdf_data)

    async with session_factory() as session:
        case = Case(
            id=case_id,
            fir_number="FIR/2026/TN/EXPIRED",
            tenant_id="TN-STATE",
            district_id="CHENNAI",
            police_station_id="PS-CENTRAL",
            status="INVESTIGATING",
        )
        report = ReportModel(
            id=report_id,
            case_id=case_id,
            tenant_id="TN-STATE",
            district_id="CHENNAI",
            police_station_id="PS-CENTRAL",
            report_type="SECTION_63_BSA",
            title="Expired Test Report",
            file_path=doc.key,
            storage_path=doc.key,
            file_size_bytes=len(pdf_data),
            content_hash=hashlib.sha256(pdf_data).hexdigest(),
            file_hash=hashlib.sha256(pdf_data).hexdigest(),
            status="COMPLETED",
            storage_backend="LOCAL",
        )
        session.add(case)
        session.add(report)
        await session.commit()

    # Construct an expired pre-signed URL with timestamp 1 hour in the past
    past_timestamp = int(time.time()) - 3600
    token_sig = hmac.new(
        settings.secret_key_value.encode("utf-8"),
        f"{doc.key}:{past_timestamp}:TN-STATE".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    expired_url = f"/api/v1/reports/{report_id}/download?token={token_sig}&expires={past_timestamp}&tenant=TN-STATE"
    res = await async_client.get(expired_url)
    assert res.status_code == 403
    assert res.json()["detail"]["code"] == "EXPIRED_TOKEN"


@pytest.mark.asyncio
async def test_presigned_url_boundary_just_expired(test_engine, async_client: AsyncClient):
    """
    Adversarial Challenge:
    Test boundary edge case: timestamp is exactly 1 second in the past (expires = now - 1).
    Must strictly return 403 EXPIRED_TOKEN.
    """
    report_id = str(uuid.uuid4())
    past_1s = int(time.time()) - 1
    url = f"/api/v1/reports/{report_id}/download?token=anytoken&expires={past_1s}&tenant=TN-STATE"
    res = await async_client.get(url)
    assert res.status_code == 403
    assert res.json()["detail"]["code"] == "EXPIRED_TOKEN"


@pytest.mark.asyncio
async def test_presigned_url_missing_expires_parameter(test_engine, async_client: AsyncClient):
    """
    Adversarial Challenge:
    Request with a token parameter but omitting the expires parameter entirely.
    Must strictly return 403 EXPIRED_TOKEN.
    """
    report_id = str(uuid.uuid4())
    url = f"/api/v1/reports/{report_id}/download?token=some_token&tenant=TN-STATE"
    res = await async_client.get(url)
    assert res.status_code == 403
    assert res.json()["detail"]["code"] == "EXPIRED_TOKEN"


# ==============================================================================
# 4. MULTI-TENANT IDOR ATTACKS ON REPORTS AND PRE-SIGNED URLS
# ==============================================================================

@pytest.mark.asyncio
async def test_idor_presigned_url_and_download_cross_tenant(test_engine, async_client: AsyncClient):
    """
    Adversarial Challenge:
    Tenant B (KL-STATE) attempts to:
    1. Issue a pre-signed download URL for Tenant A's (TN-STATE) report -> 404 Not Found.
    2. Download Tenant A's report using Bearer token -> 404 Not Found.
    3. Poll status of Tenant A's report compilation job -> 404 Not Found.
    4. List reports for Tenant A's case -> 404 Not Found.
    Must strictly enforce anti-enumeration (404 Not Found) across all endpoints.
    """
    session_factory = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    case_id_a = str(uuid.uuid4())
    report_id_a = str(uuid.uuid4())
    job_id_a = str(uuid.uuid4())
    pdf_content = b"%PDF-1.4 Tenant A Confidential Dossier"

    storage = get_storage_service()
    doc_a = await storage.put_object(f"reports/TN-STATE/{case_id_a}/rep_{report_id_a[:8]}.pdf", pdf_content)

    async with session_factory() as session:
        case_a = Case(
            id=case_id_a,
            fir_number="FIR/2026/TN/CONFIDENTIAL",
            tenant_id="TN-STATE",
            district_id="CHENNAI",
            police_station_id="PS-CENTRAL",
            status="INVESTIGATING",
        )
        report_a = ReportModel(
            id=report_id_a,
            case_id=case_id_a,
            tenant_id="TN-STATE",
            district_id="CHENNAI",
            police_station_id="PS-CENTRAL",
            report_type="SECTION_63_BSA",
            title="Tenant A Sensitive Report",
            file_path=doc_a.key,
            storage_path=doc_a.key,
            file_size_bytes=len(pdf_content),
            content_hash=hashlib.sha256(pdf_content).hexdigest(),
            file_hash=hashlib.sha256(pdf_content).hexdigest(),
            status="COMPLETED",
            job_id=job_id_a,
            storage_backend="LOCAL",
        )
        session.add(case_a)
        session.add(report_a)
        await session.commit()

    # Tenant B (Adversary: Kerala State Police)
    token_tenant_b = create_access_token({
        "sub": "IO-KL-99",
        "role": Role.INVESTIGATING_OFFICER.value,
        "tenant_id": "KL-STATE",
        "district_id": "THIRUVANANTHAPURAM",
        "police_station_id": "PS-CYBER",
    })

    # 1. Tenant B attempts to issue pre-signed URL for Tenant A's report -> 404
    res_presign = await async_client.post(
        f"/api/v1/reports/{report_id_a}/presigned-url",
        json={"expires_in_seconds": 900},
        headers={"Authorization": f"Bearer {token_tenant_b}"},
    )
    assert res_presign.status_code == 404
    assert res_presign.json()["detail"]["code"] == "NOT_FOUND"

    # 2. Tenant B attempts direct download with Bearer token -> 404
    res_download = await async_client.get(
        f"/api/v1/reports/{report_id_a}/download",
        headers={"Authorization": f"Bearer {token_tenant_b}"},
    )
    assert res_download.status_code == 404
    assert res_download.json()["detail"]["code"] == "NOT_FOUND"

    # 3. Tenant B attempts to poll Tenant A's job status -> 404
    res_job = await async_client.get(
        f"/api/v1/reports/jobs/{job_id_a}",
        headers={"Authorization": f"Bearer {token_tenant_b}"},
    )
    assert res_job.status_code == 404
    assert res_job.json()["detail"]["code"] == "NOT_FOUND"

    # 4. Tenant B attempts to list reports for Tenant A's case -> 404
    res_list = await async_client.get(
        f"/api/v1/cases/{case_id_a}/reports",
        headers={"Authorization": f"Bearer {token_tenant_b}"},
    )
    assert res_list.status_code == 404
    assert res_list.json()["detail"]["code"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_idor_report_generation_endpoints_cross_tenant(test_engine, async_client: AsyncClient):
    """
    Adversarial Challenge:
    Tenant B attempts to trigger report generation (dossier, bnss94, bsa63) on Tenant A's case.
    All endpoints must return HTTP 404 Not Found.
    """
    session_factory = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    case_id_a = str(uuid.uuid4())
    trace_id_a = str(uuid.uuid4())

    async with session_factory() as session:
        case_a = Case(
            id=case_id_a,
            fir_number="FIR/2026/TN/IDOR-GEN",
            tenant_id="TN-STATE",
            district_id="CHENNAI",
            police_station_id="PS-CENTRAL",
            status="INVESTIGATING",
        )
        trace_a = Trace(
            id=trace_id_a,
            case_id=case_id_a,
            chain="TRON",
            input_value="TSuspectAddress111",
            asset="USDT",
        )
        session.add(case_a)
        session.add(trace_a)
        await session.commit()

    token_tenant_b = create_access_token({
        "sub": "IO-KL-99",
        "role": Role.INVESTIGATING_OFFICER.value,
        "tenant_id": "KL-STATE",
        "district_id": "KOCHI",
        "police_station_id": "PS-NORTH",
    })

    headers = {"Authorization": f"Bearer {token_tenant_b}"}

    # 1. Dossier
    res_dos = await async_client.post(
        f"/api/v1/cases/{case_id_a}/reports/dossier?sync=true",
        json={"trace_id": trace_id_a, "investigator_name": "IO-Hacker"},
        headers=headers,
    )
    assert res_dos.status_code == 404

    # 2. BNSS 94
    res_bnss = await async_client.post(
        f"/api/v1/cases/{case_id_a}/reports/bnss94?sync=true",
        json={"trace_id": trace_id_a, "investigator_name": "IO-Hacker"},
        headers=headers,
    )
    assert res_bnss.status_code == 404

    # 3. BSA 63
    res_bsa = await async_client.post(
        f"/api/v1/cases/{case_id_a}/reports/bsa63?sync=true",
        json={"trace_id": trace_id_a, "investigator_name": "IO-Hacker"},
        headers=headers,
    )
    assert res_bsa.status_code == 404


# ==============================================================================
# 5. CIPHERTEXT CORRUPTION & AEAD AUTHENTICATION INTEGRITY
# ==============================================================================

@pytest.mark.asyncio
async def test_aead_direct_ciphertext_bitflip_raises_invalid_tag():
    """
    Adversarial Challenge:
    Direct cryptographic stress-test of AES-256-GCM encryption at rest:
    Flip 1 bit in ciphertext or authentication tag.
    Decryption MUST detect tag mismatch and raise InvalidTag, never returning corrupted plaintext.
    """
    key = "reports/TN-STATE/case-101/confidential_dossier.pdf"
    plaintext = b"%PDF-1.4 Secret Electronic Evidence Statutory Dossier"
    aes_key = get_encryption_key()
    aesgcm = AESGCM(aes_key)
    nonce = os.urandom(NONCE_LENGTH_BYTES)

    ciphertext = aesgcm.encrypt(nonce, plaintext, associated_data=key.encode("utf-8"))

    # 1. Baseline: Unmodified ciphertext decrypts cleanly
    clean_decrypted = aesgcm.decrypt(nonce, ciphertext, associated_data=key.encode("utf-8"))
    assert clean_decrypted == plaintext

    # 2. Attack: Flip 1 bit in ciphertext body
    corrupted_ciphertext = bytearray(ciphertext)
    corrupted_ciphertext[8] ^= 0x01
    with pytest.raises(InvalidTag):
        aesgcm.decrypt(nonce, bytes(corrupted_ciphertext), associated_data=key.encode("utf-8"))

    # 3. Attack: Flip 1 bit in authentication tag (last 16 bytes of ciphertext)
    corrupted_tag = bytearray(ciphertext)
    corrupted_tag[-2] ^= 0x80
    with pytest.raises(InvalidTag):
        aesgcm.decrypt(nonce, bytes(corrupted_tag), associated_data=key.encode("utf-8"))

    # 4. Attack: Tamper with nonce (12-byte IV)
    corrupted_nonce = bytearray(nonce)
    corrupted_nonce[0] ^= 0xFF
    with pytest.raises(InvalidTag):
        aesgcm.decrypt(bytes(corrupted_nonce), ciphertext, associated_data=key.encode("utf-8"))

    # 5. Attack: Associated Data (AAD) Transposition Attack:
    # Attacker moves ciphertext to another storage key without modifying the bytes.
    transposed_key = "reports/TN-STATE/case-999/unauthorized_target.pdf"
    with pytest.raises(InvalidTag):
        aesgcm.decrypt(nonce, ciphertext, associated_data=transposed_key.encode("utf-8"))


@pytest.mark.asyncio
async def test_storage_vault_ciphertext_corruption_fails_securely():
    """
    Adversarial Challenge:
    Corrupt on-disk ciphertext in LocalStorageProvider.
    Verify that retrieval never returns the original plaintext,
    content hash verification detects the mismatch, and plaintext is never leaked.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        provider = LocalStorageProvider(base_dir=tmpdir, encrypt_at_rest=True)
        key = "reports/TN-STATE/case-202/evidence.pdf"
        plaintext = b"%PDF-1.4 Classified Legal Certificate Payload"

        stored = await provider.put_object(key=key, data=plaintext)
        full_path = provider._resolve_path(key)

        with open(full_path, "rb") as f:
            raw_bytes = bytearray(f.read())

        # Corrupt 2 bytes in the ciphertext payload
        raw_bytes[NONCE_LENGTH_BYTES + 4] ^= 0xAA
        raw_bytes[NONCE_LENGTH_BYTES + 5] ^= 0x55

        with open(full_path, "wb") as f:
            f.write(raw_bytes)

        retrieved_bytes, doc = await provider.get_object(key)
        # 1. Plaintext must never be returned
        assert retrieved_bytes != plaintext
        # 2. Corrupted data must not match original content hash
        assert doc.content_hash != stored.content_hash
        # 3. Corrupted bytes do not form a valid PDF header
        assert not retrieved_bytes.startswith(b"%PDF-")


# ==============================================================================
# 6. ASYNC WORKER ERROR RESILIENCE
# ==============================================================================

@pytest.mark.asyncio
async def test_report_worker_unsupported_report_type_failure():
    """
    Adversarial Challenge:
    Enqueue a background job with an invalid/unsupported report_type.
    ReportWorker MUST catch the failure, transition status to FAILED,
    populate a descriptive error_message, and broadcast the FAILED event.
    """
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        from backend.app.persistence.models import Base
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    report_id = str(uuid.uuid4())
    job_id = str(uuid.uuid4())
    case_id = str(uuid.uuid4())

    async with session_factory() as session:
        report = ReportModel(
            id=report_id,
            case_id=case_id,
            tenant_id="TN-STATE",
            district_id="CHENNAI",
            police_station_id="PS-CENTRAL",
            report_type="UNSUPPORTED_MALICIOUS_TYPE",
            title="Hostile Report Type Test",
            file_path="",
            file_size_bytes=0,
            content_hash="",
            status="QUEUED",
            job_id=job_id,
        )
        session.add(report)
        await session.commit()

    queue = InMemoryReportQueue()
    payload = ReportJobPayload(
        job_id=job_id,
        report_id=report_id,
        case_id=case_id,
        tenant_id="TN-STATE",
        district_id="CHENNAI",
        police_station_id="PS-CENTRAL",
        officer_id="IO-Test",
        report_type="UNSUPPORTED_MALICIOUS_TYPE",
        parameters={},
    )
    await queue.enqueue(payload)

    worker = ReportWorker(db_session_factory=session_factory, queue=queue)
    job = await queue.pop(timeout_seconds=0.5)
    assert job is not None
    await worker.process_job(job)

    # Verify DB persistence of FAILED state
    async with session_factory() as session:
        updated_report = await session.get(ReportModel, report_id)
        assert updated_report is not None
        assert updated_report.status == "FAILED"
        assert "Unsupported report type" in updated_report.error_message

    await engine.dispose()


@pytest.mark.asyncio
async def test_report_job_poll_endpoint_returns_failed_state(test_engine, async_client: AsyncClient):
    """
    Adversarial Challenge:
    Poll GET /api/v1/reports/jobs/{job_id} for a job that failed during execution.
    Endpoint MUST return 200 OK with status='FAILED', descriptive error_message,
    and download_url/presigned_url set to null.
    """
    session_factory = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    report_id = str(uuid.uuid4())
    job_id = str(uuid.uuid4())
    case_id = str(uuid.uuid4())

    async with session_factory() as session:
        case = Case(
            id=case_id,
            fir_number="FIR/2026/TN/JOB-FAIL",
            tenant_id="TN-STATE",
            district_id="CHENNAI",
            police_station_id="PS-CENTRAL",
            status="INVESTIGATING",
        )
        report = ReportModel(
            id=report_id,
            case_id=case_id,
            tenant_id="TN-STATE",
            district_id="CHENNAI",
            police_station_id="PS-CENTRAL",
            report_type="SECTION_63_BSA",
            title="Failed Job Report",
            file_path="",
            file_size_bytes=0,
            content_hash="",
            status="FAILED",
            job_id=job_id,
            error_message="Simulated PDF rendering engine out of memory",
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

    res = await async_client.get(
        f"/api/v1/reports/jobs/{job_id}",
        headers={"Authorization": f"Bearer {token_io_tn}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "FAILED"
    assert data["error_message"] == "Simulated PDF rendering engine out of memory"
    assert data["download_url"] is None
    assert data["presigned_url"] is None


@pytest.mark.asyncio
async def test_report_worker_handles_missing_db_session_factory():
    """
    Adversarial Challenge:
    Invoke ReportWorker.process_job with db_session_factory=None.
    Must log a warning and return gracefully without raising unhandled exceptions.
    """
    queue = InMemoryReportQueue()
    worker = ReportWorker(db_session_factory=None, queue=queue)
    payload = ReportJobPayload(
        job_id="job-1",
        report_id="rep-1",
        case_id="case-1",
        tenant_id="TN-STATE",
        district_id="CHENNAI",
        police_station_id="PS-CENTRAL",
        officer_id="IO-1",
        report_type="SECTION_63_BSA",
        parameters={},
    )
    # Should not raise exception
    await worker.process_job(payload)


# ==============================================================================
# 7. SECTION 63 BSA & SECTION 94 BNSS STATUTORY ASSERTIONS
# ==============================================================================

def test_bsa63_statutory_mandatory_sections_and_clauses():
    """
    Adversarial Challenge:
    Verify Section 63 BSA Certificate generator:
    - Adheres to Section 63(4) Bharatiya Sakshya Adhiniyam, 2023.
    - References superseded Section 65B of Indian Evidence Act, 1872.
    - Emits SCHEDULE — PART A (identification of electronic records & device particulars).
    - Emits SCHEDULE — PART B (certificate by person in charge & lawful control conditions).
    - Enforces statutory conditions: Sec. 63(2)(a), (b), (c), (d).
    - Includes deterministic genesis hash anchor in Part A.
    - Strict guardrail: MUST NOT contain 'conclusive attribution'.
    """
    case_id = str(uuid.uuid4())
    trace_id = str(uuid.uuid4())
    genesis_hash = compute_genesis_hash(case_id)
    now = datetime.now(timezone.utc)

    case = Case(
        id=case_id,
        fir_number="FIR/2026/BSA/777",
        tenant_id="TN-STATE",
        victim_reference="A. Parthasarathy",
        loss_amount_inr=Decimal("1200000.00"),
        suspect_wallet="TSuspectBSA63FullCheck1111111111",
        chain="TRON",
        asset="TRC20:USDT",
    )
    trace = Trace(
        id=trace_id,
        case_id=case_id,
        chain="TRON",
        input_value="TSuspectBSA63FullCheck1111111111",
        asset="TRC20:USDT",
    )
    ev_item = EvidenceItem(
        id="ev_001",
        case_id=case_id,
        trace_id=trace_id,
        evidence_type=EvidenceType.TRANSACTION_RECORD,
        classification=EvidenceClassification.OBSERVED,
        title="Observed Transaction Record",
        source="trongrid",
        source_reference="tx_bsa_test",
        payload={"txid": "tx_bsa_test", "amount": 10000.0},
        content_hash="mock_ev_hash_1",
        collected_at=now,
    )

    pdf_bytes, report_hash, meta = Section63BSAGenerator.generate_pdf(
        case=case,
        trace=trace,
        evidence_items=[ev_item],
        investigator_name="Inspector R. Chandran",
        investigator_rank="Inspector of Police",
        police_station="Cyber Crime Police Station, Central",
        technical_examiner="Dr. K. Ananth, Forensic Scientist",
    )

    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 5000
    assert pdf_bytes.startswith(b"%PDF-")
    assert meta["statutory_section"] == "Section 63(4)"
    assert meta["genesis_hash"] == genesis_hash
    assert meta["evidence_count"] == 1

    extracted_text = extract_pdf_text_streams(pdf_bytes)
    lower_text = extracted_text.lower()

    # 1. Statutory Act & Sections
    assert "section 63" in lower_text
    assert "bharatiya sakshya adhiniyam" in lower_text
    assert "section 65b" in lower_text
    assert "indian evidence act" in lower_text

    # 2. Schedule Part A & Part B
    assert "part a" in lower_text
    assert "part b" in lower_text
    assert "schedule" in lower_text

    # 3. Four mandatory admissibility conditions under Section 63(2)
    assert "sec. 63(2)(a)" in lower_text or "lawful production" in lower_text
    assert "sec. 63(2)(b)" in lower_text or "regular feed of information" in lower_text
    assert "sec. 63(2)(c)" in lower_text or "uninterrupted & proper operation" in lower_text
    assert "sec. 63(2)(d)" in lower_text or "reproducible fidelity" in lower_text
    assert "lawful control" in lower_text

    # 4. Strict guardrail against false forensic certainty
    assert "conclusive attribution" not in lower_text


def test_bnss94_draft_notice_mandatory_warnings_and_demands():
    """
    Adversarial Challenge:
    Verify Section 94 BNSS Draft Notice generator:
    - Prominent officer review warning banner: 'DRAFT NOTICE — FOR INVESTIGATING OFFICER (IO) REVIEW ONLY'.
    - Clear notice that Crypto-Tracer does not autonomously freeze accounts or dispatch legal process.
    - References Section 94 BNSS (formerly Section 91 CrPC).
    - Contains all 6 statutory record-production demands (KYC, Ledger, Counterparties, Audit Logs, Preservation under Section 106 BNSS).
    - Penal warning under Sections 223 / 228 Bharatiya Nyaya Sanhita, 2023 (BNS).
    - Strict guardrail: uses 'accepted attribution hypothesis' rather than claiming absolute certainty.
    """
    case_id = str(uuid.uuid4())
    trace_id = str(uuid.uuid4())

    case = Case(
        id=case_id,
        fir_number="FIR/2026/BNSS/555",
        tenant_id="TN-STATE",
        victim_reference="P. Shanmugam",
        loss_amount_inr=Decimal("850000.00"),
        suspect_wallet="TSuspectBNSS94FullCheck11111111",
        chain="TRON",
        asset="TRC20:USDT",
    )
    trace = Trace(
        id=trace_id,
        case_id=case_id,
        chain="TRON",
        input_value="TSuspectBNSS94FullCheck11111111",
        asset="TRC20:USDT",
    )

    pdf_bytes, report_hash, meta = BNSS94DraftGenerator.generate_pdf(
        case=case,
        trace=trace,
        attribution_report=None,
        target_vasp_override="Binance Holdings Ltd.",
        candidate_address_override="TDepositBNSS94TargetAddress2222",
        investigator_name="Inspector S. Sundaram",
        investigator_rank="Inspector of Police",
        police_station="Cyber Crime Police Station, South",
        urgency_hours=48,
    )

    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 5000
    assert pdf_bytes.startswith(b"%PDF-")
    assert meta["target_vasp"] == "Binance Holdings Ltd."
    assert meta["target_wallet"] == "TDepositBNSS94TargetAddress2222"

    extracted_text = extract_pdf_text_streams(pdf_bytes)
    lower_text = extracted_text.lower()

    # 1. Prominent Warning Banner
    assert "draft notice" in lower_text
    assert "officer review only" in lower_text
    assert "not for autonomous dispatch" in lower_text

    # 2. Statutory References
    assert "section 94" in lower_text
    assert "bharatiya nagarik suraksha sanhita" in lower_text
    assert "section 91" in lower_text
    assert "code of criminal procedure" in lower_text

    # 3. Specific Production Demands
    assert "subscriber kyc" in lower_text
    assert "transaction ledger" in lower_text
    assert "p2p counterparties" in lower_text
    assert "login audit trails" in lower_text
    assert "section 106 bnss" in lower_text

    # 4. Penal Warning
    assert "bharatiya nyaya sanhita" in lower_text or "bns" in lower_text

    # 5. Attestation wording
    assert "accepted attribution hypothesis" in lower_text
    assert "conclusive attribution" not in lower_text


@pytest.mark.asyncio
async def test_bnss94_guardrails_mixer_and_low_confidence_rejection(test_engine, async_client: AsyncClient):
    """
    Adversarial Challenge:
    Test Section 94 BNSS statutory guardrails at API endpoint:
    1. Attempt to generate BNSS 94 notice targeting a privacy mixer (Tornado Cash) -> 400 MIXER_BOUNDARY.
    2. Attempt to generate BNSS 94 notice for an empty trace -> 400 NO_TRANSFERS_FOUND.
    """
    session_factory = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    case_id = str(uuid.uuid4())
    trace_id_empty = str(uuid.uuid4())
    trace_id_mixer = str(uuid.uuid4())

    async with session_factory() as session:
        case = Case(
            id=case_id,
            fir_number="FIR/2026/TN/GUARDRAILS",
            tenant_id="TN-STATE",
            district_id="CHENNAI",
            police_station_id="PS-CENTRAL",
            status="INVESTIGATING",
        )
        # Empty trace
        trace_empty = Trace(
            id=trace_id_empty,
            case_id=case_id,
            chain="TRON",
            input_value="TEmptyTrace111",
            asset="USDT",
            graph_data={"nodes": [], "edges": []},
        )
        # Mixer trace
        trace_mixer = Trace(
            id=trace_id_mixer,
            case_id=case_id,
            chain="TRON",
            input_value="TMixerTrace111",
            asset="USDT",
            graph_data={
                "nodes": [
                    {"id": "n1", "address": "TMixerTrace111", "chain": "TRON", "node_type": "suspect", "hop": 0, "total_received": "0", "total_sent": "1000", "transaction_count": 1},
                    {"id": "n2", "address": "TMixerDest222", "chain": "TRON", "node_type": "intermediate", "hop": 1, "total_received": "1000", "total_sent": "0", "transaction_count": 1},
                ],
                "edges": [
                    {"id": "e1", "tx_hash": "tx_m1", "from_address": "TMixerTrace111", "to_address": "TMixerDest222", "amount": "1000.00", "amount_raw": 1000000000, "asset": "TRC20:USDT", "timestamp": "2026-09-13T12:00:00Z", "hop": 1, "source": "trongrid", "relevance_score": "1.0", "pruned": False},
                ],
                "meta": {"root_address": "TMixerTrace111", "max_hops": 1},
            },
        )
        session.add_all([case, trace_empty, trace_mixer])
        await session.commit()

    token_io_tn = create_access_token({
        "sub": "IO-TN-01",
        "role": Role.INVESTIGATING_OFFICER.value,
        "tenant_id": "TN-STATE",
        "district_id": "CHENNAI",
        "police_station_id": "PS-CENTRAL",
    })

    headers = {"Authorization": f"Bearer {token_io_tn}"}

    # 1. Empty trace rejection
    res_empty = await async_client.post(
        f"/api/v1/cases/{case_id}/reports/bnss94?sync=true",
        json={"trace_id": trace_id_empty, "target_vasp": "Binance"},
        headers=headers,
    )
    assert res_empty.status_code == 400
    assert res_empty.json()["detail"]["code"] == "NO_TRANSFERS_FOUND"

    # 2. Mixer boundary rejection
    res_mixer = await async_client.post(
        f"/api/v1/cases/{case_id}/reports/bnss94?sync=true",
        json={
            "trace_id": trace_id_mixer,
            "target_vasp": "Tornado Cash Mixer Protocol",
            "candidate_address": "TMixerDest222",
        },
        headers=headers,
    )
    assert res_mixer.status_code == 400
    assert res_mixer.json()["detail"]["code"] == "MIXER_BOUNDARY"
