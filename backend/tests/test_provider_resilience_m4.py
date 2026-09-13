import asyncio
import time
from datetime import datetime, timezone
from decimal import Decimal
import pytest
import httpx

from backend.app.adapters.base import (
    BlockchainProvider,
    BlockchainProviderError,
    ProviderTimeoutError,
    ProviderRateLimitError,
    InvalidAddressError,
    CircuitBreakerOpenError,
    NodeExhaustionError,
    TransactionExecutionError,
)
from backend.app.core.circuit_breaker import CircuitBreaker, CircuitState
from backend.app.adapters.cache import InMemoryL1Cache, TwoTierBlockchainCache
from backend.app.adapters.failover_pool import RpcNode, RpcFailoverPool
from backend.app.adapters.tron_provider import TronProvider, validate_tron_address
from backend.app.domain.models import Transfer, TransferPage

SAMPLE_TRON_ADDR = "TYDZSxdBzWnCuB4jF3K6j5X3qW7b9X1234"
SAMPLE_DEST_ADDR = "TXYZdestinationWalletAddress1234567"
USDT_CONTRACT = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"


# ============================================================================
# 1. Feature 25: BlockchainProvider ABC & Exception Hierarchy Tests
# ============================================================================

def test_blockchain_provider_abc_cannot_be_instantiated_directly():
    """Verify BlockchainProvider is an ABC and cannot be instantiated without get_transfers."""
    with pytest.raises(TypeError) as excinfo:
        BlockchainProvider()  # type: ignore
    assert "Can't instantiate abstract class" in str(excinfo.value)


@pytest.mark.asyncio
async def test_blockchain_provider_default_implementations():
    """Verify non-breaking default implementations on concrete BlockchainProvider subclass."""
    class MinimalProvider(BlockchainProvider):
        async def get_transfers(self, address, asset_contract=None, cursor=None, limit=20, direction=None):
            return TransferPage(transfers=[], total_fetched=0)

    provider = MinimalProvider()
    assert provider.chain_name == "TRON"
    assert provider.validate_address("anything") is True
    assert provider.normalize_transfer({}, "contract") is None
    health = await provider.health_check()
    assert health["status"] == "HEALTHY"
    balance = await provider.get_account_balance("TYDZSxdBzWnCuB4jF3K6j5X3qW7b9X1234")
    assert balance["balance"] == "0.00"


def test_exception_hierarchy_relationships():
    """Verify that all new M4 provider exceptions inherit from BlockchainProviderError."""
    assert issubclass(CircuitBreakerOpenError, BlockchainProviderError)
    assert issubclass(NodeExhaustionError, BlockchainProviderError)
    assert issubclass(TransactionExecutionError, BlockchainProviderError)
    assert issubclass(ProviderTimeoutError, BlockchainProviderError)
    assert issubclass(ProviderRateLimitError, BlockchainProviderError)
    assert issubclass(InvalidAddressError, BlockchainProviderError)

    cb_err = CircuitBreakerOpenError(endpoint="https://node.tron", retry_after=15.5)
    assert cb_err.endpoint == "https://node.tron"
    assert cb_err.retry_after == 15.5
    assert "15.5s" in str(cb_err)


# ============================================================================
# 2. Feature 27: 3-State Circuit Breaker Tests
# ============================================================================

@pytest.mark.asyncio
async def test_circuit_breaker_state_lifecycle():
    """Verify CLOSED -> OPEN -> HALF_OPEN -> CLOSED lifecycle."""
    cb = CircuitBreaker(
        name="test_cb",
        failure_threshold=3,
        recovery_timeout=0.2,
        half_open_trials=2,
        backoff_factor=1.5,
        jitter_ratio=0.0,
    )

    # Initial state
    assert cb.state == CircuitState.CLOSED
    assert cb.allow_request() is True

    # 1st failure
    await cb.record_failure(Exception("Fail 1"))
    assert cb.state == CircuitState.CLOSED
    assert cb.allow_request() is True

    # 2nd failure
    await cb.record_failure(Exception("Fail 2"))
    assert cb.state == CircuitState.CLOSED
    assert cb.allow_request() is True

    # 3rd failure -> Trips to OPEN
    await cb.record_failure(Exception("Fail 3"))
    assert cb.state == CircuitState.OPEN
    assert cb.allow_request() is False
    assert cb.get_remaining_cooldown() > 0

    # Wait for cooldown to expire
    await asyncio.sleep(0.25)
    assert cb.state == CircuitState.HALF_OPEN
    assert cb.allow_request() is True

    # In HALF_OPEN: 1st trial success
    await cb.record_success()
    assert cb.state == CircuitState.HALF_OPEN

    # 2nd trial success -> Recovers to CLOSED
    await cb.record_success()
    assert cb.state == CircuitState.CLOSED
    assert cb.allow_request() is True
    stats = cb.get_stats()
    assert stats["state"] == "CLOSED"
    assert stats["consecutive_failures"] == 0


