"""
Empirical Challenger Adversarial Security Test Suite for Milestone 2:
Phase 1: Auth, Multi-Tenancy Foundation & At-Rest Encryption

Probes:
1. Token signature tampering (payload tampering, header tampering, bit-flipping, truncated signature, unsigned token) -> 401
2. Token expiration and temporal boundaries (expired token, historical token, future nbf) -> 401
3. Algorithm confusion attacks (RS256 vs HS256 key confusion with RSA public key, forged tokens, none algorithm) -> 401
4. Cross-tenant IDOR attacks (Tenant A: "TN-STATE" vs Tenant B: "DL-POLICE" probing GET, PATCH, DELETE, notes, traces, reports, audit, findings) -> strict 404
5. Privilege escalation attacks (AUDITOR role attempting case creation, trace execution, deletion, mutation, report generation) -> strict 403
6. Production zero-trust unauthenticated perimeter gate -> strict 401 across endpoints
7. DPDP Act 2023 at-rest encryption verification and ciphertext corruption resilience
"""
import base64
import json
import os
import uuid
from datetime import datetime, timezone, timedelta
import pytest
from httpx import AsyncClient
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
import jwt
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from backend.app.config import settings
from backend.app.core.auth import (
    Role,
    jwt_auth_engine,
    create_access_token,
    normalize_role,
)
from backend.app.persistence.models import Case


@pytest.fixture
def rsa_keypair():
    """Generates an ephemeral 2048-bit RSA keypair for testing RS256/algorithm confusion."""
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


def make_officer_token(officer_id: str, tenant_id: str, role: str = "INVESTIGATING_OFFICER", **kwargs) -> str:
    """Helper to generate JWT bearer token for a specific tenant and role."""
    claims = {
        "sub": officer_id,
        "name": f"Officer {officer_id}",
        "badge_number": f"BADGE-{officer_id}",
        "unit": "Forensic Cyber Crime Unit",
        "role": role,
        "tenant_id": tenant_id,
        "district_id": f"{tenant_id}-DISTRICT",
        "police_station_id": f"{tenant_id}-PS-1",
        **kwargs,
    }
    return create_access_token(claims)


# ============================================================================
# 1. TOKEN SIGNATURE TAMPERING PROBES
# ============================================================================

@pytest.mark.asyncio
async def test_adversarial_tamper_payload_role_escalation_rejected_401(async_client: AsyncClient):
    """
    Adversarial Probe: An attacker takes a valid INVESTIGATING_OFFICER token,
    tampering with the decoded payload JSON to set role='ADMIN', and forwards the modified token
    with the original signature. The server must reject it with HTTP 401 Unauthorized.
    """
    valid_token = make_officer_token("OFF-IO-TAMPER", "TN-STATE", role="INVESTIGATING_OFFICER")
    parts = valid_token.split(".")
    assert len(parts) == 3

    # Decode payload
    payload_raw = base64.urlsafe_b64decode(parts[1] + "==").decode("utf-8")
    payload_json = json.loads(payload_raw)
    assert payload_json["role"] == "INVESTIGATING_OFFICER"

    # Escalate role to ADMIN without re-signing
    payload_json["role"] = "ADMIN"
    payload_json["sub"] = "OFF-ATTACKER"
    tampered_payload_b64 = base64.urlsafe_b64encode(json.dumps(payload_json).encode("utf-8")).decode("utf-8").rstrip("=")
    tampered_token = f"{parts[0]}.{tampered_payload_b64}.{parts[2]}"

    # Send to /api/v1/auth/me
    res = await async_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {tampered_token}"},
    )
    assert res.status_code == 401
    data = res.json()
    assert data["error"]["code"] == "UNAUTHORIZED"
    assert "signature" in data["error"]["message"].lower()

    # Send to /api/v1/cases
    res_cases = await async_client.post(
        "/api/v1/cases",
        json={"fir_number": "FIR-TAMPER-001", "victim_reference": "VICTIM-1"},
        headers={"Authorization": f"Bearer {tampered_token}"},
    )
    assert res_cases.status_code == 401
    assert res_cases.json()["error"]["code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_adversarial_tamper_header_algorithm_rejected_401(async_client: AsyncClient):
    """
    Adversarial Probe: Modify header fields (e.g. changing typ or adding custom fields)
    while keeping the original signature. The server must detect signature mismatch and return HTTP 401.
    """
    valid_token = make_officer_token("OFF-IO-HEADER", "TN-STATE")
    parts = valid_token.split(".")

    header_raw = base64.urlsafe_b64decode(parts[0] + "==").decode("utf-8")
    header_json = json.loads(header_raw)
    header_json["forged_by"] = "attacker"
    tampered_header_b64 = base64.urlsafe_b64encode(json.dumps(header_json).encode("utf-8")).decode("utf-8").rstrip("=")
    tampered_token = f"{tampered_header_b64}.{parts[1]}.{parts[2]}"

    res = await async_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {tampered_token}"},
    )
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_adversarial_corrupted_signature_bits_rejected_401(async_client: AsyncClient):
    """
    Adversarial Probe: Bit-flipping and character replacement in the signature part.
    The server must return HTTP 401.
    """
    valid_token = make_officer_token("OFF-IO-BITS", "TN-STATE")
    header_b64, payload_b64, sig_b64 = valid_token.split(".")

    # Flip middle characters in signature
    corrupted_sig = sig_b64[:10] + ("A" if sig_b64[10] != "A" else "B") + sig_b64[11:]
    corrupted_token = f"{header_b64}.{payload_b64}.{corrupted_sig}"

    res = await async_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {corrupted_token}"},
    )
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_adversarial_signature_truncation_and_garbage_rejected_401(async_client: AsyncClient):
    """
    Adversarial Probe: Truncated signature, appended garbage, and missing signature.
    All must be rejected with HTTP 401.
    """
    valid_token = make_officer_token("OFF-IO-TRUNC", "TN-STATE")
    header_b64, payload_b64, sig_b64 = valid_token.split(".")

    # 1. Truncated signature (first 8 chars only)
    res1 = await async_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {header_b64}.{payload_b64}.{sig_b64[:8]}"},
    )
    assert res1.status_code == 401

    # 2. Appended garbage
    res2 = await async_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {header_b64}.{payload_b64}.{sig_b64}==GARBAGE99=="},
    )
    assert res2.status_code == 401

    # 3. Missing signature trailing dot
    res3 = await async_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {header_b64}.{payload_b64}."},
    )
    assert res3.status_code == 401

    # 4. Only two segments
    res4 = await async_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {header_b64}.{payload_b64}"},
    )
    assert res4.status_code == 401


