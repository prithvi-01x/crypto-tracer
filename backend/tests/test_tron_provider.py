import json
from decimal import Decimal
from datetime import datetime, timezone
import pytest
import httpx

from backend.app.domain.models import Transfer, TransferPage
from backend.app.adapters.base import (
    InvalidAddressError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    BlockchainProviderError,
)
from backend.app.adapters.tron_provider import TronProvider, validate_tron_address
from backend.app.adapters.fixture_provider import FixtureProvider

SAMPLE_TRON_ADDRESS = "TYDZSxdBzWnCuB4jF3K6j5X3qW7b9X1234"
USDT_CONTRACT = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"

RAW_TRONGRID_ITEM = {
    "transaction_id": "8a32b0f4c391782ec9f4410a08e6f1124d781b0a8cf92497676cfa73587b1234",
    "token_info": {
        "symbol": "USDT",
        "address": USDT_CONTRACT,
        "decimals": 6,
        "name": "Tether USD",
    },
    "block_timestamp": 1715000000000,
    "from": "TYDZSxdBzWnCuB4jF3K6j5X3qW7b9X1234",
    "to": "TXYZdestinationWalletAddress1234567",
    "type": "Transfer",
    "value": "5500000000",
}


def test_validate_tron_address():
    assert validate_tron_address("TYDZSxdBzWnCuB4jF3K6j5X3qW7b9X1234") is True
    assert validate_tron_address("0x71C8fb861337510c4774B830a6D6EB83e9F") is False
    assert validate_tron_address("short") is False
    assert validate_tron_address("") is False


def test_transfer_normalization():
    provider = TronProvider()
    transfer = provider.normalize_transfer(RAW_TRONGRID_ITEM, USDT_CONTRACT)

    assert transfer is not None
    assert transfer.chain == "TRON"
    assert transfer.tx_hash == "8a32b0f4c391782ec9f4410a08e6f1124d781b0a8cf92497676cfa73587b1234"
    assert transfer.from_address == "TYDZSxdBzWnCuB4jF3K6j5X3qW7b9X1234"
    assert transfer.to_address == "TXYZdestinationWalletAddress1234567"
    assert transfer.amount_raw == 5500000000
    assert transfer.amount_decimal == Decimal("5500.000000")
    assert transfer.asset_symbol == "USDT"
    assert transfer.asset_contract == USDT_CONTRACT
    assert transfer.timestamp == datetime.fromtimestamp(1715000000, tz=timezone.utc)
    assert transfer.source == "trongrid"


@pytest.mark.asyncio
async def test_get_transfers_with_pagination_and_deduplication():
    # Response contains two transfers, but the second is a duplicate of the first
    mock_payload = {
        "success": True,
        "data": [
            RAW_TRONGRID_ITEM,
            RAW_TRONGRID_ITEM,  # duplicate
            {
                **RAW_TRONGRID_ITEM,
                "transaction_id": "second_unique_tx_hash_1234567890abcdef",
                "value": "100000000",  # 100 USDT
            },
        ],
        "meta": {
            "page_size": 20,
            "fingerprint": "next_page_cursor_token_xyz",
        },
    }

    mock_transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json=mock_payload)
    )

    async with httpx.AsyncClient(transport=mock_transport) as client:
        provider = TronProvider(http_client=client)
        page = await provider.get_transfers(SAMPLE_TRON_ADDRESS)

        # Deduplication check: 3 items input -> 2 unique items output
        assert len(page.transfers) == 2
        assert page.total_fetched == 2
        assert page.transfers[0].amount_decimal == Decimal("5500")
        assert page.transfers[1].amount_decimal == Decimal("100")

        # Pagination check
        assert page.has_more is True
        assert page.next_cursor == "next_page_cursor_token_xyz"
        assert page.cached is False


@pytest.mark.asyncio
async def test_invalid_address_error():
    provider = TronProvider()
    with pytest.raises(InvalidAddressError):
        await provider.get_transfers("0xInvalidEthAddress")


@pytest.mark.asyncio
async def test_timeout_error_handling():
    def timeout_handler(request):
        raise httpx.TimeoutException("Read timed out")

    mock_transport = httpx.MockTransport(timeout_handler)

    async with httpx.AsyncClient(transport=mock_transport) as client:
        provider = TronProvider(http_client=client, max_retries=2, timeout_seconds=0.1)
        with pytest.raises(ProviderTimeoutError):
            await provider.get_transfers(SAMPLE_TRON_ADDRESS)


@pytest.mark.asyncio
async def test_rate_limit_429_handling():
    def rate_limit_handler(request):
        return httpx.Response(429, json={"error": "Too Many Requests"})

    mock_transport = httpx.MockTransport(rate_limit_handler)

    async with httpx.AsyncClient(transport=mock_transport) as client:
        provider = TronProvider(http_client=client, max_retries=2)
        with pytest.raises(ProviderRateLimitError):
            await provider.get_transfers(SAMPLE_TRON_ADDRESS)


