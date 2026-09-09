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
