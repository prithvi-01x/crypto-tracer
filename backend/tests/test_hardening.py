import pytest
from decimal import Decimal
from httpx import AsyncClient

from backend.app.domain.demo.canonical_data import (
    CANONICAL_CASE_ID,
    CANONICAL_FIR,
    CANONICAL_SUSPECT_WALLET,
)


@pytest.mark.asyncio
async def test_malformed_address_inputs(async_client: AsyncClient):
    """Verify malformed, SQL-injection, and XSS inputs are rejected with clean HTTP 400."""
    # First seed a case to get a valid case_id
    seed_res = await async_client.post("/api/v1/demo/seed")
    case_id = seed_res.json()["case_id"]

    malformed_addresses = [
        # Missing leading 'T'
        "4YDZSxdBzWnCuB4jF3K6j5X3qW7b9X1234",
        # Too short
        "TYDZSxdBzWnCuB4jF3",
        # Too long
        "TYDZSxdBzWnCuB4jF3K6j5X3qW7b9X1234TYDZSxdBzWnCuB4jF3K6j5X3qW7b9X1234",
        # Invalid Base58 characters ('0', 'O', 'I', 'l')
        "T000000000000000000000000000000000",
        "TOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO",
        # SQL Injection attempt
        "TSuspect' OR '1'='1' --",
        # XSS attempt
        "<script>alert('pwn')</script>",
        # Control characters
        "TSuspect\x00Wallet11111111111111111",
    ]

    for bad_addr in malformed_addresses:
        res = await async_client.post(
            "/api/v1/traces",
            json={
                "case_id": case_id,
                "chain": "TRON",
                "input_type": "address",
                "input": bad_addr,
                "asset": "TRC20:USDT",
                "max_hops": 2,
            },
        )
        assert res.status_code == 400, f"Expected 400 for '{bad_addr}', got {res.status_code}"
        err = res.json()["detail"]
        assert err["code"] == "INVALID_ADDRESS"


@pytest.mark.asyncio
async def test_out_of_bounds_parameters_rejected(async_client: AsyncClient):
    """Verify out-of-bounds parameters are rejected by Pydantic schemas (HTTP 422)."""
    seed_res = await async_client.post("/api/v1/demo/seed")
    case_id = seed_res.json()["case_id"]

    # 1. max_hops > 6 (safe bound)
    res = await async_client.post(
        "/api/v1/traces",
        json={
            "case_id": case_id,
            "input": CANONICAL_SUSPECT_WALLET,
            "max_hops": 10,
        },
    )
    assert res.status_code == 422

    # 2. max_hops < 1
    res = await async_client.post(
        "/api/v1/traces",
        json={
            "case_id": case_id,
            "input": CANONICAL_SUSPECT_WALLET,
            "max_hops": 0,
        },
    )
    assert res.status_code == 422

    # 3. min_relevant_usd negative
    res = await async_client.post(
        "/api/v1/traces",
        json={
            "case_id": case_id,
            "input": CANONICAL_SUSPECT_WALLET,
            "min_relevant_usd": -5.0,
        },
    )
    assert res.status_code == 422

    # 4. execution_mode invalid
    res = await async_client.post(
        "/api/v1/traces",
        json={
            "case_id": case_id,
            "input": CANONICAL_SUSPECT_WALLET,
            "execution_mode": "INVALID_MODE",
        },
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_case_negative_loss_rejected(async_client: AsyncClient):
    """Verify negative financial loss is rejected during case registration."""
    res = await async_client.post(
        "/api/v1/cases",
        json={
            "fir_number": "FIR-TEST-NEG-001",
            "loss_amount_inr": -5000.0,
            "chain": "TRON",
            "asset": "TRC20:USDT",
        },
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_unsupported_chain_and_asset(async_client: AsyncClient):
    """Verify unsupported blockchain and asset combinations are blocked with informative error."""
    res_chain = await async_client.post(
        "/api/v1/cases",
        json={
            "fir_number": "FIR-TEST-SOLANA-001",
            "chain": "SOLANA",
            "asset": "SOL",
        },
    )
    assert res_chain.status_code == 400
    assert res_chain.json()["detail"]["code"] == "UNSUPPORTED_CHAIN"

    res_asset = await async_client.post(
        "/api/v1/cases",
        json={
            "fir_number": "FIR-TEST-DOGE-001",
            "chain": "TRON",
            "asset": "DOGE",
        },
    )
    assert res_asset.status_code == 400
    assert res_asset.json()["detail"]["code"] == "UNSUPPORTED_ASSET"


@pytest.mark.asyncio
async def test_report_path_traversal_defense(async_client: AsyncClient):
    """Verify path traversal attempts in report downloads are securely blocked."""
    # Attempt to download with invalid UUID / path traversal string
    res = await async_client.get("/api/v1/reports/../../etc/passwd/download")
    assert res.status_code in (404, 403, 422)


@pytest.mark.asyncio
async def test_demo_seed_idempotent_repetition(async_client: AsyncClient):
    """Verify repeated calls to /demo/seed reset and maintain deterministic canonical state."""
    for _ in range(3):
        res = await async_client.post("/api/v1/demo/seed")
        assert res.status_code in (200, 201)
        data = res.json()
        assert data["case_id"] == CANONICAL_CASE_ID
        assert data["fir_number"] == CANONICAL_FIR
        assert data["attribution"]["attributed_vasp"] == "Binance"
        assert data["attribution"]["confidence_band"] == "HIGH"