class FakeRedis:
    def __init__(self):
        self.store = {}

    async def get(self, key: str):
        return self.store.get(key)

    async def setex(self, key: str, ttl: int, value: str):
        self.store[key] = value


@pytest.mark.asyncio
async def test_redis_cache_hit_and_miss():
    fake_redis = FakeRedis()
    mock_payload = {
        "success": True,
        "data": [RAW_TRONGRID_ITEM],
        "meta": {},
    }

    call_count = 0

    def counting_handler(request):
        nonlocal call_count
        call_count += 1
        return httpx.Response(200, json=mock_payload)

    mock_transport = httpx.MockTransport(counting_handler)

    async with httpx.AsyncClient(transport=mock_transport) as client:
        provider = TronProvider(
            redis_client=fake_redis,  # type: ignore
            http_client=client,
        )

        # First call: Cache Miss
        page_miss = await provider.get_transfers(SAMPLE_TRON_ADDRESS)
        assert call_count == 1
        assert page_miss.cached is False
        assert len(page_miss.transfers) == 1

        # Second call: Cache Hit
        page_hit = await provider.get_transfers(SAMPLE_TRON_ADDRESS)
        assert call_count == 1  # No additional HTTP request made
        assert page_hit.cached is True
        assert len(page_hit.transfers) == 1
        assert page_hit.transfers[0].tx_hash == RAW_TRONGRID_ITEM["transaction_id"]


@pytest.mark.asyncio
async def test_fixture_provider():
    fixture_provider = FixtureProvider()
    sample_transfer = Transfer(
        chain="TRON",
        tx_hash="demo_tx_hash_999",
        timestamp=datetime.now(timezone.utc),
        from_address=SAMPLE_TRON_ADDRESS,
        to_address="TDemoDepositAddress1234567890",
        asset_contract=USDT_CONTRACT,
        asset_symbol="USDT",
        amount_raw=2500000000,
        amount_decimal=Decimal("2500.00"),
        source="fixture",
    )
    fixture_provider.register_fixture(SAMPLE_TRON_ADDRESS, [sample_transfer])

    page = await fixture_provider.get_transfers(SAMPLE_TRON_ADDRESS)
    assert len(page.transfers) == 1
    assert page.transfers[0].amount_decimal == Decimal("2500.00")
    assert page.cached is True


