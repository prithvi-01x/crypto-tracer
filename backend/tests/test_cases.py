import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_case_success(async_client: AsyncClient):
    payload = {
        "fir_number": "2026/812",
        "victim_reference": "RAMESH-001",
        "loss_amount_inr": 500000.00,
        "ack_number": "1930-DL-2026-812",
        "suspect_wallet": "TYDZSxdBzWnCuB4jF3K6j5X3qW7b9X1234",
        "chain": "TRON",
        "asset": "TRC20:USDT",
        "notes": "Telegram task-based fraudulent investment syndicate",
    }
    response = await async_client.post("/api/v1/cases", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert data["fir_number"] == "2026/812"
    assert data["victim_reference"] == "RAMESH-001"
    assert float(data["loss_amount_inr"]) == 500000.00
    assert data["ack_number"] == "1930-DL-2026-812"
    assert data["suspect_wallet"] == "TYDZSxdBzWnCuB4jF3K6j5X3qW7b9X1234"
    assert data["chain"] == "TRON"
    assert data["asset"] == "TRC20:USDT"
    assert data["status"] == "OPEN"


@pytest.mark.asyncio
async def test_get_case_by_id(async_client: AsyncClient):
    # First create
    create_payload = {
        "fir_number": "2026/905",
        "victim_reference": "ANITA-002",
        "loss_amount_inr": 250000.00,
        "ack_number": "1930-MH-2026-905",
        "suspect_wallet": "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t",
        "chain": "TRON",
        "asset": "TRC20:USDT",
        "notes": "Part-time job Ponzi scam",
    }
    create_res = await async_client.post("/api/v1/cases", json=create_payload)
    assert create_res.status_code == 201
    case_id = create_res.json()["id"]

    # Now get
    get_res = await async_client.get(f"/api/v1/cases/{case_id}")
    assert get_res.status_code == 200
    data = get_res.json()
    assert data["id"] == case_id
    assert data["fir_number"] == "2026/905"
    assert data["victim_reference"] == "ANITA-002"
    assert float(data["loss_amount_inr"]) == 250000.00


@pytest.mark.asyncio
async def test_list_cases(async_client: AsyncClient):
    # Ensure at least one case exists
    create_payload = {
        "fir_number": "2026/101",
        "victim_reference": "TEST-USER",
        "loss_amount_inr": 50000.00,
    }
    create_res = await async_client.post("/api/v1/cases", json=create_payload)
    assert create_res.status_code == 201

    response = await async_client.get("/api/v1/cases")
    assert response.status_code == 200
    data = response.json()
    assert "total" in data
    assert "cases" in data
    assert isinstance(data["cases"], list)
    assert data["total"] >= 1
    assert any(c["fir_number"] == "2026/101" for c in data["cases"])


@pytest.mark.asyncio
async def test_get_case_not_found(async_client: AsyncClient):
    response = await async_client.get("/api/v1/cases/non-existent-uuid-12345")
    assert response.status_code == 404
    data = response.json()
    assert "detail" in data


@pytest.mark.asyncio
async def test_create_case_missing_required_fir(async_client: AsyncClient):
    payload = {
        "victim_reference": "NO-FIR-USER",
        "loss_amount_inr": 10000.00,
    }
    response = await async_client.post("/api/v1/cases", json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_list_traces_for_case(async_client: AsyncClient):
    # 1. Create a case
    create_payload = {
        "fir_number": "2026/TRACES_LIST",
        "victim_reference": "TRACE-LIST-USER",
        "loss_amount_inr": 150000.00,
    }
    case_res = await async_client.post("/api/v1/cases", json=create_payload)
    assert case_res.status_code == 201
    case_id = case_res.json()["id"]

    # 2. Initially 0 traces
    traces_res = await async_client.get(f"/api/v1/cases/{case_id}/traces")
    assert traces_res.status_code == 200
    assert traces_res.json() == []


@pytest.mark.asyncio
async def test_update_case_notes_and_status(async_client: AsyncClient):
    create_payload = {
        "fir_number": "2026/UPDATE_NOTES_01",
        "victim_reference": "UPDATE-TEST-USER",
        "loss_amount_inr": 200000.00,
        "notes": "Initial FIR notes",
    }
    case_res = await async_client.post("/api/v1/cases", json=create_payload)
    assert case_res.status_code == 201
    case_id = case_res.json()["id"]

    # Update notes via PATCH
    patch_res = await async_client.patch(
        f"/api/v1/cases/{case_id}",
        json={"notes": "Updated comprehensive investigation notes.", "status": "IN_PROGRESS"}
    )
    assert patch_res.status_code == 200
    updated = patch_res.json()
    assert updated["notes"] == "Updated comprehensive investigation notes."
    assert updated["status"] == "IN_PROGRESS"

    # Verify persistence with GET
    get_res = await async_client.get(f"/api/v1/cases/{case_id}")
    assert get_res.status_code == 200
    assert get_res.json()["notes"] == "Updated comprehensive investigation notes."
    assert get_res.json()["status"] == "IN_PROGRESS"


@pytest.mark.asyncio
async def test_add_case_note_appends_timestamped_entry(async_client: AsyncClient):
    create_payload = {
        "fir_number": "2026/ADD_NOTE_02",
        "victim_reference": "NOTE-TEST-USER",
        "notes": "Existing observation 1",
    }
    case_res = await async_client.post("/api/v1/cases", json=create_payload)
    assert case_res.status_code == 201
    case_id = case_res.json()["id"]

    # Append note
    note_payload = {
        "note": "Section 91 CrPC notice dispatched to Binance Compliance.",
        "author": "Insp. Vikramaditya",
    }
    note_res = await async_client.post(f"/api/v1/cases/{case_id}/notes", json=note_payload)
    assert note_res.status_code == 200
    data = note_res.json()
    assert "Existing observation 1" in data["notes"]
    assert "Section 91 CrPC notice dispatched to Binance Compliance." in data["notes"]
    assert "Insp. Vikramaditya" in data["notes"]
    assert "UTC" in data["notes"]


@pytest.mark.asyncio
async def test_update_case_not_found(async_client: AsyncClient):
    res = await async_client.patch(
        "/api/v1/cases/00000000-0000-0000-0000-000000000000",
        json={"notes": "Should fail"}
    )
    assert res.status_code == 404