@pytest.mark.asyncio
async def test_circuit_breaker_half_open_failure_re_trips():
    """Verify failure during HALF_OPEN immediately re-trips to OPEN with increased backoff."""
    cb = CircuitBreaker(
        name="retry_cb",
        failure_threshold=1,
        recovery_timeout=0.1,
        half_open_trials=2,
        backoff_factor=2.0,
        jitter_ratio=0.0,
    )

    # Trip to OPEN
    await cb.record_failure(Exception("Initial failure"))
    assert cb.state == CircuitState.OPEN

    # Wait for HALF_OPEN
    await asyncio.sleep(0.12)
    assert cb.state == CircuitState.HALF_OPEN

    # Probe failure in HALF_OPEN -> immediately re-trips to OPEN
    await cb.record_failure(Exception("Probe failure"))
    assert cb.state == CircuitState.OPEN
    # Backoff increased: 0.1 * 2^1 = 0.2s
    assert cb._current_timeout >= 0.19


# ============================================================================
# 3. Feature 28: Multi-Node RPC Failover Pool Tests
# ============================================================================

@pytest.mark.asyncio
async def test_failover_pool_priority_and_fallback():
    """Verify pool queries primary (priority 0), fails over to secondary on 503."""
    primary_url = "https://primary.tron.rpc"
    fallback_url = "https://fallback.tron.rpc"

    calls = []

    def mock_handler(request: httpx.Request):
        url_str = str(request.url)
        calls.append(url_str)
        if "primary" in url_str:
            return httpx.Response(503, text="Primary node offline")
        elif "fallback" in url_str:
            return httpx.Response(200, json={
                "success": True,
                "data": [],
                "meta": {"fingerprint": None}
            })
        return httpx.Response(404)

    transport = httpx.MockTransport(mock_handler)
    async with httpx.AsyncClient(transport=transport) as client:
        pool = RpcFailoverPool(
            primary_url=primary_url,
            fallback_urls=[fallback_url],
            timeout_seconds=1.0,
            max_retries_per_node=1,
        )

        resp = await pool.execute_request(
            path="/v1/test",
            params={},
            headers={},
            http_client=client,
        )
        assert resp["success"] is True
        assert any("primary" in c for c in calls)
        assert any("fallback" in c for c in calls)

        # Primary node has 1 failed request, fallback has 1 successful
        primary_node = [n for n in pool.nodes if "primary" in n.url][0]
        fallback_node = [n for n in pool.nodes if "fallback" in n.url][0]
        assert primary_node.failed_requests == 1
        assert fallback_node.successful_requests == 1
        assert fallback_node.avg_latency_ms >= 0


@pytest.mark.asyncio
async def test_failover_pool_invalid_address_immediate_raise():
    """Verify HTTP 400 immediately raises InvalidAddressError without failover."""
    calls = []

    def mock_handler(request: httpx.Request):
        calls.append(str(request.url))
        return httpx.Response(400, json={"error": "class java.lang.IllegalArgumentException : Invalid address"})

    transport = httpx.MockTransport(mock_handler)
    async with httpx.AsyncClient(transport=transport) as client:
        pool = RpcFailoverPool(
            primary_url="https://primary.tron.rpc",
            fallback_urls=["https://fallback.tron.rpc"],
            max_retries_per_node=2,
        )

        with pytest.raises(InvalidAddressError):
            await pool.execute_request("/v1/test", {}, {}, http_client=client)

        # Must have attempted ONLY primary, exactly 1 time (no retry, no fallback)
        assert len(calls) == 1
        assert "primary" in calls[0]


@pytest.mark.asyncio
async def test_failover_pool_exhaustion_raises_circuit_or_exhaustion():
    """Verify pool raises CircuitBreakerOpenError or NodeExhaustionError when all nodes fail."""
    def mock_handler(request: httpx.Request):
        return httpx.Response(500, text="Internal Error")

    transport = httpx.MockTransport(mock_handler)
    async with httpx.AsyncClient(transport=transport) as client:
        pool = RpcFailoverPool(
            primary_url="https://solo.tron.rpc",
            timeout_seconds=0.5,
            max_retries_per_node=1,
        )
        with pytest.raises(BlockchainProviderError):
            await pool.execute_request("/v1/test", {}, {}, http_client=client)


# ============================================================================
# 4. Feature 29: Two-Tier Blockchain Cache Tests
# ============================================================================