@pytest.mark.asyncio
async def test_api_endpoint_tron_transfers_removed(async_client):
    """Verify deprecated dev-only blockchain inspection endpoint returns 404."""
    response = await async_client.get(f"/api/v1/blockchain/tron/transfers/{SAMPLE_TRON_ADDRESS}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_tron_provider_fallback_to_secondary_endpoint():
    """Verify TronProvider fails over to secondary endpoint when primary endpoint returns 500."""
    primary_url = "https://primary.rpc.invalid"
    fallback_url = "https://fallback.rpc.invalid"

    calls = []

    def mock_handler(request: httpx.Request):
        url_str = str(request.url)
        calls.append(url_str)
        if "primary.rpc.invalid" in url_str:
            return httpx.Response(503, text="Service Unavailable")
        elif "fallback.rpc.invalid" in url_str:
            return httpx.Response(200, json={
                "success": True,
                "data": [RAW_TRONGRID_ITEM],
                "meta": {"fingerprint": None}
            })
        return httpx.Response(404)

    mock_transport = httpx.MockTransport(mock_handler)
    async with httpx.AsyncClient(transport=mock_transport) as client:
        provider = TronProvider(
            base_url=primary_url,
            fallback_urls=[fallback_url],
            max_retries=1,
            http_client=client,
        )
        page = await provider.get_transfers(SAMPLE_TRON_ADDRESS)

        assert len(page.transfers) == 1
        assert page.transfers[0].amount_decimal == Decimal("5500")
        assert any("primary.rpc.invalid" in c for c in calls)
        assert any("fallback.rpc.invalid" in c for c in calls)


@pytest.mark.asyncio
async def test_tron_provider_empty_transfers():
    """Verify TronProvider handles empty on-chain transfer list cleanly."""
    mock_payload = {
        "success": True,
        "data": [],
        "meta": {"at": 1741700000, "page_size": 20},
    }

    mock_transport = httpx.MockTransport(lambda req: httpx.Response(200, json=mock_payload))
    async with httpx.AsyncClient(transport=mock_transport) as client:
        provider = TronProvider(http_client=client)
        page = await provider.get_transfers(SAMPLE_TRON_ADDRESS)

        assert len(page.transfers) == 0
        assert page.total_fetched == 0
        assert page.has_more is False
        assert page.next_cursor is None


@pytest.mark.asyncio
async def test_tron_provider_http_400_invalid_address():
    """Verify HTTP 400 with invalid address detail raises InvalidAddressError immediately without failover."""
    calls = []

    def mock_handler(request: httpx.Request):
        calls.append(str(request.url))
        return httpx.Response(400, json={"success": False, "error": "A valid account address is required."})

    mock_transport = httpx.MockTransport(mock_handler)
    async with httpx.AsyncClient(transport=mock_transport) as client:
        provider = TronProvider(
            base_url="https://primary.rpc.invalid",
            fallback_urls=["https://fallback.rpc.invalid"],
            max_retries=2,
            http_client=client,
        )
        with pytest.raises(InvalidAddressError) as exc_info:
            await provider.get_transfers(SAMPLE_TRON_ADDRESS)

        assert "A valid account address is required" in str(exc_info.value)
        # Should NOT failover to fallback endpoint on 400
        assert len(calls) == 1
        assert "primary.rpc.invalid" in calls[0]


@pytest.mark.asyncio
async def test_tron_provider_malformed_json_response():
    """Verify non-JSON response raises BlockchainProviderError cleanly."""
    mock_transport = httpx.MockTransport(
        lambda req: httpx.Response(200, content=b"<!DOCTYPE html><html><body>Error 502 Bad Gateway</body></html>")
    )
    async with httpx.AsyncClient(transport=mock_transport) as client:
        provider = TronProvider(max_retries=1, http_client=client)
        with pytest.raises(BlockchainProviderError) as exc_info:
            await provider.get_transfers(SAMPLE_TRON_ADDRESS)

        assert "Malformed JSON" in str(exc_info.value) or "expected JSON object" in str(exc_info.value)


@pytest.mark.asyncio
async def test_tron_provider_unsuccessful_status_flag():
    """Verify HTTP 200 with success: false raises BlockchainProviderError."""
    mock_transport = httpx.MockTransport(
        lambda req: httpx.Response(200, json={"success": False, "error": "Internal contract evaluation timeout"})
    )
    async with httpx.AsyncClient(transport=mock_transport) as client:
        provider = TronProvider(max_retries=1, http_client=client)
        with pytest.raises(BlockchainProviderError) as exc_info:
            await provider.get_transfers(SAMPLE_TRON_ADDRESS)

        assert "Internal contract evaluation timeout" in str(exc_info.value)


@pytest.mark.asyncio
async def test_trace_api_default_live_mode_and_explicit_demo_mode(async_client):
    """
    Verify POST /api/v1/traces:
    1. Defaults to execution_mode="LIVE"
    2. Respects explicit execution_mode="DEMO" without modifying live default
    3. Never silently coerces live mode to demo
    """
    # 1. Create a parent case
    case_res = await async_client.post("/api/v1/cases", json={
        "fir_number": "FIR-2026-LIVE-DEFAULT-01",
        "victim_reference": "VICTIM-LIVE-TEST",
        "loss_amount_inr": 200000.0,
    })
    assert case_res.status_code == 201
    case_id = case_res.json()["id"]

    # 2. Trace with explicit DEMO mode on canonical demo address -> succeeds with DEMO mode
    from backend.app.domain.demo.canonical_data import ADDR_SUSPECT_ROOT
    demo_trace_res = await async_client.post("/api/v1/traces", json={
        "case_id": case_id,
        "chain": "TRON",
        "input_type": "address",
        "input": ADDR_SUSPECT_ROOT,
        "asset": "TRC20:USDT",
        "max_hops": 2,
        "execution_mode": "DEMO",
    })
    assert demo_trace_res.status_code == 201
    demo_data = demo_trace_res.json()
    assert demo_data["execution_mode"] == "DEMO"
    assert demo_data["status"] in ("COMPLETED", "PARTIAL")

    # 3. Trace WITHOUT specifying execution_mode -> defaults to LIVE (querying TronProvider)
    live_trace_res = await async_client.post("/api/v1/traces", json={
        "case_id": case_id,
        "chain": "TRON",
        "input_type": "address",
        "input": ADDR_SUSPECT_ROOT,
        "asset": "TRC20:USDT",
        "max_hops": 2,
    })
    # Since ADDR_SUSPECT_ROOT is a simulated demo address not on live TronGrid,
    # live provider queries TronGrid and receives 400 (Invalid Address) or executes live.
    # It must NOT silently return the demo fixture with execution_mode DEMO!
    assert live_trace_res.status_code in (201, 400, 502, 504)
    if live_trace_res.status_code == 201:
        assert live_trace_res.json()["execution_mode"] == "LIVE"
    elif live_trace_res.status_code == 400:
        err_detail = live_trace_res.json()["detail"]
        assert err_detail["code"] == "INVALID_ADDRESS"


