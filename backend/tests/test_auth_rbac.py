"""
Tests for Feature 8 & 9: OIDC / JWT RS256 & HS256 Authentication and 4-Role RBAC.
"""
from datetime import timedelta
import pytest
from httpx import AsyncClient
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
import jwt

from backend.app.config import settings
from backend.app.core.auth import (
    Role,
    jwt_auth_engine,
    create_access_token,
    normalize_role,
)


@pytest.fixture
def rsa_keypair():
    """Generates an ephemeral 2048-bit RSA keypair for testing RS256 token verification."""
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )
    pem_private = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    pem_public = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return pem_private, pem_public


@pytest.mark.asyncio
async def test_unauthenticated_dev_fallback_returns_default_session(async_client: AsyncClient):
    """In development/test mode, unauthenticated request falls back to default mock officer."""
    settings.APP_ENV = "development"
    response = await async_client.get("/api/v1/auth/me")
    assert response.status_code == 200
    data = response.json()
    assert data["is_authenticated"] is True
    assert data["officer_id"] == "OFFICER-DL-812"
    assert data["role"] == "INVESTIGATING_OFFICER"
    assert data["tenant_id"] == "TN-STATE"
    assert data["district_id"] == "CYBER-CRIME-HQ"
    assert data["police_station_id"] == "PS-CENTRAL"
    assert data["station_id"] == "PS-CENTRAL"


@pytest.mark.asyncio
async def test_production_unauthenticated_returns_401(async_client: AsyncClient):
    """In production mode, unauthenticated request strictly returns HTTP 401 with dual error envelope."""
    orig_env = settings.APP_ENV
    try:
        settings.APP_ENV = "production"
        response = await async_client.get("/api/v1/auth/me")
        assert response.status_code == 401
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == "UNAUTHORIZED"
        assert "Missing Authorization header" in data["error"]["message"]
    finally:
        settings.APP_ENV = orig_env


@pytest.mark.asyncio
async def test_invalid_authorization_header_format_returns_401(async_client: AsyncClient):
    """Malformed Authorization header (e.g. not 'Bearer <token>') returns HTTP 401."""
    response = await async_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Basic dXNlcjpwYXNz"},
    )
    assert response.status_code == 401
    data = response.json()
    assert data["error"]["code"] == "UNAUTHORIZED"
    assert "Expected 'Bearer <token>'" in data["error"]["message"]


@pytest.mark.asyncio
async def test_hs256_valid_token_decoding(async_client: AsyncClient):
    """Valid HS256 token decodes identity and tenant claims accurately."""
    token = create_access_token(
        claims={
            "sub": "OFFICER-KA-441",
            "name": "Inspector Ananya Rao",
            "badge_number": "CYBER-BLR-1024",
            "unit": "Karnataka CID Cyber Cell",
            "role": "SUPERVISOR",
            "tenant_id": "KA-STATE",
            "district_id": "BLR-CITY",
            "police_station_id": "PS-INDIRANAGAR",
        }
    )
    response = await async_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["officer_id"] == "OFFICER-KA-441"
    assert data["name"] == "Inspector Ananya Rao"
    assert data["role"] == "SUPERVISOR"
    assert data["tenant_id"] == "KA-STATE"
    assert data["district_id"] == "BLR-CITY"
    assert data["police_station_id"] == "PS-INDIRANAGAR"


@pytest.mark.asyncio
async def test_expired_token_returns_401(async_client: AsyncClient):
    """Expired JWT token returns HTTP 401 Unauthorized."""
    token = create_access_token(
        claims={"sub": "OFFICER-EXPIRED", "role": "INVESTIGATING_OFFICER"},
        expires_delta=timedelta(seconds=-60),
    )
    response = await async_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 401
    data = response.json()
    assert data["error"]["code"] == "UNAUTHORIZED"
    assert "expired" in data["error"]["message"].lower()


@pytest.mark.asyncio
async def test_invalid_signature_returns_401(async_client: AsyncClient):
    """Token signed with a different secret key fails signature validation."""
    tampered_token = create_access_token(
        claims={"sub": "OFFICER-TAMPERED", "role": "ADMIN"},
        key="completely-different-wrong-secret-key-00000000",
    )
    response = await async_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {tampered_token}"},
    )
    assert response.status_code == 401
    data = response.json()
    assert data["error"]["code"] == "UNAUTHORIZED"
    assert "signature" in data["error"]["message"].lower()