@pytest.mark.asyncio
async def test_two_tier_cache_l1_and_l2():
    """Verify L1 in-memory LRU hit and L2 Redis hit backfilling into L1."""
    class MockRedis:
        def __init__(self):
            self.data = {}

        async def get(self, key):
            return self.data.get(key)

        async def setex(self, key, ttl, val):
            self.data[key] = val

    mock_redis = MockRedis()
    cache = TwoTierBlockchainCache(
        redis_client=mock_redis,
        default_ttl=300,
        finalized_ttl=86400,
        l1_max_entries=5,
        l1_ttl=60.0,
    )

    test_page = TransferPage(
        transfers=[
            Transfer(
                chain="TRON",
                tx_hash="0x123",
                timestamp=datetime.now(timezone.utc),
                from_address=SAMPLE_TRON_ADDR,
                to_address=SAMPLE_DEST_ADDR,
                asset_contract=USDT_CONTRACT,
                asset_symbol="USDT",
                amount_raw=1000000,
                amount_decimal=Decimal("1.0"),
            )
        ],
        total_fetched=1,
    )

    key = cache.build_key("tron", SAMPLE_TRON_ADDR, USDT_CONTRACT, limit=20)

    # Initially None
    assert await cache.get(key) is None

    # Set cache
    await cache.set(key, test_page, is_finalized=True)

    # Verify L1 hit
    l1_page = await cache.get(key)
    assert l1_page is not None
    assert l1_page.cached is True
    assert l1_page.transfers[0].tx_hash == "0x123"

    # Clear L1 to force L2 Redis read
    cache.clear_l1()
    assert len(cache.l1) == 0

    # Read from L2 Redis (and backfill to L1)
    l2_page = await cache.get(key)
    assert l2_page is not None
    assert l2_page.cached is True
    assert len(cache.l1) == 1  # Backfilled!


def test_in_memory_l1_cache_lru_eviction():
    """Verify LRU capacity eviction in InMemoryL1Cache."""
    l1 = InMemoryL1Cache(max_entries=2, default_ttl=10.0)
    p1 = TransferPage(transfers=[], total_fetched=1)
    p2 = TransferPage(transfers=[], total_fetched=2)
    p3 = TransferPage(transfers=[], total_fetched=3)

    l1.set("k1", p1)
    l1.set("k2", p2)
    assert len(l1) == 2

    # Adding k3 should evict oldest (k1)
    l1.set("k3", p3)
    assert len(l1) == 2
    assert l1.get("k1") is None
    assert l1.get("k2") is not None
    assert l1.get("k3") is not None


# ============================================================================
# 5. Feature 26: TRON Ingestion Hardening Tests
# ============================================================================

def test_tron_revert_and_failure_flags_filtered():
    """Verify normalize_transfer filters out reverted/failed transactions."""
    provider = TronProvider()

    # 1. ret array with contractRet: REVERT
    revert_item = {
        "transaction_id": "tx_revert_001",
        "ret": [{"contractRet": "REVERT"}],
        "token_info": {"decimals": 6, "symbol": "USDT"},
        "value": "1000000",
    }
    assert provider.normalize_transfer(revert_item, USDT_CONTRACT) is None

    # 2. ret array with contractRet: OUT_OF_ENERGY
    ooe_item = {
        "transaction_id": "tx_ooe_002",
        "ret": [{"contractRet": "OUT_OF_ENERGY"}],
        "token_info": {"decimals": 6, "symbol": "USDT"},
        "value": "1000000",
    }
    assert provider.normalize_transfer(ooe_item, USDT_CONTRACT) is None

    # 3. top-level finalResult: FAILED
    failed_item = {
        "transaction_id": "tx_failed_003",
        "finalResult": "FAILED",
        "token_info": {"decimals": 6, "symbol": "USDT"},
        "value": "1000000",
    }
    assert provider.normalize_transfer(failed_item, USDT_CONTRACT) is None

    # 4. non-Transfer event type (e.g. Approval)
    approval_item = {
        "transaction_id": "tx_approval_004",
        "type": "Approval",
        "token_info": {"decimals": 6, "symbol": "USDT"},
        "value": "1000000",
    }
    assert provider.normalize_transfer(approval_item, USDT_CONTRACT) is None

    # 5. Zero or negative amount
    zero_item = {
        "transaction_id": "tx_zero_005",
        "value": "0",
        "token_info": {"decimals": 6, "symbol": "USDT"},
    }
    assert provider.normalize_transfer(zero_item, USDT_CONTRACT) is None

    # 6. Valid SUCCESS transfer
    success_item = {
        "transaction_id": "tx_success_006",
        "ret": [{"contractRet": "SUCCESS"}],
        "type": "Transfer",
        "from": SAMPLE_TRON_ADDR,
        "to": SAMPLE_DEST_ADDR,
        "value": "50000000",  # 50 USDT
        "token_info": {"decimals": 6, "symbol": "USDT", "address": USDT_CONTRACT},
        "block_timestamp": 1715000000000,
    }
    tx = provider.normalize_transfer(success_item, USDT_CONTRACT)
    assert tx is not None
    assert tx.tx_hash == "tx_success_006"
    assert tx.amount_decimal == Decimal("50.000000")
    assert tx.from_address == SAMPLE_TRON_ADDR
    assert tx.to_address == SAMPLE_DEST_ADDR
