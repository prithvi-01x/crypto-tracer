"""
Empirical Challenger Adversarial Tests for Milestone 1:
- OWASP Security Headers across regular, error (400, 404, 405, 422, 500), and binary download responses
- Inbound X-Correlation-ID lifecycle, whitespace/empty fallbacks, oversized truncation, and error body synchronization
- Dual Error Envelope schema compliance ({ "error": ..., "detail": ... }) across HTTP error codes
- Production 500 traceback masking vs development debug disclosures in ASGI request pipeline
- Demo route production gating (403 DEMO_MODE_DISABLED) and database state isolation
- Production configuration fail-fast invariant enforcement
"""
import os
import uuid
import pytest
from datetime import datetime
from httpx import AsyncClient, ASGITransport
from pydantic import SecretStr

from backend.app.config import settings, Settings
from backend.app.main import app
from backend.app.persistence.models import ReportModel, Case


@pytest.mark.asyncio
async def test_security_headers_on_binary_download(async_client: AsyncClient, test_engine):
    """
    Stress-Test: Verify that FileResponse binary downloads retain all OWASP security headers
    and echo or generate X-Correlation-ID correctly.
    """
    from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

    session_factory = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    
    # 1. Prepare dummy report file on disk
    os.makedirs(settings.REPORTS_DIR, exist_ok=True)
    report_id = str(uuid.uuid4())
    case_id = f"test-case-{report_id[:8]}"
    case_dir = os.path.join(settings.REPORTS_DIR, case_id)
    os.makedirs(case_dir, exist_ok=True)
    pdf_path = os.path.join(case_dir, f"Dossier_{report_id[:8]}.pdf")
    pdf_content = b"%PDF-1.4\n1 0 obj\n<< /Title (Adversarial Test) >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF"
    with open(pdf_path, "wb") as f:
        f.write(pdf_content)

    # 2. Persist Report model in test database
    async with session_factory() as session:
        report = ReportModel(
            id=report_id,
            case_id=case_id,
            trace_id="test-trace-binary",
            report_type="EVIDENCE_DOSSIER",
            title="Adversarial Verification Report",
            file_path=pdf_path,
            file_size_bytes=len(pdf_content),
            content_hash="mock-sha256-seal-binary",
            generated_by="investigator_challenger",
        )
        session.add(report)
        await session.commit()

    # 3. Request download with custom correlation ID
    inbound_corr_id = "binary-download-trace-corr-001"
    res = await async_client.get(
        f"/api/v1/reports/{report_id}/download",
        headers={"X-Correlation-ID": inbound_corr_id},
    )

    assert res.status_code == 200
    assert res.content == pdf_content
    assert res.headers.get("content-type") == "application/pdf"

    # Assert OWASP headers on binary download
    assert res.headers.get("x-frame-options") == "DENY"
    assert res.headers.get("x-content-type-options") == "nosniff"
    assert res.headers.get("referrer-policy") == "strict-origin-when-cross-origin"
    csp = res.headers.get("content-security-policy", "")
    assert "default-src 'self'" in csp
    assert "frame-ancestors 'none'" in csp

    # Assert correlation ID propagated
    assert res.headers.get("x-correlation-id") == inbound_corr_id


@pytest.mark.asyncio
async def test_security_headers_and_envelope_on_routing_404(async_client: AsyncClient):
    """
    Stress-Test: Verify that an unregistered route triggers 404 with full dual error envelope,
    valid ISO-8601 UTC timestamp, and complete security headers.
    """
    custom_cid = "unregistered-route-trace-404"
    res = await async_client.get(
        "/api/v1/unregistered-adversarial-route-does-not-exist",
        headers={"X-Correlation-ID": custom_cid},
    )

    assert res.status_code == 404
    data = res.json()
    assert "error" in data and "detail" in data

    err = data["error"]
    assert err["code"] == "NOT_FOUND"
    assert err["trace_id"] == custom_cid
    assert datetime.fromisoformat(err["timestamp"]) is not None

    # Security headers check
    assert res.headers.get("x-correlation-id") == custom_cid
    assert res.headers.get("x-frame-options") == "DENY"
    assert res.headers.get("x-content-type-options") == "nosniff"
    assert "default-src" in res.headers.get("content-security-policy", "")


