"""
Tests for Features 10 & 11: Multi-Tenancy Foundation, Tenant Partitioning & IDOR Defense.
Verifies that cross-tenant access returns HTTP 404 Not Found to prevent entity existence enumeration.
"""
import pytest
from httpx import AsyncClient

from backend.app.core.auth import create_access_token


def make_officer_token(officer_id: str, tenant_id: str, role: str = "INVESTIGATING_OFFICER") -> str:
    """Helper to generate JWT bearer token for a specific tenant and role."""
    return create_access_token(
        claims={
            "sub": officer_id,
            "role": role,
            "tenant_id": tenant_id,
            "district_id": f"{tenant_id}-DISTRICT",
            "police_station_id": f"{tenant_id}-PS-1",
        }
    )


@pytest.mark.asyncio
async def test_case_list_tenant_isolation(async_client: AsyncClient):
    """Cases created by Tenant TN are never visible in the case list of Tenant MH."""
    token_tn = make_officer_token("OFF-TN-1", "TN-STATE")
    token_mh = make_officer_token("OFF-MH-1", "MH-STATE")

    # Create Case in TN-STATE
    case_tn_res = await async_client.post(
        "/api/v1/cases",
        json={"fir_number": "FIR-TN-101", "victim_reference": "VICTIM-TN"},
        headers={"Authorization": f"Bearer {token_tn}"},
    )
    assert case_tn_res.status_code == 201
    case_tn_id = case_tn_res.json()["id"]

    # Create Case in MH-STATE
    case_mh_res = await async_client.post(
        "/api/v1/cases",
        json={"fir_number": "FIR-MH-202", "victim_reference": "VICTIM-MH"},
        headers={"Authorization": f"Bearer {token_mh}"},
    )
    assert case_mh_res.status_code == 201
    case_mh_id = case_mh_res.json()["id"]

    # List cases as TN
    tn_list_res = await async_client.get(
        "/api/v1/cases",
        headers={"Authorization": f"Bearer {token_tn}"},
    )
    assert tn_list_res.status_code == 200
    tn_cases = tn_list_res.json()["cases"]
    tn_ids = [c["id"] for c in tn_cases]
    assert case_tn_id in tn_ids
    assert case_mh_id not in tn_ids

    # List cases as MH
    mh_list_res = await async_client.get(
        "/api/v1/cases",
        headers={"Authorization": f"Bearer {token_mh}"},
    )
    assert mh_list_res.status_code == 200
    mh_cases = mh_list_res.json()["cases"]
    mh_ids = [c["id"] for c in mh_cases]
    assert case_mh_id in mh_ids
    assert case_tn_id not in mh_ids


