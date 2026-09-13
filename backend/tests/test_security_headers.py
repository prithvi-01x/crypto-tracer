"""
Unit and integration tests for security middlewares, OWASP security headers,
request correlation tracking, centralized error envelopes, and demo route gating.
"""
import uuid
import pytest
from httpx import AsyncClient

from backend.app.config import settings
from backend.app.logging import (
    correlation_id_ctx,
    get_correlation_id,
    StructuredJsonFormatter,
)
import logging


@pytest.mark.asyncio
async def test_standard_security_headers_present(async_client: AsyncClient):
    """Verify OWASP defense-in-depth security headers are present on HTTP responses."""
    res = await async_client.get("/")
    assert res.status_code == 200

    # 1. Clickjacking prevention
    assert res.headers.get("x-frame-options") == "DENY"

    # 2. MIME-sniffing prevention
    assert res.headers.get("x-content-type-options") == "nosniff"

    # 3. Referrer leakage prevention
    assert res.headers.get("referrer-policy") == "strict-origin-when-cross-origin"

    # 4. Content Security Policy
    csp = res.headers.get("content-security-policy")
    assert csp is not None
    assert "default-src 'self'" in csp
    assert "frame-ancestors 'none'" in csp


@pytest.mark.asyncio
async def test_conditional_hsts_behavior(async_client: AsyncClient):
    """Verify Strict-Transport-Security is omitted over plain HTTP and added when secure transport is indicated."""
    # 1. Plain HTTP request: HSTS must NOT be set
    res_plain = await async_client.get("/")
    assert "strict-transport-security" not in res_plain.headers

    # 2. Request behind TLS-terminating proxy with X-Forwarded-Proto: https
    res_https = await async_client.get("/", headers={"X-Forwarded-Proto": "https"})
    hsts = res_https.headers.get("strict-transport-security")
    assert hsts is not None
    assert "max-age=31536000" in hsts
    assert "includeSubDomains" in hsts


@pytest.mark.asyncio
async def test_correlation_id_generation_and_propagation(async_client: AsyncClient):
    """Verify X-Correlation-ID is generated if omitted, or echoed if provided."""
    # 1. Omitted header: generated as valid UUID4
    res_auto = await async_client.get("/")
    auto_cid = res_auto.headers.get("x-correlation-id")
    assert auto_cid is not None
    parsed_uuid = uuid.UUID(auto_cid)
    assert parsed_uuid.version == 4

    # 2. Inbound custom header: echoed verbatim
    custom_cid = "corr-investigation-test-12345"
    res_custom = await async_client.get("/", headers={"X-Correlation-ID": custom_cid})
    assert res_custom.headers.get("x-correlation-id") == custom_cid


@pytest.mark.asyncio
async def test_cors_exposes_correlation_id(async_client: AsyncClient):
    """Verify CORS response exposes X-Correlation-ID to client JavaScript."""
    res = await async_client.get(
        "/api/v1/cases",
        headers={
            "Origin": "http://localhost:5173",
        },
    )
    exposed = res.headers.get("access-control-expose-headers", "")
    assert "x-correlation-id" in exposed.lower() or "X-Correlation-ID" in exposed


@pytest.mark.asyncio
async def test_error_envelope_structure_on_404(async_client: AsyncClient):
    """Verify 404 Not Found returns the dual error envelope with trace_id and detail."""
    res = await async_client.get("/api/v1/cases/non-existent-case-id-12345")
    assert res.status_code == 404

    data = res.json()
    assert "error" in data
    assert "detail" in data

    err = data["error"]
    assert err["code"] == "NOT_FOUND"
    assert "trace_id" in err
    assert "timestamp" in err

    # Security headers and correlation ID header must be present on error responses
    assert "x-frame-options" in res.headers
    assert res.headers.get("x-correlation-id") == err["trace_id"]


@pytest.mark.asyncio
async def test_error_envelope_structure_on_422(async_client: AsyncClient):
    """Verify 422 Validation Error returns dual envelope with validation details."""
    res = await async_client.post(
        "/api/v1/cases",
        json={"invalid_field": "missing_required_fir"},
    )
    assert res.status_code == 422

    data = res.json()
    assert "error" in data
    assert "detail" in data

    err = data["error"]
    assert err["code"] == "VALIDATION_ERROR"
    assert "details" in err
    assert isinstance(err["details"], list)
    assert isinstance(data["detail"], list)
    assert res.headers.get("x-correlation-id") == err["trace_id"]