@pytest.mark.asyncio
async def test_security_headers_and_envelope_on_405_method_not_allowed(async_client: AsyncClient):
    """
    Stress-Test: Verify that calling an invalid HTTP verb returns 405 with dual envelope
    and full security headers.
    """
    res = await async_client.post("/api/v1/health", headers={"X-Correlation-ID": "method-405-trace"})

    assert res.status_code == 405
    data = res.json()
    assert "error" in data and "detail" in data
    assert data["error"]["code"] == "METHOD_NOT_ALLOWED"
    assert data["error"]["trace_id"] == "method-405-trace"

    assert res.headers.get("x-correlation-id") == "method-405-trace"
    assert res.headers.get("x-frame-options") == "DENY"
    assert res.headers.get("x-content-type-options") == "nosniff"


@pytest.mark.asyncio
async def test_security_headers_and_envelope_on_malformed_json(async_client: AsyncClient):
    """
    Stress-Test: Verify that submitting a body with broken JSON syntax returns 422
    formatted into the dual error envelope rather than an unhandled parser crash.
    """
    res = await async_client.post(
        "/api/v1/cases",
        content=b'{"fir_number": [unclosed array syntax',
        headers={"Content-Type": "application/json", "X-Correlation-ID": "malformed-json-trace"},
    )

    assert res.status_code in (400, 422)
    data = res.json()
    assert "error" in data and "detail" in data
    assert data["error"]["trace_id"] == "malformed-json-trace"
    assert res.headers.get("x-correlation-id") == "malformed-json-trace"
    assert res.headers.get("x-frame-options") == "DENY"
    assert res.headers.get("x-content-type-options") == "nosniff"


@pytest.mark.asyncio
async def test_correlation_id_lifecycle_and_edge_cases(async_client: AsyncClient):
    """
    Stress-Test: Verify correlation ID generator/echo logic across edge cases:
    - Omitted header generates valid UUID4
    - Whitespace-only header generates valid UUID4
    - Empty header generates valid UUID4
    - Oversized header (>128 chars) generates valid UUID4
    - Standard custom alphanumeric/punctuation header preserved
    """
    # 1. Omitted
    r1 = await async_client.get("/")
    cid1 = r1.headers.get("x-correlation-id")
    assert cid1 is not None
    assert uuid.UUID(cid1).version == 4

    # 2. Whitespace-only
    r2 = await async_client.get("/", headers={"X-Correlation-ID": "     "})
    cid2 = r2.headers.get("x-correlation-id")
    assert cid2 != "     "
    assert uuid.UUID(cid2).version == 4

    # 3. Empty string
    r3 = await async_client.get("/", headers={"X-Correlation-ID": ""})
    cid3 = r3.headers.get("x-correlation-id")
    assert cid3 != ""
    assert uuid.UUID(cid3).version == 4

    # 4. Oversized (> 128 characters)
    oversized = "X" * 256
    r4 = await async_client.get("/", headers={"X-Correlation-ID": oversized})
    cid4 = r4.headers.get("x-correlation-id")
    assert cid4 != oversized
    assert uuid.UUID(cid4).version == 4

    # 5. Formatted structured correlation ID
    structured_id = "TN-POLICE:CRIME-BRANCH:FIR-2026-9901:INVESTIGATOR-42"
    r5 = await async_client.get("/", headers={"X-Correlation-ID": structured_id})
    assert r5.headers.get("x-correlation-id") == structured_id