@pytest.mark.asyncio
async def test_cross_tenant_case_lookup_returns_404_idor_defense(async_client: AsyncClient):
    """Direct lookup of Tenant A's case ID by Tenant B returns HTTP 404 (NOT 403) to prevent ID enumeration."""
    token_tn = make_officer_token("OFF-TN-1", "TN-STATE")
    token_mh = make_officer_token("OFF-MH-1", "MH-STATE")

    case_res = await async_client.post(
        "/api/v1/cases",
        json={"fir_number": "FIR-TN-PRIVATE", "victim_reference": "CONFIDENTIAL-TN"},
        headers={"Authorization": f"Bearer {token_tn}"},
    )
    case_id = case_res.json()["id"]

    # Tenant MH attempts to fetch Tenant TN's case
    cross_res = await async_client.get(
        f"/api/v1/cases/{case_id}",
        headers={"Authorization": f"Bearer {token_mh}"},
    )
    assert cross_res.status_code == 404
    data = cross_res.json()
    assert data["error"]["code"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_cross_tenant_case_mutation_returns_404(async_client: AsyncClient):
    """Attempts by Tenant B to update, append notes to, or delete Tenant A's case return HTTP 404."""
    token_tn = make_officer_token("OFF-TN-1", "TN-STATE")
    token_mh = make_officer_token("OFF-MH-1", "MH-STATE")

    case_res = await async_client.post(
        "/api/v1/cases",
        json={"fir_number": "FIR-TN-MUTATE", "victim_reference": "TN-TARGET"},
        headers={"Authorization": f"Bearer {token_tn}"},
    )
    case_id = case_res.json()["id"]

    # 1. Update attempt
    patch_res = await async_client.patch(
        f"/api/v1/cases/{case_id}",
        json={"status": "CLOSED"},
        headers={"Authorization": f"Bearer {token_mh}"},
    )
    assert patch_res.status_code == 404
    assert patch_res.json()["error"]["code"] == "NOT_FOUND"

    # 2. Add note attempt
    note_res = await async_client.post(
        f"/api/v1/cases/{case_id}/notes",
        json={"note": "Malicious cross-tenant note insertion"},
        headers={"Authorization": f"Bearer {token_mh}"},
    )
    assert note_res.status_code == 404
    assert note_res.json()["error"]["code"] == "NOT_FOUND"

    # 3. Delete attempt
    del_res = await async_client.delete(
        f"/api/v1/cases/{case_id}",
        headers={"Authorization": f"Bearer {token_mh}"},
    )
    assert del_res.status_code == 404
    assert del_res.json()["error"]["code"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_cross_tenant_trace_execution_prevented(async_client: AsyncClient):
    """Tenant B cannot start a trace against Tenant A's case ID (returns 404)."""
    token_tn = make_officer_token("OFF-TN-1", "TN-STATE")
    token_mh = make_officer_token("OFF-MH-1", "MH-STATE")

    case_res = await async_client.post(
        "/api/v1/cases",
        json={"fir_number": "FIR-TN-TRACE", "victim_reference": "TN-TRACE-VICTIM"},
        headers={"Authorization": f"Bearer {token_tn}"},
    )
    case_id = case_res.json()["id"]

    # Tenant MH attempts to execute trace under Tenant TN's case
    trace_res = await async_client.post(
        "/api/v1/traces",
        json={
            "case_id": case_id,
            "chain": "TRON",
            "input": "TYDZSxdBzWnCuB4jF3K6j5X3qW7b9X1234",
            "execution_mode": "DEMO",
        },
        headers={"Authorization": f"Bearer {token_mh}"},
    )
    assert trace_res.status_code == 404
    assert trace_res.json()["error"]["code"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_cross_tenant_trace_lookup_returns_404(async_client: AsyncClient):
    """Tenant B cannot view trace status, graph, or attribution of Tenant A's trace (returns 404)."""
    token_tn = make_officer_token("OFF-TN-1", "TN-STATE")
    token_mh = make_officer_token("OFF-MH-1", "MH-STATE")

    case_res = await async_client.post(
        "/api/v1/cases",
        json={"fir_number": "FIR-TN-FOR-TRACE", "victim_reference": "TN-TRACE-TARGET"},
        headers={"Authorization": f"Bearer {token_tn}"},
    )
    case_id = case_res.json()["id"]

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

    # Tenant MH attempts to fetch trace status
    t_status = await async_client.get(
        f"/api/v1/traces/{trace_id}",
        headers={"Authorization": f"Bearer {token_mh}"},
    )
    assert t_status.status_code == 404
    assert t_status.json()["error"]["code"] == "NOT_FOUND"

    # Tenant MH attempts to fetch graph
    t_graph = await async_client.get(
        f"/api/v1/traces/{trace_id}/graph",
        headers={"Authorization": f"Bearer {token_mh}"},
    )
    assert t_graph.status_code == 404
    assert t_graph.json()["error"]["code"] == "NOT_FOUND"

    # Tenant MH attempts to fetch attribution
    t_attr = await async_client.get(
        f"/api/v1/traces/{trace_id}/attribution",
        headers={"Authorization": f"Bearer {token_mh}"},
    )
    assert t_attr.status_code == 404
    assert t_attr.json()["error"]["code"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_cross_tenant_report_download_idor_defense(async_client: AsyncClient):
    """Tenant B cannot download confidential PDF reports generated by Tenant A (returns 404)."""
    token_tn = make_officer_token("OFF-TN-1", "TN-STATE")
    token_mh = make_officer_token("OFF-MH-1", "MH-STATE")

    case_res = await async_client.post(
        "/api/v1/cases",
        json={"fir_number": "FIR-TN-REPORT-SEC", "victim_reference": "SECRET-VICTIM"},
        headers={"Authorization": f"Bearer {token_tn}"},
    )
    case_id = case_res.json()["id"]

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
    trace_id = trace_res.json()["trace_id"]

    dossier_res = await async_client.post(
        f"/api/v1/cases/{case_id}/reports/dossier",
        json={
            "trace_id": trace_id,
            "investigator_name": "Inspector TN",
            "investigator_rank": "Inspector",
            "police_station": "PS-TN",
        },
        headers={"Authorization": f"Bearer {token_tn}"},
    )
    assert dossier_res.status_code == 201
    report_id = dossier_res.json()["id"]

    # Tenant MH tries to download Tenant TN's report
    download_res = await async_client.get(
        f"/api/v1/reports/{report_id}/download",
        headers={"Authorization": f"Bearer {token_mh}"},
    )
    assert download_res.status_code == 404
    assert download_res.json()["error"]["code"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_cross_tenant_audit_and_evidence_isolation(async_client: AsyncClient):
    """Audit logs and evidence items are strictly isolated per tenant."""
    token_tn = make_officer_token("OFF-TN-1", "TN-STATE")
    token_mh = make_officer_token("OFF-MH-1", "MH-STATE")

    case_res = await async_client.post(
        "/api/v1/cases",
        json={"fir_number": "FIR-TN-AUDIT-ISO", "victim_reference": "AUDIT-ISO"},
        headers={"Authorization": f"Bearer {token_tn}"},
    )
    case_id = case_res.json()["id"]

    # Record audit event as TN
    audit_res = await async_client.post(
        f"/api/v1/cases/{case_id}/audit",
        json={
            "actor_id": "OFF-TN-1",
            "event_type": "EVIDENCE_REVIEWED",
            "action_summary": "Tenant TN confidential evidence collection",
        },
        headers={"Authorization": f"Bearer {token_tn}"},
    )
    assert audit_res.status_code == 201

    # Tenant MH tries to list audit events
    cross_audit = await async_client.get(
        f"/api/v1/cases/{case_id}/audit",
        headers={"Authorization": f"Bearer {token_mh}"},
    )
    assert cross_audit.status_code == 404
    assert cross_audit.json()["error"]["code"] == "NOT_FOUND"

    # Tenant MH tries to list findings
    cross_findings = await async_client.get(
        f"/api/v1/cases/{case_id}/findings",
        headers={"Authorization": f"Bearer {token_mh}"},
    )
    assert cross_findings.status_code == 404
    assert cross_findings.json()["error"]["code"] == "NOT_FOUND"