@pytest.mark.asyncio
async def test_adversarial_unsupported_or_none_algorithm_rejected_401(async_client: AsyncClient):
    """
    Adversarial Probe: None algorithm attack (alg: 'none', alg: 'None', alg: 'NONE')
    with empty or omitted signature. The server must reject it with HTTP 401.
    """
    for none_alg in ["none", "None", "NONE"]:
        header = base64.urlsafe_b64encode(json.dumps({"alg": none_alg, "typ": "JWT"}).encode()).decode().rstrip("=")
        payload = base64.urlsafe_b64encode(json.dumps({
            "sub": "ATTACKER-NONE",
            "role": "ADMIN",
            "tenant_id": "TN-STATE",
            "exp": int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()),
        }).encode()).decode().rstrip("=")

        none_token = f"{header}.{payload}."
        res = await async_client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {none_token}"},
        )
        assert res.status_code == 401
        data = res.json()
        assert data["error"]["code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_adversarial_forged_hmac_secret_rejected_401(async_client: AsyncClient):
    """
    Adversarial Probe: Attacker signs a token with their own arbitrary HMAC secret.
    The server must reject it with HTTP 401.
    """
    forged_token = jwt.encode(
        {
            "sub": "ATTACKER-FORGE",
            "role": "ADMIN",
            "tenant_id": "TN-STATE",
            "exp": int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()),
        },
        "attacker-secret-key-that-does-not-match-server-key-12345",
        algorithm="HS256",
    )
    res = await async_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {forged_token}"},
    )
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "UNAUTHORIZED"


# ============================================================================
# 2. TOKEN EXPIRATION & TEMPORAL BOUNDARY PROBES
# ============================================================================

@pytest.mark.asyncio
async def test_adversarial_expired_token_rejected_401(async_client: AsyncClient):
    """
    Adversarial Probe: Craft an expired token (expired 30 seconds ago).
    Server must strictly reject with HTTP 401 and error indicating expiration.
    """
    expired_token = create_access_token(
        claims={"sub": "OFF-EXPIRED-IO", "role": "INVESTIGATING_OFFICER", "tenant_id": "TN-STATE"},
        expires_delta=timedelta(seconds=-30),
    )
    res = await async_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {expired_token}"},
    )
    assert res.status_code == 401
    data = res.json()
    assert data["error"]["code"] == "UNAUTHORIZED"
    assert "expired" in data["error"]["message"].lower()

    # Also test on protected mutation endpoint
    res_cases = await async_client.post(
        "/api/v1/cases",
        json={"fir_number": "FIR-EXP-001", "victim_reference": "V"},
        headers={"Authorization": f"Bearer {expired_token}"},
    )
    assert res_cases.status_code == 401


@pytest.mark.asyncio
async def test_adversarial_historical_expired_token_rejected_401(async_client: AsyncClient):
    """
    Adversarial Probe: Token expired 365 days in the past.
    Server must strictly reject with HTTP 401.
    """
    old_token = create_access_token(
        claims={"sub": "OFF-ANCIENT", "role": "ADMIN", "tenant_id": "TN-STATE"},
        expires_delta=timedelta(days=-365),
    )
    res = await async_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {old_token}"},
    )
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_adversarial_future_not_before_rejected_401(async_client: AsyncClient):
    """
    Adversarial Probe: Token with nbf (not before) set 2 hours in the future.
    Server must reject with HTTP 401.
    """
    future_nbf = int((datetime.now(timezone.utc) + timedelta(hours=2)).timestamp())
    token = create_access_token(
        claims={"sub": "OFF-NBF-FUTURE", "role": "INVESTIGATING_OFFICER", "tenant_id": "TN-STATE", "nbf": future_nbf},
    )
    res = await async_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "UNAUTHORIZED"


# ============================================================================
# 3. ALGORITHM CONFUSION ATTACKS
# ============================================================================

@pytest.mark.asyncio
async def test_adversarial_algorithm_confusion_hs256_with_rsa_public_key_rejected_401(
    async_client: AsyncClient,
    rsa_keypair,
):
    """
    Adversarial Probe (CVE-2015-9235 style Algorithm Confusion):
    When the server is configured to verify RS256 using an RSA public key, an attacker
    crafts a token with header alg='HS256' and manually signs it using the RSA public key
    (PEM bytes and PEM string) as the HMAC secret key.
    The server MUST NOT verify an HS256 token using the RSA public key.
    The server must reject the forged token with HTTP 401 Unauthorized.
    """
    import hmac
    import hashlib

    pem_private, pem_public = rsa_keypair
    jwt_auth_engine._test_rsa_public_key = pem_public

    try:
        # Helper to craft raw HMAC token without pyjwt key validation
        def craft_raw_hmac(payload: dict, secret: bytes, alg: str = "HS256") -> str:
            header_b64 = base64.urlsafe_b64encode(json.dumps({"alg": alg, "typ": "JWT"}).encode()).decode().rstrip("=")
            payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
            msg = f"{header_b64}.{payload_b64}".encode()
            sig = hmac.new(secret, msg, hashlib.sha256).digest()
            sig_b64 = base64.urlsafe_b64encode(sig).decode().rstrip("=")
            return f"{header_b64}.{payload_b64}.{sig_b64}"

        payload = {
            "sub": "ATTACKER-CONFUSION-1",
            "role": "ADMIN",
            "tenant_id": "TN-STATE",
            "exp": int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()),
        }

        # 1. Attacker signs with public key PEM bytes as HMAC-SHA256 secret
        forged_hs256_bytes = craft_raw_hmac(payload, pem_public, alg="HS256")

        res1 = await async_client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {forged_hs256_bytes}"},
        )
        assert res1.status_code == 401
        assert res1.json()["error"]["code"] == "UNAUTHORIZED"

        # 2. Attacker signs with public key PEM string as HMAC-SHA256 secret
        forged_hs256_str = craft_raw_hmac(payload, pem_public.decode("utf-8").encode("utf-8"), alg="HS256")

        res2 = await async_client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {forged_hs256_str}"},
        )
        assert res2.status_code == 401
        assert res2.json()["error"]["code"] == "UNAUTHORIZED"

        # 3. Attempt case creation with the forged token
        res3 = await async_client.post(
            "/api/v1/cases",
            json={"fir_number": "FIR-ATTACK-CONFUSION", "victim_reference": "Attacker Target"},
            headers={"Authorization": f"Bearer {forged_hs256_str}"},
        )
        assert res3.status_code == 401
        assert res3.json()["error"]["code"] == "UNAUTHORIZED"

    finally:
        jwt_auth_engine._test_rsa_public_key = None