@pytest.mark.asyncio
async def test_unhandled_500_in_real_asgi_pipeline_production(monkeypatch):
    """
    Stress-Test: Verify that an unhandled exception thrown in endpoint execution
    through the actual ASGI pipeline in production:
    - Returns HTTP 500
    - Emits dual error envelope
    - Sets generic error message "Internal server error"
    - Absolutely masks internal tracebacks and sensitive credentials
    - Includes HSTS header (in production)
    """
    monkeypatch.setattr(settings, "APP_ENV", "production")

    @app.get("/api/v1/adversarial-crash-test-endpoint")
    def crash_endpoint():
        raise RuntimeError("LEAKED_DB_CREDENTIAL: postgresql://admin:SuperSecretPassword999@10.0.0.5:5432/core")

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get(
            "/api/v1/adversarial-crash-test-endpoint",
            headers={"X-Correlation-ID": "prod-500-trace-001"},
        )

        assert res.status_code == 500
        assert res.headers.get("x-correlation-id") == "prod-500-trace-001"
        assert res.headers.get("x-frame-options") == "DENY"
        assert res.headers.get("x-content-type-options") == "nosniff"
        assert res.headers.get("strict-transport-security") == "max-age=31536000; includeSubDomains"

        data = res.json()
        assert "error" in data and "detail" in data
        assert data["error"]["code"] == "INTERNAL_SERVER_ERROR"
        assert data["error"]["message"] == "Internal server error"
        assert data["detail"]["message"] == "Internal server error"

        # Verification that no secrets or tracebacks are exposed
        assert "traceback" not in data["error"]
        assert "traceback" not in data["detail"]
        assert "SuperSecretPassword999" not in res.text
        assert "10.0.0.5" not in res.text


@pytest.mark.asyncio
async def test_unhandled_500_in_real_asgi_pipeline_development(monkeypatch):
    """
    Stress-Test: Verify that an unhandled exception in development mode provides
    diagnostic traceback information in the error envelope.
    """
    monkeypatch.setattr(settings, "APP_ENV", "development")

    @app.get("/api/v1/adversarial-crash-test-dev-endpoint")
    def crash_endpoint():
        raise ValueError("DEV_DIAGNOSTIC: Detailed calculation overflow")

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get(
            "/api/v1/adversarial-crash-test-dev-endpoint",
            headers={"X-Correlation-ID": "dev-500-trace-002"},
        )

        assert res.status_code == 500
        data = res.json()
        assert "error" in data and "detail" in data
        assert data["error"]["code"] == "INTERNAL_SERVER_ERROR"
        assert "DEV_DIAGNOSTIC" in data["error"]["message"]
        assert "traceback" in data["error"]
        assert "traceback" in data["detail"]


@pytest.mark.asyncio
async def test_demo_gating_in_production_with_database_isolation(async_client: AsyncClient, test_engine, monkeypatch):
    """
    Stress-Test: Verify that when APP_ENV=production:
    - /api/v1/demo/status returns HTTP 403 Forbidden with DEMO_MODE_DISABLED
    - /api/v1/demo/seed returns HTTP 403 Forbidden with DEMO_MODE_DISABLED
    - Execution dependency blocks execution BEFORE any DB mutations occur
    """
    from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

    monkeypatch.setattr(settings, "APP_ENV", "production")
    session_factory = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    # 1. Pre-seed a sensitive production-like case record
    protected_case_id = "prod-isolated-case-id-1234"
    async with session_factory() as session:
        case = Case(
            id=protected_case_id,
            fir_number="FIR-PROD-RETAIN-001",
            victim_reference="Protected Victim Record",
            loss_amount_inr=500000.0,
            ack_number="ACK-PROD-001",
            suspect_wallet="TMuA6YqfCeX8EhbfYEg5y7S4Dqz9Dw92eP",
            chain="TRON",
            asset="USDT",
            status="OPEN",
        )
        session.add(case)
        await session.commit()

    # 2. Attack: Attempt to invoke POST /api/v1/demo/seed to purge/reset DB
    res_seed = await async_client.post("/api/v1/demo/seed", headers={"X-Correlation-ID": "attack-demo-seed"})
    assert res_seed.status_code == 403
    data_seed = res_seed.json()
    assert data_seed["error"]["code"] == "DEMO_MODE_DISABLED"
    assert data_seed["detail"]["code"] == "DEMO_MODE_DISABLED"
    assert res_seed.headers.get("x-frame-options") == "DENY"

    # 3. Verify the case record in DB was NOT deleted or modified
    async with session_factory() as session:
        retained = await session.get(Case, protected_case_id)
        assert retained is not None
        assert retained.fir_number == "FIR-PROD-RETAIN-001"

    # 4. Attempt GET /api/v1/demo/status
    res_status = await async_client.get("/api/v1/demo/status")
    assert res_status.status_code == 403
    data_status = res_status.json()
    assert data_status["error"]["code"] == "DEMO_MODE_DISABLED"