@pytest.mark.asyncio
async def test_rs256_token_decoding(async_client: AsyncClient, rsa_keypair):
    """Valid RS256 token signed with private RSA key is verified by public key."""
    pem_private, pem_public = rsa_keypair
    jwt_auth_engine._test_rsa_public_key = pem_public

    try:
        rs256_token = jwt.encode(
            {
                "sub": "OFFICER-CBI-007",
                "name": "Superintendent Vikram Singh",
                "role": "ADMIN",
                "tenant_id": "CBI-CENTRAL",
                "district_id": "SPECIAL-CRIME",
                "police_station_id": "CBI-HQ",
            },
            pem_private,
            algorithm="RS256",
        )

        response = await async_client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {rs256_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["officer_id"] == "OFFICER-CBI-007"
        assert data["role"] == "ADMIN"
        assert data["tenant_id"] == "CBI-CENTRAL"
    finally:
        jwt_auth_engine._test_rsa_public_key = None


def test_role_normalization():
    """Confirms role strings across IdP dialects normalize to canonical 4 roles."""
    assert normalize_role("ROLE_INVESTIGATOR") == Role.INVESTIGATING_OFFICER.value
    assert normalize_role("INVESTIGATING_OFFICER") == Role.INVESTIGATING_OFFICER.value
    assert normalize_role("io") == Role.INVESTIGATING_OFFICER.value
    assert normalize_role("ROLE_SUPERVISOR") == Role.SUPERVISOR.value
    assert normalize_role("Supervisor") == Role.SUPERVISOR.value
    assert normalize_role("ROLE_ADMIN") == Role.ADMIN.value
    assert normalize_role("ADMINISTRATOR") == Role.ADMIN.value
    assert normalize_role("ROLE_AUDITOR") == Role.AUDITOR.value
    assert normalize_role("auditor") == Role.AUDITOR.value
    assert normalize_role(None) == Role.INVESTIGATING_OFFICER.value


@pytest.mark.asyncio
async def test_rbac_investigating_officer_can_create_case(async_client: AsyncClient):
    """Investigating Officer can register a new case."""
    token = create_access_token(claims={"sub": "OFF-IO-1", "role": "INVESTIGATING_OFFICER", "tenant_id": "TN-STATE"})
    payload = {
        "fir_number": "FIR-2026-IO-001",
        "victim_reference": "VICTIM-IO-1",
        "loss_amount_inr": 100000.00,
    }
    response = await async_client.post(
        "/api/v1/cases",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    assert response.json()["fir_number"] == "FIR-2026-IO-001"


@pytest.mark.asyncio
async def test_rbac_supervisor_can_create_case(async_client: AsyncClient):
    """Supervisor can register a new case."""
    token = create_access_token(claims={"sub": "OFF-SUP-1", "role": "SUPERVISOR", "tenant_id": "TN-STATE"})
    payload = {
        "fir_number": "FIR-2026-SUP-001",
        "victim_reference": "VICTIM-SUP-1",
        "loss_amount_inr": 200000.00,
    }
    response = await async_client.post(
        "/api/v1/cases",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201


@pytest.mark.asyncio
async def test_rbac_admin_can_create_case(async_client: AsyncClient):
    """Admin can register a new case."""
    token = create_access_token(claims={"sub": "OFF-ADM-1", "role": "ADMIN", "tenant_id": "TN-STATE"})
    payload = {
        "fir_number": "FIR-2026-ADM-001",
        "victim_reference": "VICTIM-ADM-1",
        "loss_amount_inr": 300000.00,
    }
    response = await async_client.post(
        "/api/v1/cases",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201


@pytest.mark.asyncio
async def test_rbac_auditor_forbidden_from_case_creation(async_client: AsyncClient):
    """Auditor role is read-only and is strictly forbidden from creating cases (HTTP 403)."""
    token = create_access_token(claims={"sub": "OFF-AUD-1", "role": "AUDITOR", "tenant_id": "TN-STATE"})
    payload = {
        "fir_number": "FIR-2026-AUD-FAIL",
        "victim_reference": "VICTIM-FAIL",
        "loss_amount_inr": 50000.00,
    }
    response = await async_client.post(
        "/api/v1/cases",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403
    data = response.json()
    assert data["error"]["code"] == "FORBIDDEN"
    assert "not authorized" in data["error"]["message"]


@pytest.mark.asyncio
async def test_rbac_auditor_forbidden_from_trace_execution(async_client: AsyncClient):
    """Auditor role is forbidden from starting traces (HTTP 403)."""
    token = create_access_token(claims={"sub": "OFF-AUD-2", "role": "AUDITOR", "tenant_id": "TN-STATE"})
    payload = {
        "case_id": "some-case-id",
        "chain": "TRON",
        "input": "TYDZSxdBzWnCuB4jF3K6j5X3qW7b9X1234",
    }
    response = await async_client.post(
        "/api/v1/traces",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_rbac_auditor_allowed_to_read_cases(async_client: AsyncClient):
    """Auditor role has read-only access to view case registers."""
    token = create_access_token(claims={"sub": "OFF-AUD-3", "role": "AUDITOR", "tenant_id": "TN-STATE"})
    response = await async_client.get(
        "/api/v1/cases",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert "cases" in response.json()