@pytest.mark.asyncio
async def test_adversarial_algorithm_confusion_rs256_with_hmac_signature_rejected_401(
    async_client: AsyncClient,
    rsa_keypair,
):
    """
    Adversarial Probe: Token header claims alg='RS256', but the signature was generated
    via HMAC-SHA256 using the HMAC secret or public key. The server's RSA verification
    must fail and return HTTP 401.
    """
    pem_private, pem_public = rsa_keypair
    jwt_auth_engine._test_rsa_public_key = pem_public

    try:
        header = base64.urlsafe_b64encode(json.dumps({"alg": "RS256", "typ": "JWT"}).encode()).decode().rstrip("=")
        payload = base64.urlsafe_b64encode(json.dumps({
            "sub": "ATTACKER-HMAC-RS256",
            "role": "ADMIN",
            "tenant_id": "TN-STATE",
            "exp": int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()),
        }).encode()).decode().rstrip("=")

        # Generate HMAC signature over header.payload
        import hmac
        import hashlib
        msg = f"{header}.{payload}".encode()
        hmac_sig = hmac.new(settings.jwt_secret_key_value.encode(), msg, hashlib.sha256).digest()
        hmac_sig_b64 = base64.urlsafe_b64encode(hmac_sig).decode().rstrip("=")

        crafted_token = f"{header}.{payload}.{hmac_sig_b64}"

        res = await async_client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {crafted_token}"},
        )
        assert res.status_code == 401
        assert res.json()["error"]["code"] == "UNAUTHORIZED"
    finally:
        jwt_auth_engine._test_rsa_public_key = None


@pytest.mark.asyncio
async def test_adversarial_algorithm_confusion_alternate_hmac_variants_rejected_401(
    async_client: AsyncClient,
    rsa_keypair,
):
    """
    Adversarial Probe: Attacker tries HS384 or HS512 with public key as secret.
    The server must reject with HTTP 401 (unsupported algorithm / invalid signature).
    """
    import hmac
    import hashlib

    pem_private, pem_public = rsa_keypair
    jwt_auth_engine._test_rsa_public_key = pem_public

    try:
        for alg, hash_fn in [("HS384", hashlib.sha384), ("HS512", hashlib.sha512)]:
            header_b64 = base64.urlsafe_b64encode(json.dumps({"alg": alg, "typ": "JWT"}).encode()).decode().rstrip("=")
            payload_b64 = base64.urlsafe_b64encode(json.dumps({
                "sub": f"ATTACKER-{alg}",
                "role": "ADMIN",
                "tenant_id": "TN-STATE",
                "exp": int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()),
            }).encode()).decode().rstrip("=")
            msg = f"{header_b64}.{payload_b64}".encode()
            sig = hmac.new(pem_public, msg, hash_fn).digest()
            sig_b64 = base64.urlsafe_b64encode(sig).decode().rstrip("=")
            token = f"{header_b64}.{payload_b64}.{sig_b64}"

            res = await async_client.get(
                "/api/v1/auth/me",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert res.status_code == 401
            assert res.json()["error"]["code"] == "UNAUTHORIZED"
    finally:
        jwt_auth_engine._test_rsa_public_key = None


@pytest.mark.asyncio
async def test_adversarial_forged_rsa_token_with_unregistered_private_key_rejected_401(
    async_client: AsyncClient,
    rsa_keypair,
):
    """
    Adversarial Probe: Attacker signs a token with a newly generated, attacker-controlled RSA private key.
    The server verifies using its legitimate public key, which must fail with HTTP 401.
    """
    server_private, server_public = rsa_keypair
    jwt_auth_engine._test_rsa_public_key = server_public

    try:
        # Attacker creates their own RSA key
        attacker_priv = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        attacker_pem = attacker_priv.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )

        forged_rsa_token = jwt.encode(
            {
                "sub": "ATTACKER-FORGED-RSA",
                "role": "ADMIN",
                "tenant_id": "TN-STATE",
                "exp": int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()),
            },
            attacker_pem,
            algorithm="RS256",
        )

        res = await async_client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {forged_rsa_token}"},
        )
        assert res.status_code == 401
        assert res.json()["error"]["code"] == "UNAUTHORIZED"
    finally:
        jwt_auth_engine._test_rsa_public_key = None


# ============================================================================
# 4. CROSS-TENANT IDOR ATTACKS (TN-STATE vs DL-POLICE)
# ============================================================================