def test_production_configuration_invariants_adversarial_suite():
    """
    Stress-Test: Verify validate_production_invariants() against boundary conditions:
    1. Empty SECRET_KEY
    2. Short SECRET_KEY (< 32 chars)
    3. Insecure development prefix ('insecure-dev')
    4. Placeholder 'change-me'
    5. SQLite database URL in production
    6. Default development postgres credentials (postgres:postgres@localhost)
    7. Valid production configuration
    """
    # 1. Empty SECRET_KEY
    with pytest.raises(SystemExit) as exc:
        s = Settings(APP_ENV="production", SECRET_KEY=SecretStr(""), DATABASE_URL=SecretStr("postgresql+asyncpg://u:p@db/prod"))
        s.validate_production_invariants()
    assert exc.value.code == 1

    # 2. Short SECRET_KEY
    with pytest.raises(SystemExit) as exc:
        s = Settings(APP_ENV="production", SECRET_KEY=SecretStr("short-secret-key-12345"), DATABASE_URL=SecretStr("postgresql+asyncpg://u:p@db/prod"))
        s.validate_production_invariants()
    assert exc.value.code == 1

    # 3. Insecure prefix
    with pytest.raises(SystemExit) as exc:
        s = Settings(APP_ENV="production", SECRET_KEY=SecretStr("insecure-dev-production-key-at-least-32-chars-long"), DATABASE_URL=SecretStr("postgresql+asyncpg://u:p@db/prod"))
        s.validate_production_invariants()
    assert exc.value.code == 1

    # 4. Placeholder change-me
    with pytest.raises(SystemExit) as exc:
        s = Settings(APP_ENV="production", SECRET_KEY=SecretStr("my-production-key-change-me-please-long-enough"), DATABASE_URL=SecretStr("postgresql+asyncpg://u:p@db/prod"))
        s.validate_production_invariants()
    assert exc.value.code == 1

    # 5. SQLite in production
    with pytest.raises(SystemExit) as exc:
        s = Settings(APP_ENV="production", SECRET_KEY=SecretStr("a" * 32), DATABASE_URL=SecretStr("sqlite+aiosqlite:///:memory:"))
        s.validate_production_invariants()
    assert exc.value.code == 1

    # 6. Default postgres in production
    with pytest.raises(SystemExit) as exc:
        s = Settings(APP_ENV="production", SECRET_KEY=SecretStr("a" * 32), DATABASE_URL=SecretStr("postgresql+asyncpg://postgres:postgres@localhost:5432/crypto_tracer"))
        s.validate_production_invariants()
    assert exc.value.code == 1

    # 7. Valid production configuration must NOT exit
    valid_settings = Settings(
        APP_ENV="production",
        SECRET_KEY=SecretStr("z" * 64),
        DATABASE_URL=SecretStr("postgresql+asyncpg://forensic_svc:P%40ssw0rd!Secure99@db.forensics.state.gov:5432/crypto_tracer_prod"),
    )
    valid_settings.validate_production_invariants()