@pytest.mark.asyncio
async def test_error_envelope_structure_on_400(async_client: AsyncClient):
    """Verify 400 Bad Request returns dual envelope preserving code and message."""
    res = await async_client.post(
        "/api/v1/cases",
        json={
            "fir_number": "FIR-TEST-UNSUP-001",
            "chain": "SOLANA",
            "asset": "SOL",
        },
    )
    assert res.status_code == 400

    data = res.json()
    assert "error" in data
    assert "detail" in data

    assert data["error"]["code"] == "UNSUPPORTED_CHAIN"
    assert data["detail"]["code"] == "UNSUPPORTED_CHAIN"
    assert res.headers.get("x-correlation-id") == data["error"]["trace_id"]


@pytest.mark.asyncio
async def test_demo_routes_gated_in_production(async_client: AsyncClient, monkeypatch):
    """Verify /demo/* endpoints return 403 DEMO_MODE_DISABLED when running in production mode."""
    monkeypatch.setattr(settings, "APP_ENV", "production")

    # 1. GET /demo/status
    res_status = await async_client.get("/api/v1/demo/status")
    assert res_status.status_code == 403
    data_status = res_status.json()
    assert data_status["error"]["code"] == "DEMO_MODE_DISABLED"
    assert "Demo routes are disabled in production" in data_status["error"]["message"]
    assert data_status["detail"]["code"] == "DEMO_MODE_DISABLED"

    # 2. POST /demo/seed
    res_seed = await async_client.post("/api/v1/demo/seed")
    assert res_seed.status_code == 403
    data_seed = res_seed.json()
    assert data_seed["error"]["code"] == "DEMO_MODE_DISABLED"


@pytest.mark.asyncio
async def test_demo_routes_accessible_in_development(async_client: AsyncClient, monkeypatch):
    """Verify /demo/* endpoints are accessible when running in development mode."""
    monkeypatch.setattr(settings, "APP_ENV", "development")

    res_status = await async_client.get("/api/v1/demo/status")
    assert res_status.status_code == 200
    data = res_status.json()
    assert "scenario" in data


def test_structured_json_logging_format():
    """Verify StructuredJsonFormatter outputs valid JSON with correlation_id."""
    formatter = StructuredJsonFormatter()
    record = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname="test.py",
        lineno=42,
        msg="Forensic trace started for address %s",
        args=("TMuA6YqfCeX8EhbfYEg5y7S4Dqz9Dw92eP",),
        exc_info=None,
    )

    token = correlation_id_ctx.set("trace-uuid-abcdef-123456")
    try:
        formatted = formatter.format(record)
        import json
        parsed = json.loads(formatted)
        assert parsed["level"] == "INFO"
        assert parsed["logger"] == "test_logger"
        assert parsed["correlation_id"] == "trace-uuid-abcdef-123456"
        assert "TMuA6YqfCeX8EhbfYEg5y7S4Dqz9Dw92eP" in parsed["message"]
        assert "timestamp" in parsed
    finally:
        correlation_id_ctx.reset(token)


@pytest.mark.asyncio
async def test_unhandled_exception_handler_masks_in_production(monkeypatch):
    """Verify 500 error handler masks tracebacks in production mode."""
    import json
    from starlette.requests import Request
    from backend.app.core.errors import unhandled_exception_handler

    monkeypatch.setattr(settings, "APP_ENV", "production")

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/api/v1/test-crash",
        "headers": [(b"host", b"test"), (b"x-correlation-id", b"crash-trace-123")],
    }
    request = Request(scope)
    exc = RuntimeError("Database connection secret_pw@internal leaked!")

    response = await unhandled_exception_handler(request, exc)
    assert response.status_code == 500
    assert response.headers.get("x-correlation-id") == "crash-trace-123"
    assert response.headers.get("x-frame-options") == "DENY"

    body = json.loads(response.body.decode("utf-8"))
    assert body["error"]["code"] == "INTERNAL_SERVER_ERROR"
    assert body["error"]["message"] == "Internal server error"
    assert "secret_pw" not in str(body)
    assert "traceback" not in body["error"]


@pytest.mark.asyncio
async def test_unhandled_exception_handler_includes_details_in_development(monkeypatch):
    """Verify 500 error handler provides debug traceback in development mode."""
    import json
    from starlette.requests import Request
    from backend.app.core.errors import unhandled_exception_handler

    monkeypatch.setattr(settings, "APP_ENV", "development")

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/api/v1/test-crash",
        "headers": [(b"host", b"test")],
    }
    request = Request(scope)
    exc = ValueError("Explicit test error")

    response = await unhandled_exception_handler(request, exc)
    assert response.status_code == 500
    body = json.loads(response.body.decode("utf-8"))
    assert body["error"]["code"] == "INTERNAL_SERVER_ERROR"
    assert "ValueError: Explicit test error" in body["error"]["message"]
    assert "traceback" in body["error"]