@pytest.mark.asyncio
async def test_adversarial_cross_tenant_idor_full_lifecycle(async_client: AsyncClient):
    """
    Adversarial Probe:
    Tenant A ("TN-STATE") creates a high-profile cyber fraud case with victim details.
    Tenant B ("DL-POLICE") attempts comprehensive cross-tenant operations:
    1. GET /api/v1/cases/{case_a_id} -> strict 404 (no entity existence leakage)
    2. PATCH /api/v1/cases/{case_a_id} -> strict 404
    3. DELETE /api/v1/cases/{case_a_id} -> strict 404
    4. POST /api/v1/cases/{case_a_id}/notes -> strict 404
    5. GET /api/v1/cases/{case_a_id}/traces -> strict 404
    6. POST /api/v1/traces (with case_id=case_a_id) -> strict 404
    7. GET /api/v1/cases/{case_a_id}/reports -> strict 404
    8. POST /api/v1/cases/{case_a_id}/reports/dossier -> strict 404
    9. POST /api/v1/cases/{case_a_id}/reports/bnss94 -> strict 404
    10. GET /api/v1/cases/{case_a_id}/findings -> strict 404
    11. GET /api/v1/cases/{case_a_id}/audit -> strict 404
    12. POST /api/v1/cases/{case_a_id}/audit -> strict 404
    """
    token_tn = make_officer_token("OFF-TN-CHALLENGER", "TN-STATE", role="INVESTIGATING_OFFICER")
    token_dl = make_officer_token("OFF-DL-ATTACKER", "DL-POLICE", role="INVESTIGATING_OFFICER")
    token_dl_admin = make_officer_token("OFF-DL-ADMIN", "DL-POLICE", role="ADMIN")

    # Step 1: Tenant A ("TN-STATE") creates a case
    create_res = await async_client.post(
        "/api/v1/cases",
        json={
            "fir_number": "FIR-2026-TN-CONFIDENTIAL-007",
            "victim_reference": "Industrial Syndicate Victim",
            "loss_amount_inr": 25000000.0,
            "ack_number": "ACK-TN-1930-9999",
            "suspect_wallet": "TMuA6YqfCeX8EhbfYEg5y7S4Dqz9Dw92eP",
            "chain": "TRON",
            "asset": "USDT",
            "notes": "Top secret intelligence notes under Tamil Nadu jurisdiction.",
        },
        headers={"Authorization": f"Bearer {token_tn}"},
    )
    assert create_res.status_code == 201
    case_a_id = create_res.json()["id"]

    # Step 2: Tenant B ("DL-POLICE") attempts GET /api/v1/cases/{case_a_id}
    get_res = await async_client.get(
        f"/api/v1/cases/{case_a_id}",
        headers={"Authorization": f"Bearer {token_dl}"},
    )
    assert get_res.status_code == 404, f"Expected strict 404, got {get_res.status_code}"
    assert get_res.json()["error"]["code"] == "NOT_FOUND"

    # Step 3: Tenant B attempts PATCH /api/v1/cases/{case_a_id}
    patch_res = await async_client.patch(
        f"/api/v1/cases/{case_a_id}",
        json={"status": "CLOSED", "notes": "Tampered by DL-POLICE"},
        headers={"Authorization": f"Bearer {token_dl}"},
    )
    assert patch_res.status_code == 404
    assert patch_res.json()["error"]["code"] == "NOT_FOUND"

    # Step 4: Tenant B (even as ADMIN in DL-POLICE) attempts DELETE /api/v1/cases/{case_a_id}
    del_res = await async_client.delete(
        f"/api/v1/cases/{case_a_id}",
        headers={"Authorization": f"Bearer {token_dl_admin}"},
    )
    assert del_res.status_code == 404
    assert del_res.json()["error"]["code"] == "NOT_FOUND"

    # Step 5: Tenant B attempts POST /api/v1/cases/{case_a_id}/notes
    note_res = await async_client.post(
        f"/api/v1/cases/{case_a_id}/notes",
        json={"note": "Malicious injected note", "author": "Hacker"},
        headers={"Authorization": f"Bearer {token_dl}"},
    )
    assert note_res.status_code == 404
    assert note_res.json()["error"]["code"] == "NOT_FOUND"

    # Step 6: Tenant B attempts GET /api/v1/cases/{case_a_id}/traces
    traces_res = await async_client.get(
        f"/api/v1/cases/{case_a_id}/traces",
        headers={"Authorization": f"Bearer {token_dl}"},
    )
    assert traces_res.status_code == 404
    assert traces_res.json()["error"]["code"] == "NOT_FOUND"

    # Step 7: Tenant B attempts POST /api/v1/traces referencing Tenant A's case
    post_trace_res = await async_client.post(
        "/api/v1/traces",
        json={
            "case_id": case_a_id,
            "chain": "TRON",
            "input": "TYDZSxdBzWnCuB4jF3K6j5X3qW7b9X1234",
            "execution_mode": "DEMO",
        },
        headers={"Authorization": f"Bearer {token_dl}"},
    )
    assert post_trace_res.status_code == 404
    assert post_trace_res.json()["error"]["code"] == "NOT_FOUND"

    # Step 8: Tenant B attempts GET /api/v1/cases/{case_a_id}/reports
    rep_list_res = await async_client.get(
        f"/api/v1/cases/{case_a_id}/reports",
        headers={"Authorization": f"Bearer {token_dl}"},
    )
    assert rep_list_res.status_code == 404
    assert rep_list_res.json()["error"]["code"] == "NOT_FOUND"

    # Step 9: Tenant B attempts POST /api/v1/cases/{case_a_id}/reports/dossier
    dossier_res = await async_client.post(
        f"/api/v1/cases/{case_a_id}/reports/dossier",
        json={
            "trace_id": "dummy-trace-id",
            "investigator_name": "DL Attacker",
            "investigator_rank": "Inspector",
            "police_station": "DL-PS-1",
        },
        headers={"Authorization": f"Bearer {token_dl}"},
    )
    assert dossier_res.status_code == 404
    assert dossier_res.json()["error"]["code"] == "NOT_FOUND"

    # Step 10: Tenant B attempts POST /api/v1/cases/{case_a_id}/reports/bnss94
    bnss_res = await async_client.post(
        f"/api/v1/cases/{case_a_id}/reports/bnss94",
        json={
            "trace_id": "dummy-trace-id",
            "investigator_name": "DL Attacker",
            "investigator_rank": "Inspector",
            "police_station": "DL-PS-1",
        },
        headers={"Authorization": f"Bearer {token_dl}"},
    )
    assert bnss_res.status_code == 404
    assert bnss_res.json()["error"]["code"] == "NOT_FOUND"

    # Step 11: Tenant B attempts GET /api/v1/cases/{case_a_id}/findings
    find_res = await async_client.get(
        f"/api/v1/cases/{case_a_id}/findings",
        headers={"Authorization": f"Bearer {token_dl}"},
    )
    assert find_res.status_code == 404
    assert find_res.json()["error"]["code"] == "NOT_FOUND"

    # Step 12: Tenant B attempts GET /api/v1/cases/{case_a_id}/audit
    audit_get = await async_client.get(
        f"/api/v1/cases/{case_a_id}/audit",
        headers={"Authorization": f"Bearer {token_dl}"},
    )
    assert audit_get.status_code == 404
    assert audit_get.json()["error"]["code"] == "NOT_FOUND"

    # Step 13: Tenant B attempts POST /api/v1/cases/{case_a_id}/audit
    audit_post = await async_client.post(
        f"/api/v1/cases/{case_a_id}/audit",
        json={
            "actor_id": "OFF-DL-ATTACKER",
            "event_type": "CASE_CREATED",
            "action_summary": "Malicious audit insertion",
        },
        headers={"Authorization": f"Bearer {token_dl}"},
    )
    assert audit_post.status_code == 404
    assert audit_post.json()["error"]["code"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_adversarial_cross_tenant_report_download_idor_defense(async_client: AsyncClient):
    """
    Adversarial Probe:
    Tenant A ("TN-STATE") runs a trace and generates an official Section 63 BSA Forensic Dossier.
    Tenant B ("DL-POLICE") attempts to download the confidential PDF via /api/v1/reports/{report_id}/download.
    The server MUST return strict HTTP 404 Not Found (blocking IDOR and entity enumeration).
    """
    token_tn = make_officer_token("OFF-TN-REP", "TN-STATE", role="INVESTIGATING_OFFICER")
    token_dl = make_officer_token("OFF-DL-REP", "DL-POLICE", role="INVESTIGATING_OFFICER")

    # 1. Create case as TN-STATE
    case_res = await async_client.post(
        "/api/v1/cases",
        json={"fir_number": "FIR-2026-TN-REP-001", "victim_reference": "Confidential Commercial Bank"},
        headers={"Authorization": f"Bearer {token_tn}"},
    )
    case_id = case_res.json()["id"]

    # 2. Run trace as TN-STATE (using canonical demo address)
    trace_res = await async_client.post(
        "/api/v1/traces",
        json={
            "case_id": case_id,
            "chain": "TRON",
            "input": "TYDZSxdBzWnCuB4jF3K6j5X3qW7b9X1234",
            "execution_mode": "DEMO",
        },
        headers={"Authorization": f"Bearer {token_tn}"},
    )
    assert trace_res.status_code == 201
    trace_id = trace_res.json()["trace_id"]

    # 3. Generate Section 63 BSA Dossier as TN-STATE
    dossier_res = await async_client.post(
        f"/api/v1/cases/{case_id}/reports/dossier",
        json={
            "trace_id": trace_id,
            "investigator_name": "Inspector S. Raman",
            "investigator_rank": "Inspector of Police",
            "police_station": "Cyber Crime PS, Chennai",
        },
        headers={"Authorization": f"Bearer {token_tn}"},
    )
    assert dossier_res.status_code == 201
    report_id = dossier_res.json()["id"]

    # 4. Legitimate officer in TN-STATE downloads report -> 200 OK
    legit_dl = await async_client.get(
        f"/api/v1/reports/{report_id}/download",
        headers={"Authorization": f"Bearer {token_tn}"},
    )
    assert legit_dl.status_code == 200
    assert legit_dl.headers.get("content-type") == "application/pdf"

    # 5. Attacker in DL-POLICE attempts to download report -> Strict 404 NOT_FOUND!
    attack_dl = await async_client.get(
        f"/api/v1/reports/{report_id}/download",
        headers={"Authorization": f"Bearer {token_dl}"},
    )
    assert attack_dl.status_code == 404
    assert attack_dl.json()["error"]["code"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_adversarial_cross_tenant_trace_and_graph_idor_defense(async_client: AsyncClient):
    """
    Adversarial Probe:
    Tenant A ("TN-STATE") initiates a trace.
    Tenant B ("DL-POLICE") attempts to access:
    - /api/v1/traces/{trace_id}
    - /api/v1/traces/{trace_id}/graph
    - /api/v1/traces/{trace_id}/evidence
    - /api/v1/traces/{trace_id}/attribution
    All must return strict HTTP 404 Not Found.
    """
    token_tn = make_officer_token("OFF-TN-TRACE", "TN-STATE")
    token_dl = make_officer_token("OFF-DL-TRACE", "DL-POLICE")

    # Create Case & Trace in TN-STATE
    c_res = await async_client.post(
        "/api/v1/cases",
        json={"fir_number": "FIR-2026-TN-TRACE-001", "victim_reference": "Victim TN"},
        headers={"Authorization": f"Bearer {token_tn}"},
    )
    case_id = c_res.json()["id"]

    t_res = await async_client.post(
        "/api/v1/traces",
        json={
            "case_id": case_id,
            "chain": "TRON",
            "input": "TYDZSxdBzWnCuB4jF3K6j5X3qW7b9X1234",
            "execution_mode": "DEMO",
        },
        headers={"Authorization": f"Bearer {token_tn}"},
    )
    trace_id = t_res.json()["trace_id"]

    # DL-POLICE probes trace status
    res_status = await async_client.get(f"/api/v1/traces/{trace_id}", headers={"Authorization": f"Bearer {token_dl}"})
    assert res_status.status_code == 404

    # DL-POLICE probes graph
    res_graph = await async_client.get(f"/api/v1/traces/{trace_id}/graph", headers={"Authorization": f"Bearer {token_dl}"})
    assert res_graph.status_code == 404

    # DL-POLICE probes evidence
    res_ev = await async_client.get(f"/api/v1/traces/{trace_id}/evidence", headers={"Authorization": f"Bearer {token_dl}"})
    assert res_ev.status_code == 404

    # DL-POLICE probes attribution
    res_attr = await async_client.get(f"/api/v1/traces/{trace_id}/attribution", headers={"Authorization": f"Bearer {token_dl}"})
    assert res_attr.status_code == 404


@pytest.mark.asyncio
async def test_adversarial_cross_tenant_listing_strict_isolation(async_client: AsyncClient):
    """
    Adversarial Probe:
    Ensure cases created across two tenants ("TN-STATE" and "DL-POLICE") never leak
    into the list endpoint of the other tenant under any pagination parameters.
    """
    token_tn = make_officer_token("OFF-TN-LIST", "TN-STATE")
    token_dl = make_officer_token("OFF-DL-LIST", "DL-POLICE")

    tn_cases = []
    for i in range(3):
        r = await async_client.post(
            "/api/v1/cases",
            json={"fir_number": f"FIR-TN-MULTI-{i}", "victim_reference": f"TN-Victim-{i}"},
            headers={"Authorization": f"Bearer {token_tn}"},
        )
        assert r.status_code == 201
        tn_cases.append(r.json()["id"])

    dl_cases = []
    for i in range(3):
        r = await async_client.post(
            "/api/v1/cases",
            json={"fir_number": f"FIR-DL-MULTI-{i}", "victim_reference": f"DL-Victim-{i}"},
            headers={"Authorization": f"Bearer {token_dl}"},
        )
        assert r.status_code == 201
        dl_cases.append(r.json()["id"])

    # Query list as TN-STATE
    list_tn = await async_client.get("/api/v1/cases?limit=100", headers={"Authorization": f"Bearer {token_tn}"})
    assert list_tn.status_code == 200
    returned_tn = [c["id"] for c in list_tn.json()["cases"]]
    for cid in tn_cases:
        assert cid in returned_tn
    for cid in dl_cases:
        assert cid not in returned_tn, f"DL case {cid} leaked to TN tenant!"

    # Query list as DL-POLICE
    list_dl = await async_client.get("/api/v1/cases?limit=100", headers={"Authorization": f"Bearer {token_dl}"})
    assert list_dl.status_code == 200
    returned_dl = [c["id"] for c in list_dl.json()["cases"]]
    for cid in dl_cases:
        assert cid in returned_dl
    for cid in tn_cases:
        assert cid not in returned_dl, f"TN case {cid} leaked to DL tenant!"


@pytest.mark.asyncio
async def test_adversarial_cross_tenant_persistence_immutability_under_attack(
    async_client: AsyncClient,
    test_engine,
):
    """
    Adversarial Probe:
    After all cross-tenant attack attempts by DL-POLICE, verify in the underlying database
    that TN-STATE's case record remains exactly intact, unmutated, and undeleted.
    """
    token_tn = make_officer_token("OFF-TN-INTEGRITY", "TN-STATE")
    token_dl = make_officer_token("OFF-DL-ATTACK-IMMUTABLE", "DL-POLICE")

    # Create Case in TN-STATE
    res = await async_client.post(
        "/api/v1/cases",
        json={
            "fir_number": "FIR-2026-TN-IMMUTABLE-001",
            "victim_reference": "Immutable Victim Record",
            "notes": "Original uncorrupted notes.",
        },
        headers={"Authorization": f"Bearer {token_tn}"},
    )
    case_id = res.json()["id"]

    # DL-POLICE executes hostile attacks
    await async_client.patch(
        f"/api/v1/cases/{case_id}",
        json={"status": "CLOSED", "notes": "HACKED"},
        headers={"Authorization": f"Bearer {token_dl}"},
    )
    await async_client.delete(
        f"/api/v1/cases/{case_id}",
        headers={"Authorization": f"Bearer {token_dl}"},
    )
    await async_client.post(
        f"/api/v1/cases/{case_id}/notes",
        json={"note": "HACKED NOTE"},
        headers={"Authorization": f"Bearer {token_dl}"},
    )

    # Directly verify in DB that the record was not touched
    session_factory = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        case = await session.get(Case, case_id)
        assert case is not None
        assert case.fir_number == "FIR-2026-TN-IMMUTABLE-001"
        assert case.status == "OPEN"
        assert case.victim_reference == "Immutable Victim Record"
        assert "Original uncorrupted notes." in case.notes
        assert "HACKED" not in case.notes


# ============================================================================
# 5. PRIVILEGE ESCALATION & RBAC BOUNDARY PROBES
# ============================================================================

@pytest.mark.asyncio
async def test_adversarial_privilege_escalation_auditor_case_creation_rejected_403(async_client: AsyncClient):
    """
    Adversarial Probe: Authenticate with role='AUDITOR' and attempt POST /api/v1/cases.
    The server must strictly reject with HTTP 403 Forbidden.
    """
    token_auditor = make_officer_token("OFF-AUD-ESC-1", "TN-STATE", role="AUDITOR")
    res = await async_client.post(
        "/api/v1/cases",
        json={"fir_number": "FIR-AUD-ILLEGAL", "victim_reference": "Illegal Creation"},
        headers={"Authorization": f"Bearer {token_auditor}"},
    )
    assert res.status_code == 403, f"Expected 403 Forbidden, got {res.status_code}"
    data = res.json()
    assert data["error"]["code"] == "FORBIDDEN"
    assert "not authorized" in data["error"]["message"]


@pytest.mark.asyncio
async def test_adversarial_privilege_escalation_auditor_trace_creation_rejected_403(async_client: AsyncClient):
    """
    Adversarial Probe: Authenticate with role='AUDITOR' and attempt POST /api/v1/traces.
    The server must strictly reject with HTTP 403 Forbidden.
    """
    token_auditor = make_officer_token("OFF-AUD-ESC-2", "TN-STATE", role="AUDITOR")
    res = await async_client.post(
        "/api/v1/traces",
        json={
            "case_id": "any-case-id",
            "chain": "TRON",
            "input": "TYDZSxdBzWnCuB4jF3K6j5X3qW7b9X1234",
        },
        headers={"Authorization": f"Bearer {token_auditor}"},
    )
    assert res.status_code == 403
    assert res.json()["error"]["code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_adversarial_privilege_escalation_auditor_case_deletion_rejected_403(async_client: AsyncClient):
    """
    Adversarial Probe: Authenticate with role='AUDITOR' and attempt DELETE /api/v1/cases/{id}.
    The server must strictly reject with HTTP 403 Forbidden.
    """
    token_io = make_officer_token("OFF-IO-FOR-AUD", "TN-STATE", role="INVESTIGATING_OFFICER")
    token_auditor = make_officer_token("OFF-AUD-ESC-3", "TN-STATE", role="AUDITOR")

    # Create legitimate case
    create_res = await async_client.post(
        "/api/v1/cases",
        json={"fir_number": "FIR-AUD-DELETE-TARGET", "victim_reference": "Auditor Target"},
        headers={"Authorization": f"Bearer {token_io}"},
    )
    case_id = create_res.json()["id"]

    # Auditor attempts DELETE
    del_res = await async_client.delete(
        f"/api/v1/cases/{case_id}",
        headers={"Authorization": f"Bearer {token_auditor}"},
    )
    assert del_res.status_code == 403
    assert del_res.json()["error"]["code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_adversarial_privilege_escalation_auditor_case_mutation_rejected_403(async_client: AsyncClient):
    """
    Adversarial Probe: Authenticate with role='AUDITOR' and attempt PATCH and POST /notes.
    The server must strictly reject both with HTTP 403 Forbidden.
    """
    token_io = make_officer_token("OFF-IO-FOR-MUT", "TN-STATE", role="INVESTIGATING_OFFICER")
    token_auditor = make_officer_token("OFF-AUD-ESC-4", "TN-STATE", role="AUDITOR")

    create_res = await async_client.post(
        "/api/v1/cases",
        json={"fir_number": "FIR-AUD-MUT-TARGET", "victim_reference": "Mut Target"},
        headers={"Authorization": f"Bearer {token_io}"},
    )
    case_id = create_res.json()["id"]

    # Auditor attempts PATCH
    patch_res = await async_client.patch(
        f"/api/v1/cases/{case_id}",
        json={"status": "CLOSED"},
        headers={"Authorization": f"Bearer {token_auditor}"},
    )
    assert patch_res.status_code == 403
    assert patch_res.json()["error"]["code"] == "FORBIDDEN"

    # Auditor attempts add note
    note_res = await async_client.post(
        f"/api/v1/cases/{case_id}/notes",
        json={"note": "Auditor note"},
        headers={"Authorization": f"Bearer {token_auditor}"},
    )
    assert note_res.status_code == 403
    assert note_res.json()["error"]["code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_adversarial_privilege_escalation_auditor_report_generation_rejected_403(async_client: AsyncClient):
    """
    Adversarial Probe: Authenticate with role='AUDITOR' and attempt generating legal reports:
    - POST /cases/{id}/reports/dossier -> 403
    - POST /cases/{id}/reports/bnss94 -> 403
    """
    token_io = make_officer_token("OFF-IO-FOR-REP", "TN-STATE", role="INVESTIGATING_OFFICER")
    token_auditor = make_officer_token("OFF-AUD-ESC-5", "TN-STATE", role="AUDITOR")

    create_res = await async_client.post(
        "/api/v1/cases",
        json={"fir_number": "FIR-AUD-REP-TARGET", "victim_reference": "Rep Target"},
        headers={"Authorization": f"Bearer {token_io}"},
    )
    case_id = create_res.json()["id"]

    # Auditor attempts dossier generation
    dossier_res = await async_client.post(
        f"/api/v1/cases/{case_id}/reports/dossier",
        json={"trace_id": "dummy-trace", "investigator_name": "Auditor Name"},
        headers={"Authorization": f"Bearer {token_auditor}"},
    )
    assert dossier_res.status_code == 403
    assert dossier_res.json()["error"]["code"] == "FORBIDDEN"

    # Auditor attempts BNSS 94 generation
    bnss_res = await async_client.post(
        f"/api/v1/cases/{case_id}/reports/bnss94",
        json={"trace_id": "dummy-trace", "investigator_name": "Auditor Name"},
        headers={"Authorization": f"Bearer {token_auditor}"},
    )
    assert bnss_res.status_code == 403
    assert bnss_res.json()["error"]["code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_adversarial_privilege_escalation_auditor_audit_and_finding_mutation_rejected_403(async_client: AsyncClient):
    """
    Adversarial Probe: Authenticate with role='AUDITOR' and attempt mutating audit logs or reviewing findings:
    - POST /cases/{id}/audit -> 403
    - POST /cases/{id}/findings/{id}/review -> 403
    """
    token_io = make_officer_token("OFF-IO-FOR-AUDIT-MUT", "TN-STATE", role="INVESTIGATING_OFFICER")
    token_auditor = make_officer_token("OFF-AUD-ESC-6", "TN-STATE", role="AUDITOR")

    create_res = await async_client.post(
        "/api/v1/cases",
        json={"fir_number": "FIR-AUDIT-MUT-TARGET", "victim_reference": "Audit Target"},
        headers={"Authorization": f"Bearer {token_io}"},
    )
    case_id = create_res.json()["id"]

    # Auditor attempts audit log injection
    audit_res = await async_client.post(
        f"/api/v1/cases/{case_id}/audit",
        json={"actor_id": "AUDITOR", "event_type": "CASE_CREATED", "action_summary": "Injected by Auditor"},
        headers={"Authorization": f"Bearer {token_auditor}"},
    )
    assert audit_res.status_code == 403
    assert audit_res.json()["error"]["code"] == "FORBIDDEN"

    # Auditor attempts finding review
    find_res = await async_client.post(
        f"/api/v1/cases/{case_id}/findings/some-finding-id/review",
        json={"status": "REVIEWED", "notes": "Auditor review"},
        headers={"Authorization": f"Bearer {token_auditor}"},
    )
    assert find_res.status_code == 403
    assert find_res.json()["error"]["code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_adversarial_privilege_escalation_auditor_read_only_access_permitted(async_client: AsyncClient):
    """
    Adversarial Probe: Verify that role='AUDITOR' is permitted full read-only visibility
    into their tenant's data:
    - GET /api/v1/cases -> 200
    - GET /api/v1/cases/{id} -> 200
    - GET /api/v1/cases/{id}/traces -> 200
    - GET /api/v1/cases/{id}/reports -> 200
    - GET /api/v1/cases/{id}/findings -> 200
    - GET /api/v1/cases/{id}/audit -> 200
    """
    token_io = make_officer_token("OFF-IO-FOR-READ", "TN-STATE", role="INVESTIGATING_OFFICER")
    token_auditor = make_officer_token("OFF-AUD-READ", "TN-STATE", role="AUDITOR")

    create_res = await async_client.post(
        "/api/v1/cases",
        json={"fir_number": "FIR-AUD-READ-VERIFY", "victim_reference": "Read Verify"},
        headers={"Authorization": f"Bearer {token_io}"},
    )
    case_id = create_res.json()["id"]

    # 1. Auditor lists cases
    r_list = await async_client.get("/api/v1/cases", headers={"Authorization": f"Bearer {token_auditor}"})
    assert r_list.status_code == 200

    # 2. Auditor retrieves specific case
    r_get = await async_client.get(f"/api/v1/cases/{case_id}", headers={"Authorization": f"Bearer {token_auditor}"})
    assert r_get.status_code == 200
    assert r_get.json()["id"] == case_id

    # 3. Auditor reads traces
    r_traces = await async_client.get(f"/api/v1/cases/{case_id}/traces", headers={"Authorization": f"Bearer {token_auditor}"})
    assert r_traces.status_code == 200

    # 4. Auditor reads reports
    r_reports = await async_client.get(f"/api/v1/cases/{case_id}/reports", headers={"Authorization": f"Bearer {token_auditor}"})
    assert r_reports.status_code == 200

    # 5. Auditor reads findings
    r_findings = await async_client.get(f"/api/v1/cases/{case_id}/findings", headers={"Authorization": f"Bearer {token_auditor}"})
    assert r_findings.status_code == 200

    # 6. Auditor reads audit logs
    r_audit = await async_client.get(f"/api/v1/cases/{case_id}/audit", headers={"Authorization": f"Bearer {token_auditor}"})
    assert r_audit.status_code == 200


@pytest.mark.asyncio
async def test_adversarial_role_manipulation_unknown_role_boundary(async_client: AsyncClient):
    """
    Adversarial Probe: Token contains arbitrary unknown role strings
    ('SUPER_ROOT', 'HACKER', 'SYSTEM_OPERATOR').
    By default normalize_role falls back to INVESTIGATING_OFFICER,
    which does not grant supervisor/admin privileges.
    """
    token_hacker = make_officer_token("OFF-HACKER", "TN-STATE", role="SUPER_ROOT")
    res = await async_client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token_hacker}"})
    assert res.status_code == 200
    data = res.json()
    # Canonical fallback is INVESTIGATING_OFFICER
    assert data["role"] == Role.INVESTIGATING_OFFICER.value


# ============================================================================
# 6. PRODUCTION ZERO-TRUST UNAUTHENTICATED PERIMETER GATE
# ============================================================================

@pytest.mark.asyncio
async def test_adversarial_production_mode_unauthenticated_request_rejected_401(async_client: AsyncClient):
    """
    Adversarial Probe: In APP_ENV='production', all endpoints must reject unauthenticated
    requests with HTTP 401 Unauthorized (never falling back to dev officer session).
    """
    orig_env = settings.APP_ENV
    try:
        settings.APP_ENV = "production"

        endpoints = [
            ("GET", "/api/v1/auth/me"),
            ("GET", "/api/v1/cases"),
            ("POST", "/api/v1/cases"),
            ("GET", "/api/v1/cases/some-case-id"),
            ("GET", "/api/v1/cases/some-case-id/traces"),
            ("POST", "/api/v1/traces"),
            ("GET", "/api/v1/traces/some-trace-id"),
            ("GET", "/api/v1/reports/some-report-id/download"),
        ]

        for method, path in endpoints:
            if method == "GET":
                res = await async_client.get(path)
            else:
                res = await async_client.post(path, json={})
            assert res.status_code == 401, f"{method} {path} returned {res.status_code}, expected 401"
            data = res.json()
            assert data["error"]["code"] == "UNAUTHORIZED"
            assert "Missing Authorization header" in data["error"]["message"]
    finally:
        settings.APP_ENV = orig_env


# ============================================================================
# 7. DPDP ACT 2023 AT-REST ENCRYPTION & RESILIENCE
# ============================================================================

@pytest.mark.asyncio
async def test_adversarial_dpdp_encryption_at_rest_in_raw_sql(
    async_client: AsyncClient,
    test_engine,
):
    """
    Adversarial Probe: Verify that sensitive PII (victim_reference, ack_number, notes)
    is stored exclusively as AES-256-GCM encrypted ciphertext at rest in raw SQL queries.
    Cleartext values must NEVER appear in the underlying database table.
    """
    token = make_officer_token("OFF-TN-DPDP", "TN-STATE")
    secret_victim = "SECRET-VICTIM-AADHAAR-890123456789"
    secret_notes = "CONFIDENTIAL-INTELLIGENCE: High-net-worth individual defrauded via fake TRC-20 arbitrage bot."
    secret_ack = "ACK-1930-SPECIAL-PRIV-991"

    # Create case via API
    res = await async_client.post(
        "/api/v1/cases",
        json={
            "fir_number": "FIR-2026-DPDP-RAW-001",
            "victim_reference": secret_victim,
            "ack_number": secret_ack,
            "notes": secret_notes,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 201
    case_id = res.json()["id"]

    # Read back via raw SQL bypass of ORM
    session_factory = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        result = await session.execute(
            text("SELECT victim_reference, ack_number, notes FROM cases WHERE id = :id"),
            {"id": case_id},
        )
        row = result.first()
        raw_victim, raw_ack, raw_notes = row[0], row[1], row[2]

        # Assert cleartext is completely absent from database columns
        assert secret_victim not in raw_victim, "Plaintext victim leaked into database column!"
        assert secret_ack not in raw_ack, "Plaintext ack_number leaked into database column!"
        assert secret_notes not in raw_notes, "Plaintext notes leaked into database column!"

        # Assert format is valid Base64 ciphertext
        for col_name, raw_val in [("victim_reference", raw_victim), ("ack_number", raw_ack), ("notes", raw_notes)]:
            try:
                decoded = base64.b64decode(raw_val)
                # AES-256-GCM payload: 12-byte nonce + ciphertext + 16-byte tag (min 28 bytes)
                assert len(decoded) >= 28, f"{col_name} ciphertext length ({len(decoded)}) too short for AES-GCM"
            except Exception as e:
                pytest.fail(f"Raw column {col_name} does not contain valid Base64 ciphertext: {e}")

    # Verify that API retrieves transparently decrypted values
    get_res = await async_client.get(f"/api/v1/cases/{case_id}", headers={"Authorization": f"Bearer {token}"})
    assert get_res.status_code == 200
    data = get_res.json()
    assert data["victim_reference"] == secret_victim
    assert data["ack_number"] == secret_ack
    assert data["notes"] == secret_notes


@pytest.mark.asyncio
async def test_adversarial_dpdp_corrupted_ciphertext_graceful_handling(
    async_client: AsyncClient,
    test_engine,
):
    """
    Adversarial Probe: If an attacker or corrupted storage damages ciphertext in the database,
    the application must not throw an unhandled 500 error when reading through ORM/API,
    but handle decryption failure gracefully.
    """
    token = make_officer_token("OFF-TN-CORRUPT", "TN-STATE")

    # Create Case
    res = await async_client.post(
        "/api/v1/cases",
        json={"fir_number": "FIR-2026-CORRUPT-TEST", "victim_reference": "To Be Corrupted"},
        headers={"Authorization": f"Bearer {token}"},
    )
    case_id = res.json()["id"]

    # Directly corrupt the database row with invalid ciphertext
    session_factory = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        await session.execute(
            text("UPDATE cases SET victim_reference = 'CORRUPTED_NON_BASE64_CIPHERTEXT' WHERE id = :id"),
            {"id": case_id},
        )
        await session.commit()

    # Query through API: should not crash the server
    get_res = await async_client.get(f"/api/v1/cases/{case_id}", headers={"Authorization": f"Bearer {token}"})
    assert get_res.status_code == 200
    # Decryption fallback returns the raw string if not decryptable without throwing an unhandled exception
    assert get_res.json()["victim_reference"] == "CORRUPTED_NON_BASE64_CIPHERTEXT"
