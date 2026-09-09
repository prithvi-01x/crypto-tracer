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
async def test_api_endpoint_tron_transfers(async_client):
    # Test valid mock address format validation
    response = await async_client.get(f"/api/v1/blockchain/tron/transfers/{SAMPLE_TRON_ADDRESS}")
    # In test environment without mocking external TronGrid, either returns 200 or 502/504
    assert response.status_code in (200, 502, 504)

    # Test invalid address rejection (400 Bad Request)
    invalid_res = await async_client.get("/api/v1/blockchain/tron/transfers/invalid_eth_addr")
    assert invalid_res.status_code == 400
    assert "Invalid TRON address" in invalid_res.json()["detail"]
