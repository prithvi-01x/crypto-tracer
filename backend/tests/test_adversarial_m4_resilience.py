"""
Adversarial Stress-Testing Suite for Milestone 4 (Phase 4: Provider Resilience, TRON Hardening,
3-State Circuit Breaker, Failover Pool, and Two-Tier Cache).

Empirically challenges:
1. 3-State Circuit Breaker state transitions, fast-fail OPEN, HALF_OPEN probe recovery,
   exponential backoff scaling, jitter bounds, concurrency, and reset.
2. Multi-Node RPC Failover Pool cascade routing, node exhaustion, strict 400 client error isolation,
   429 rate limit backoff, malformed HTML/JSON responses, and provider error flags.
3. TRON Ingestion Hardening against reverted on-chain transactions, non-transfer events, zero/negative amounts,
   Base58 illegal characters, injection attacks, and duplicate transfers.
4. Two-Tier Cache (L1 LRU memory pressure eviction, monotonic TTL expiration, deep-copy mutation isolation,
   volatile vs finalized TTL validation, and Redis outage degradation).
"""

import asyncio
import math
import statistics
import time
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, Any, List, Optional
import httpx
import pytest

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


class MockAsyncRedis:
    """Mock Redis client simulating distributed cache storage and TTL tracking."""
    def __init__(self, should_fail: bool = False):
        self.data: Dict[str, str] = {}
        self.ttls: Dict[str, int] = {}
        self.should_fail = should_fail

    async def get(self, key: str) -> Optional[str]:
        if self.should_fail:
            raise ConnectionError("Simulated Redis cluster connection refused")
        return self.data.get(key)

    async def setex(self, key: str, ttl: int, value: str):
        if self.should_fail:
            raise ConnectionError("Simulated Redis cluster write timeout")
        self.data[key] = value
        self.ttls[key] = ttl


# ============================================================================
# Section 1: 3-State Circuit Breaker Transitions & Adversarial Stress Tests
# ============================================================================

@pytest.mark.asyncio
async def test_circuit_breaker_exact_failure_threshold_boundary():
    """
    Verify that the circuit remains CLOSED for strictly N-1 failures,
    and trips to OPEN on exactly the Nth consecutive failure.
    """
    threshold = 4
    cb = CircuitBreaker(name="boundary_cb", failure_threshold=threshold, recovery_timeout=1.0, jitter_ratio=0.0)

    for i in range(1, threshold):
        await cb.record_failure(Exception(f"Failure #{i}"))
        assert cb.state == CircuitState.CLOSED
        assert cb.allow_request() is True
        assert cb._consecutive_failures == i

    # Nth failure trips to OPEN
    await cb.record_failure(Exception(f"Failure #{threshold}"))
    assert cb.state == CircuitState.OPEN
    assert cb.allow_request() is False
    assert cb._consecutive_opens == 1


@pytest.mark.asyncio
async def test_circuit_breaker_intervening_success_resets_failure_count():
    """
    Verify that a single success while CLOSED resets consecutive failures to 0,
    preventing non-consecutive errors from tripping the circuit.
    """
    cb = CircuitBreaker(name="reset_failures_cb", failure_threshold=3, recovery_timeout=1.0)

    await cb.record_failure(Exception("Fail 1"))
    await cb.record_failure(Exception("Fail 2"))
    assert cb._consecutive_failures == 2

    # Intervening success resets counter
    await cb.record_success()
    assert cb._consecutive_failures == 0
    assert cb.state == CircuitState.CLOSED

    # Next failure is count 1, NOT count 3
    await cb.record_failure(Exception("Fail 3"))
    assert cb._consecutive_failures == 1
    assert cb.state == CircuitState.CLOSED
    assert cb.allow_request() is True


@pytest.mark.asyncio
async def test_circuit_breaker_fast_fail_in_open_state():
    """
    Verify that OPEN circuit instantly rejects requests without executing any operations,
    and reports accurate positive cooldown time remaining.
    """
    cb = CircuitBreaker(name="fast_fail_cb", failure_threshold=1, recovery_timeout=0.3, jitter_ratio=0.0)
    await cb.record_failure(Exception("Trigger OPEN"))

    assert cb.state == CircuitState.OPEN
    assert cb.allow_request() is False
    cooldown = cb.get_remaining_cooldown()
    assert 0.0 < cooldown <= 0.3

    # Fast-fail check multiple times without state changes
    for _ in range(10):
        assert cb.allow_request() is False


@pytest.mark.asyncio
async def test_circuit_breaker_half_open_success_sequence_recovery():
    """
    Verify that transitioning from OPEN to HALF_OPEN requires exactly
    `half_open_trials` successes to fully recover to CLOSED.
    """
    cb = CircuitBreaker(
        name="half_open_cb",
        failure_threshold=1,
        recovery_timeout=0.1,
        half_open_trials=3,
        jitter_ratio=0.0,
    )
    await cb.record_failure(Exception("Trip to OPEN"))
    assert cb.state == CircuitState.OPEN

    # Wait for cooldown expiration into HALF_OPEN
    await asyncio.sleep(0.12)
    assert cb.state == CircuitState.HALF_OPEN
    assert cb.allow_request() is True

    # 1st trial success: remains HALF_OPEN
    await cb.record_success()
    assert cb.state == CircuitState.HALF_OPEN
    assert cb._half_open_successes == 1

    # 2nd trial success: remains HALF_OPEN
    await cb.record_success()
    assert cb.state == CircuitState.HALF_OPEN
    assert cb._half_open_successes == 2

    # 3rd trial success: completes trials and recovers to CLOSED
    await cb.record_success()
    assert cb.state == CircuitState.CLOSED
    assert cb._half_open_successes == 0
    assert cb._consecutive_opens == 0
    assert cb.allow_request() is True


@pytest.mark.asyncio
async def test_circuit_breaker_half_open_single_failure_immediate_retrip():
    """
    Verify that even after partial successes in HALF_OPEN, a single failure
    immediately re-trips the circuit back to OPEN.
    """
    cb = CircuitBreaker(
        name="retrip_cb",
        failure_threshold=1,
        recovery_timeout=0.1,
        half_open_trials=3,
        jitter_ratio=0.0,
    )
    await cb.record_failure(Exception("Trip 1"))
    await asyncio.sleep(0.12)
    assert cb.state == CircuitState.HALF_OPEN

    # 2 successful probes
    await cb.record_success()
    await cb.record_success()
    assert cb._half_open_successes == 2

    # 3rd probe fails -> must immediately trip back to OPEN
    await cb.record_failure(Exception("Probe failure"))
    assert cb.state == CircuitState.OPEN
    assert cb._half_open_successes == 0
    assert cb._consecutive_opens == 2
    assert cb.allow_request() is False


@pytest.mark.asyncio
async def test_circuit_breaker_exponential_backoff_multi_trip():
    """
    Verify exponential backoff progression across subsequent OPEN trips:
    trip 1 = base * (factor^0), trip 2 = base * (factor^1), trip 3 = base * (factor^2).
    """
    base = 1.0
    factor = 2.0
    cb = CircuitBreaker(
        name="backoff_cb",
        failure_threshold=1,
        recovery_timeout=base,
        backoff_factor=factor,
        jitter_ratio=0.0,
    )

    # Trip 1
    await cb.record_failure(Exception("Trip 1"))
    assert cb._consecutive_opens == 1
    assert math.isclose(cb._current_timeout, 1.0, rel_tol=1e-3)

    # Transition to HALF_OPEN manually by adjusting timestamp
    cb._last_state_change = time.monotonic() - 1.5
    assert cb.state == CircuitState.HALF_OPEN

    # Trip 2
    await cb.record_failure(Exception("Trip 2"))
    assert cb._consecutive_opens == 2
    assert math.isclose(cb._current_timeout, 2.0, rel_tol=1e-3)

    # Transition to HALF_OPEN
    cb._last_state_change = time.monotonic() - 2.5
    assert cb.state == CircuitState.HALF_OPEN

    # Trip 3
    await cb.record_failure(Exception("Trip 3"))
    assert cb._consecutive_opens == 3
    assert math.isclose(cb._current_timeout, 4.0, rel_tol=1e-3)


@pytest.mark.asyncio
async def test_circuit_breaker_exponential_backoff_capped_at_max():
    """Verify that exponential backoff does not grow unbounded and is capped at max_recovery_timeout."""
    cb = CircuitBreaker(
        name="cap_cb",
        failure_threshold=1,
        recovery_timeout=10.0,
        backoff_factor=3.0,
        max_recovery_timeout=60.0,
        jitter_ratio=0.0,
    )

    # Simulate 10 consecutive trips
    for trip in range(1, 10):
        cb._last_state_change = time.monotonic() - 100.0
        assert cb.state in (CircuitState.CLOSED, CircuitState.HALF_OPEN)
        await cb.record_failure(Exception(f"Trip {trip}"))
        assert cb._current_timeout <= 60.0

    assert cb._consecutive_opens == 9
    assert math.isclose(cb._current_timeout, 60.0, rel_tol=1e-3)


def test_circuit_breaker_jitter_bounds_and_variance():
    """
    Verify that jittered timeouts strictly remain within [-jitter_ratio, +jitter_ratio]
    and exhibit non-zero statistical variance.
    """
    base_timeout = 20.0
    jitter_ratio = 0.25  # Expected range: [15.0, 25.0]
    samples = []

    for _ in range(100):
        cb = CircuitBreaker(
            name="jitter_cb",
            failure_threshold=1,
            recovery_timeout=base_timeout,
            jitter_ratio=jitter_ratio,
        )
        cb._transition_to(CircuitState.OPEN)
        samples.append(cb._current_timeout)

    for sample in samples:
        assert 15.0 <= sample <= 25.0, f"Sample {sample} out of jitter bounds [15.0, 25.0]"

    # Verify real randomness exists
    variance = statistics.variance(samples)
    assert variance > 0.05, f"Expected non-zero jitter variance, got {variance}"


@pytest.mark.asyncio
async def test_circuit_breaker_manual_reset():
    """Verify manual reset() restores CLOSED state, clears consecutive opens, and resets timeout."""
    cb = CircuitBreaker(name="reset_cb", failure_threshold=1, recovery_timeout=5.0)
    await cb.record_failure(Exception("Trip"))
    assert cb.state == CircuitState.OPEN
    assert cb._consecutive_opens == 1

    cb.reset()
    assert cb.state == CircuitState.CLOSED
    assert cb.allow_request() is True
    assert cb._consecutive_failures == 0
    assert cb._consecutive_opens == 0
    assert cb._current_timeout == 5.0


@pytest.mark.asyncio
async def test_circuit_breaker_concurrent_stress():
    """
    Stress-test circuit breaker under high concurrency: 100 concurrent tasks
    recording failures and successes simultaneously.
    """
    cb = CircuitBreaker(name="stress_cb", failure_threshold=10, recovery_timeout=0.05)

    async def worker(idx: int):
        if idx % 3 == 0:
            await cb.record_success()
        else:
            await cb.record_failure(Exception(f"Worker {idx} failure"))

    tasks = [worker(i) for i in range(100)]
    await asyncio.gather(*tasks)

    # Invariants must hold regardless of race order
    assert cb.state in (CircuitState.CLOSED, CircuitState.OPEN, CircuitState.HALF_OPEN)
    assert cb._consecutive_failures >= 0
    assert cb._consecutive_opens >= 0


# ============================================================================
# Section 2: Multi-Node RPC Failover Pool & Node Resilience Tests
# ============================================================================

@pytest.mark.asyncio
async def test_failover_pool_empty_nodes_raises_node_exhaustion():
    """Verify that an RpcFailoverPool initialized with no valid nodes raises NodeExhaustionError."""
    pool = RpcFailoverPool(primary_url="", fallback_urls=[])
    assert len(pool.nodes) == 0

    with pytest.raises(NodeExhaustionError) as exc_info:
        await pool.execute_request("/v1/test", {}, {})
    assert "No RPC nodes configured" in str(exc_info.value)


@pytest.mark.asyncio
async def test_failover_pool_three_node_cascade():
    """
    Verify complete failover cascade across 3 nodes:
    Node 1 (Primary): returns HTTP 500
    Node 2 (Secondary): returns HTTP 504 Gateway Timeout
    Node 3 (Tertiary): returns HTTP 200 OK
    """
    calls = []

    def mock_handler(request: httpx.Request):
        url_str = str(request.url)
        calls.append(url_str)
        if "node1" in url_str:
            return httpx.Response(500, text="Node 1 Internal Error")
        elif "node2" in url_str:
            return httpx.Response(504, text="Node 2 Gateway Timeout")
        elif "node3" in url_str:
            return httpx.Response(200, json={"success": True, "data": [{"id": "tx123"}]})
        return httpx.Response(404)

    transport = httpx.MockTransport(mock_handler)
    async with httpx.AsyncClient(transport=transport) as client:
        pool = RpcFailoverPool(
            primary_url="https://node1.tron.rpc",
            fallback_urls=["https://node2.tron.rpc", "https://node3.tron.rpc"],
            timeout_seconds=0.5,
            max_retries_per_node=1,
        )

        res = await pool.execute_request("/v1/transfers", {}, {}, http_client=client)
        assert res["success"] is True
        assert res["data"][0]["id"] == "tx123"

        # Verify all 3 nodes were attempted in priority order
        assert any("node1" in c for c in calls)
        assert any("node2" in c for c in calls)
        assert any("node3" in c for c in calls)

        # Node telemetry verification
        node1 = next(n for n in pool.nodes if "node1" in n.url)
        node2 = next(n for n in pool.nodes if "node2" in n.url)
        node3 = next(n for n in pool.nodes if "node3" in n.url)
        assert node1.failed_requests == 1
        assert node2.failed_requests == 1
        assert node3.successful_requests == 1


@pytest.mark.asyncio
async def test_failover_pool_all_nodes_tripped_raises_circuit_breaker_open_with_min_cooldown():
    """
    Verify that when all nodes have tripped their circuit breakers to OPEN,
    execute_request raises CircuitBreakerOpenError targeting the node with shortest cooldown.
    """
    pool = RpcFailoverPool(
        primary_url="https://primary.tron.rpc",
        fallback_urls=["https://backup.tron.rpc"],
        timeout_seconds=0.5,
        max_retries_per_node=1,
    )

    # Manually trip both nodes with different cooldowns
    node_primary = pool.nodes[0]
    node_backup = pool.nodes[1]

    node_primary.circuit_breaker._transition_to(CircuitState.OPEN)
    node_primary.circuit_breaker._current_timeout = 60.0  # Long cooldown

    node_backup.circuit_breaker._transition_to(CircuitState.OPEN)
    node_backup.circuit_breaker._current_timeout = 10.0  # Short cooldown

    with pytest.raises(CircuitBreakerOpenError) as exc_info:
        await pool.execute_request("/v1/test", {}, {})

    err = exc_info.value
    assert err.endpoint == "https://backup.tron.rpc"
    assert err.retry_after > 0.0
    assert "All RPC nodes in failover pool are circuit-broken" in str(err)


@pytest.mark.asyncio
async def test_failover_pool_strict_no_failover_on_400_invalid_address():
    """
    Verify that HTTP 400 immediately raises InvalidAddressError without attempting
    retries or failing over to fallback nodes, leaving the primary circuit breaker unaffected.
    """
    calls = []

    def mock_handler(request: httpx.Request):
        calls.append(str(request.url))
        return httpx.Response(400, json={"error": "class java.lang.IllegalArgumentException : Invalid address"})

    transport = httpx.MockTransport(mock_handler)
    async with httpx.AsyncClient(transport=transport) as client:
        pool = RpcFailoverPool(
            primary_url="https://node-a.tron.rpc",
            fallback_urls=["https://node-b.tron.rpc"],
            max_retries_per_node=3,
        )

        with pytest.raises(InvalidAddressError) as exc_info:
            await pool.execute_request("/v1/test", {}, {}, http_client=client)

        assert "Invalid address" in str(exc_info.value)
        # Exactly 1 call made (no retries, no fallback)
        assert len(calls) == 1
        assert "node-a" in calls[0]

        # Primary node circuit breaker was NOT penalised for client bad input
        node_a = pool.nodes[0]
        assert node_a.circuit_breaker.state == CircuitState.CLOSED
        assert node_a.circuit_breaker._consecutive_failures == 0


@pytest.mark.asyncio
async def test_failover_pool_rate_limit_429_backoff_and_failover():
    """
    Verify that HTTP 429 triggers backoff retry and, upon max retries exhausted,
    trips node's circuit breaker and fails over to secondary node.
    """
    calls = []

    def mock_handler(request: httpx.Request):
        url_str = str(request.url)
        calls.append(url_str)
        if "node1" in url_str:
            return httpx.Response(429, headers={"Retry-After": "0.01"}, text="Rate Limit Exceeded")
        return httpx.Response(200, json={"success": True, "data": []})

    transport = httpx.MockTransport(mock_handler)
    async with httpx.AsyncClient(transport=transport) as client:
        pool = RpcFailoverPool(
            primary_url="https://node1.tron.rpc",
            fallback_urls=["https://node2.tron.rpc"],
            max_retries_per_node=2,
        )

        resp = await pool.execute_request("/v1/test", {}, {}, http_client=client)
        assert resp["success"] is True

        # Node 1 was attempted twice (1 initial + 1 retry) before failing over to Node 2
        node1_calls = [c for c in calls if "node1" in c]
        node2_calls = [c for c in calls if "node2" in c]
        assert len(node1_calls) == 2
        assert len(node2_calls) == 1

        node1 = pool.nodes[0]
        assert node1.failed_requests == 2


@pytest.mark.asyncio
async def test_failover_pool_malformed_html_502_failover():
    """Verify that a node returning raw HTML (e.g. Cloudflare 502) is caught and fails over safely."""
    def mock_handler(request: httpx.Request):
        url_str = str(request.url)
        if "primary" in url_str:
            return httpx.Response(200, text="<!DOCTYPE html><html><body>502 Bad Gateway</body></html>")
        return httpx.Response(200, json={"success": True, "data": []})

    transport = httpx.MockTransport(mock_handler)
    async with httpx.AsyncClient(transport=transport) as client:
        pool = RpcFailoverPool(
            primary_url="https://primary.tron.rpc",
            fallback_urls=["https://secondary.tron.rpc"],
            max_retries_per_node=1,
        )

        resp = await pool.execute_request("/v1/test", {}, {}, http_client=client)
        assert resp["success"] is True
        assert pool.nodes[0].failed_requests == 1
        assert pool.nodes[1].successful_requests == 1


@pytest.mark.asyncio
async def test_failover_pool_malformed_json_array_failover():
    """Verify that a provider returning a JSON array instead of an object is caught and fails over."""
    def mock_handler(request: httpx.Request):
        url_str = str(request.url)
        if "primary" in url_str:
            return httpx.Response(200, json=[{"error": "unexpected list"}])
        return httpx.Response(200, json={"success": True, "data": []})

    transport = httpx.MockTransport(mock_handler)
    async with httpx.AsyncClient(transport=transport) as client:
        pool = RpcFailoverPool(
            primary_url="https://primary.tron.rpc",
            fallback_urls=["https://secondary.tron.rpc"],
            max_retries_per_node=1,
        )

        resp = await pool.execute_request("/v1/test", {}, {}, http_client=client)
        assert resp["success"] is True
        assert pool.nodes[0].failed_requests == 1


@pytest.mark.asyncio
async def test_failover_pool_success_false_error_flag():
    """Verify that when TronGrid returns 200 with {"success": false}, it is treated as a failure and fails over."""
    def mock_handler(request: httpx.Request):
        url_str = str(request.url)
        if "primary" in url_str:
            return httpx.Response(200, json={"success": False, "error": "Internal database lock timeout"})
        return httpx.Response(200, json={"success": True, "data": []})

    transport = httpx.MockTransport(mock_handler)
    async with httpx.AsyncClient(transport=transport) as client:
        pool = RpcFailoverPool(
            primary_url="https://primary.tron.rpc",
            fallback_urls=["https://secondary.tron.rpc"],
            max_retries_per_node=1,
        )

        resp = await pool.execute_request("/v1/test", {}, {}, http_client=client)
        assert resp["success"] is True
        assert pool.nodes[0].failed_requests == 1


@pytest.mark.asyncio
async def test_failover_pool_latency_tracking_and_health_reporting():
    """Verify that latency samples are tracked and reflected in get_health()."""
    node = RpcNode(url="https://test.tron.rpc", priority=0)
    assert node.avg_latency_ms == 0.0

    node.record_latency(10.0)
    node.record_latency(20.0)
    node.record_latency(30.0)
    assert math.isclose(node.avg_latency_ms, 20.0, rel_tol=1e-3)

    health = node.get_health()
    assert health["url"] == "https://test.tron.rpc"
    assert health["status"] == "HEALTHY"
    assert health["avg_latency_ms"] == 20.0


# ============================================================================
# Section 3: TRON Ingestion Hardening & Adversarial Payload Tests
# ============================================================================

def test_tron_address_validation_strict_boundaries():
    """
    Adversarially test TRON Base58Check address validation boundaries:
    - Must start with 'T'
    - Length must be exactly 34
    - Must not contain Base58 disallowed chars: 0, O, I, l
    - Must reject SQLi and script injection payloads
    """
    # Valid address
    assert validate_tron_address("TYDZSxdBzWnCuB4jF3K6j5X3qW7b9X1234") is True

    # Disallowed Base58 characters
    assert validate_tron_address("TYDZSxdBzWnCuB4jF3K6j5X3qW7b9X1230") is False  # '0' illegal
    assert validate_tron_address("TYDZSxdBzWnCuB4jF3K6j5X3qW7b9X123O") is False  # 'O' illegal
    assert validate_tron_address("TYDZSxdBzWnCuB4jF3K6j5X3qW7b9X123I") is False  # 'I' illegal
    assert validate_tron_address("TYDZSxdBzWnCuB4jF3K6j5X3qW7b9X123l") is False  # 'l' illegal

    # Invalid lengths
    assert validate_tron_address("TYDZSxdBzWnCuB4jF3K6j5X3qW7b9X123") is False   # 33 chars
    assert validate_tron_address("TYDZSxdBzWnCuB4jF3K6j5X3qW7b9X12345") is False # 35 chars

    # Invalid prefixes
    assert validate_tron_address("41DZSxdBzWnCuB4jF3K6j5X3qW7b9X12345") is False # Hex 41 prefix
    assert validate_tron_address("0xDZSxdBzWnCuB4jF3K6j5X3qW7b9X12345") is False # 0x prefix
    assert validate_tron_address("SYDZSxdBzWnCuB4jF3K6j5X3qW7b9X12345") is False # S prefix

    # Malicious SQLi & shell injections
    assert validate_tron_address("TYDZSxdBzWnCuB4jF3K6j5X3qW7b9X1234; DROP TABLE;") is False
    assert validate_tron_address("TYDZSxdBzWnCuB4jF3K6j5X3qW7b9X1234' OR '1'='1") is False

    # Edge cases
    assert validate_tron_address("") is False
    assert validate_tron_address(None) is False  # type: ignore


@pytest.mark.asyncio
async def test_tron_provider_get_transfers_rejects_invalid_address():
    """Verify TronProvider.get_transfers rejects invalid address before network query."""
    provider = TronProvider()
    with pytest.raises(InvalidAddressError) as exc_info:
        await provider.get_transfers("INVALID_ADDRESS_123")
    assert "Invalid TRON address format" in str(exc_info.value)


def test_tron_adversarial_revert_payloads():
    """
    Verify that normalize_transfer discards all variants of reverted transactions:
    - ret[0].contractRet in ("REVERT", "OUT_OF_ENERGY", "FAILED", "FAIL")
    - ret[0].ret in ("OUT_OF_TIME", "REVERT")
    - top-level finalResult, contract_ret, status flags
    """
    provider = TronProvider()

    adversarial_cases = [
        {"name": "contractRet REVERT", "payload": {"ret": [{"contractRet": "REVERT"}]}},
        {"name": "contractRet OUT_OF_ENERGY", "payload": {"ret": [{"contractRet": "OUT_OF_ENERGY"}]}},
        {"name": "contractRet FAILED", "payload": {"ret": [{"contractRet": "FAILED"}]}},
        {"name": "contractRet lower-case revert", "payload": {"ret": [{"contractRet": "revert"}]}},
        {"name": "ret OUT_OF_TIME", "payload": {"ret": [{"ret": "OUT_OF_TIME"}]}},
        {"name": "top-level finalResult FAILED", "payload": {"finalResult": "FAILED"}},
        {"name": "top-level contract_ret REVERT", "payload": {"contract_ret": "REVERT"}},
        {"name": "top-level status FAILURE", "payload": {"status": "FAILURE"}},
        {"name": "top-level result FAIL", "payload": {"result": "FAIL"}},
    ]

    for case in adversarial_cases:
        item = {
            "transaction_id": f"tx_{case['name'].replace(' ', '_')}",
            "type": "Transfer",
            "from": SAMPLE_TRON_ADDR,
            "to": SAMPLE_DEST_ADDR,
            "value": "1000000",
            "token_info": {"decimals": 6, "symbol": "USDT"},
            **case["payload"],
        }
        res = provider.normalize_transfer(item, USDT_CONTRACT)
        assert res is None, f"Failed to discard reverted transaction in case: {case['name']}"


def test_tron_adversarial_non_transfer_events():
    """Verify normalize_transfer discards non-transfer events (e.g. Approval, TransferFrom)."""
    provider = TronProvider()

    invalid_types = ["Approval", "TransferFrom", "Approve", "SetOwner", "RandomEvent", "12345"]
    for ev_type in invalid_types:
        item = {
            "transaction_id": f"tx_event_{ev_type}",
            "type": ev_type,
            "from": SAMPLE_TRON_ADDR,
            "to": SAMPLE_DEST_ADDR,
            "value": "1000000",
            "token_info": {"decimals": 6, "symbol": "USDT"},
        }
        assert provider.normalize_transfer(item, USDT_CONTRACT) is None

    # Verify case-insensitivity: "TRANSFER" in uppercase should pass
    valid_uppercase_item = {
        "transaction_id": "tx_valid_uppercase",
        "type": "TRANSFER",
        "from": SAMPLE_TRON_ADDR,
        "to": SAMPLE_DEST_ADDR,
        "value": "1000000",
        "token_info": {"decimals": 6, "symbol": "USDT"},
    }
    tx = provider.normalize_transfer(valid_uppercase_item, USDT_CONTRACT)
    assert tx is not None
    assert tx.tx_hash == "tx_valid_uppercase"


def test_tron_adversarial_amounts_and_decimals():
    """
    Verify handling of corrupted or malicious values:
    - Zero or negative amount -> discarded
    - Non-numeric amount string -> discarded without unhandled exception
    - Extreme amounts -> parsed safely with Decimal
    - Malformed token_info -> handled gracefully
    """
    provider = TronProvider()

    # Zero amount
    assert provider.normalize_transfer({
        "transaction_id": "tx_zero",
        "value": "0",
        "token_info": {"decimals": 6, "symbol": "USDT"},
    }, USDT_CONTRACT) is None

    # Negative amount
    assert provider.normalize_transfer({
        "transaction_id": "tx_negative",
        "value": "-500000",
        "token_info": {"decimals": 6, "symbol": "USDT"},
    }, USDT_CONTRACT) is None

    # Non-numeric amount
    assert provider.normalize_transfer({
        "transaction_id": "tx_str_amount",
        "value": "not_a_number",
        "token_info": {"decimals": 6, "symbol": "USDT"},
    }, USDT_CONTRACT) is None

    # Missing value
    assert provider.normalize_transfer({
        "transaction_id": "tx_missing_val",
        "token_info": {"decimals": 6, "symbol": "USDT"},
    }, USDT_CONTRACT) is None

    # Huge amount: 10^20 raw units
    huge_item = {
        "transaction_id": "tx_huge",
        "value": "100000000000000000000",
        "token_info": {"decimals": 6, "symbol": "USDT"},
    }
    tx = provider.normalize_transfer(huge_item, USDT_CONTRACT)
    assert tx is not None
    assert tx.amount_decimal == Decimal("100000000000000")

    # Missing or None token_info
    none_token_item = {
        "transaction_id": "tx_none_token",
        "value": "1000000",
        "token_info": None,
    }
    tx_none = provider.normalize_transfer(none_token_item, USDT_CONTRACT)
    # Safely handled without crashing
    assert tx_none is None or isinstance(tx_none, Transfer)


@pytest.mark.asyncio
async def test_tron_batch_deduplication_and_sanitization():
    """
    Verify that TronProvider.get_transfers sanitizes a mixed feed:
    filters out reverts, approvals, zeroes, and duplicates identical transfers.
    """
    mixed_raw_data = [
        # 1. Valid transfer 1
        {
            "transaction_id": "tx_valid_1",
            "type": "Transfer",
            "from": SAMPLE_TRON_ADDR,
            "to": SAMPLE_DEST_ADDR,
            "value": "1000000",
            "token_info": {"decimals": 6, "symbol": "USDT"},
            "block_timestamp": 1715000000000,
        },
        # 2. Reverted transfer
        {
            "transaction_id": "tx_reverted",
            "type": "Transfer",
            "from": SAMPLE_TRON_ADDR,
            "to": SAMPLE_DEST_ADDR,
            "value": "5000000",
            "ret": [{"contractRet": "REVERT"}],
            "token_info": {"decimals": 6, "symbol": "USDT"},
        },
        # 3. Non-transfer Approval
        {
            "transaction_id": "tx_approval",
            "type": "Approval",
            "from": SAMPLE_TRON_ADDR,
            "to": SAMPLE_DEST_ADDR,
            "value": "10000000",
            "token_info": {"decimals": 6, "symbol": "USDT"},
        },
        # 4. Duplicate of Valid transfer 1
        {
            "transaction_id": "tx_valid_1",
            "type": "Transfer",
            "from": SAMPLE_TRON_ADDR,
            "to": SAMPLE_DEST_ADDR,
            "value": "1000000",
            "token_info": {"decimals": 6, "symbol": "USDT"},
            "block_timestamp": 1715000000000,
        },
        # 5. Zero-value transfer
        {
            "transaction_id": "tx_zero",
            "type": "Transfer",
            "from": SAMPLE_TRON_ADDR,
            "to": SAMPLE_DEST_ADDR,
            "value": "0",
            "token_info": {"decimals": 6, "symbol": "USDT"},
        },
        # 6. Valid transfer 2
        {
            "transaction_id": "tx_valid_2",
            "type": "Transfer",
            "from": SAMPLE_TRON_ADDR,
            "to": SAMPLE_DEST_ADDR,
            "value": "2000000",
            "token_info": {"decimals": 6, "symbol": "USDT"},
            "block_timestamp": 1715000001000,
        },
    ]

    def mock_handler(request: httpx.Request):
        return httpx.Response(200, json={
            "success": True,
            "data": mixed_raw_data,
            "meta": {"fingerprint": "next_page_token"}
        })

    transport = httpx.MockTransport(mock_handler)
    async with httpx.AsyncClient(transport=transport) as client:
        provider = TronProvider(http_client=client)
        page = await provider.get_transfers(SAMPLE_TRON_ADDR)

        # Only tx_valid_1 and tx_valid_2 should survive
        assert len(page.transfers) == 2
        assert page.transfers[0].tx_hash == "tx_valid_1"
        assert page.transfers[1].tx_hash == "tx_valid_2"
        assert page.has_more is True
        assert page.next_cursor == "next_page_token"


# ============================================================================
# Section 4: Cache Resilience, LRU Eviction & Tiering Tests
# ============================================================================

def test_l1_lru_eviction_access_order_under_pressure():
    """
    Verify LRU eviction under memory pressure:
    - Cache capacity = 3
    - Inserting k1, k2, k3 fills cache
    - Accessing k1 moves it to MRU (most recently used)
    - Inserting k4 must evict k2 (least recently used), leaving k1, k3, k4
    """
    l1 = InMemoryL1Cache(max_entries=3, default_ttl=60.0)

    p1 = TransferPage(transfers=[], total_fetched=1)
    p2 = TransferPage(transfers=[], total_fetched=2)
    p3 = TransferPage(transfers=[], total_fetched=3)
    p4 = TransferPage(transfers=[], total_fetched=4)

    l1.set("k1", p1)
    l1.set("k2", p2)
    l1.set("k3", p3)
    assert len(l1) == 3

    # Access k1 to make it MRU
    hit = l1.get("k1")
    assert hit is not None

    # Insert k4 -> should evict k2
    l1.set("k4", p4)
    assert len(l1) == 3

    assert l1.get("k2") is None, "k2 should have been evicted as LRU"
    assert l1.get("k1") is not None
    assert l1.get("k3") is not None
    assert l1.get("k4") is not None


def test_l1_monotonic_ttl_expiration():
    """Verify that cached items expire and are deleted once monotonic TTL passes."""
    l1 = InMemoryL1Cache(max_entries=10, default_ttl=0.1)
    p = TransferPage(transfers=[], total_fetched=1)

    l1.set("k_expire", p, ttl=0.05)
    assert l1.get("k_expire") is not None

    # Sleep past expiration
    time.sleep(0.08)
    assert l1.get("k_expire") is None
    assert len(l1) == 0


def test_cache_deep_copy_isolation_mutability_attack():
    """
    Verify that mutating an object returned from the cache does NOT alter
    the internal cached data (defending against in-memory state poisoning).
    """
    l1 = InMemoryL1Cache(max_entries=5, default_ttl=60.0)

    original_transfer = Transfer(
        chain="TRON",
        tx_hash="tx_immutability",
        timestamp=datetime.now(timezone.utc),
        from_address=SAMPLE_TRON_ADDR,
        to_address=SAMPLE_DEST_ADDR,
        asset_contract=USDT_CONTRACT,
        asset_symbol="USDT",
        amount_raw=1000000,
        amount_decimal=Decimal("1.0"),
    )
    original_page = TransferPage(transfers=[original_transfer], total_fetched=1)
    l1.set("k_immutable", original_page)

    # 1. Fetch from cache and maliciously mutate returned instance
    retrieved_page = l1.get("k_immutable")
    assert retrieved_page is not None
    retrieved_page.transfers.clear()
    retrieved_page.total_fetched = 9999

    # 2. Fetch again -> internal cache must remain untouched
    fresh_page = l1.get("k_immutable")
    assert fresh_page is not None
    assert len(fresh_page.transfers) == 1
    assert fresh_page.transfers[0].tx_hash == "tx_immutability"
    assert fresh_page.total_fetched == 1


@pytest.mark.asyncio
async def test_two_tier_cache_volatile_vs_finalized_ttl():
    """
    Verify that head queries receive volatile TTL (300s) while historical/cursor
    queries receive finalized TTL (86400s) in Redis.
    """
    mock_redis = MockAsyncRedis()
    cache = TwoTierBlockchainCache(
        redis_client=mock_redis,
        default_ttl=300,
        finalized_ttl=86400,
    )

    page = TransferPage(transfers=[], total_fetched=0)

    # 1. Head query (is_finalized=False)
    key_head = cache.build_key("tron", SAMPLE_TRON_ADDR, USDT_CONTRACT, cursor=None)
    await cache.set(key_head, page, is_finalized=False)
    assert mock_redis.ttls[key_head] == 300

    # 2. Historical query (is_finalized=True)
    key_hist = cache.build_key("tron", SAMPLE_TRON_ADDR, USDT_CONTRACT, cursor="fp_12345")
    await cache.set(key_hist, page, is_finalized=True)
    assert mock_redis.ttls[key_hist] == 86400


@pytest.mark.asyncio
async def test_two_tier_cache_redis_outage_graceful_degradation():
    """
    Verify that when Redis experiences connection loss or outage,
    TwoTierBlockchainCache degrades gracefully without raising exceptions,
    continuing to serve from L1 in-memory.
    """
    failing_redis = MockAsyncRedis(should_fail=True)
    cache = TwoTierBlockchainCache(
        redis_client=failing_redis,
        default_ttl=300,
        finalized_ttl=86400,
    )

    key = cache.build_key("tron", SAMPLE_TRON_ADDR, USDT_CONTRACT)
    page = TransferPage(transfers=[], total_fetched=5)

    # set() should catch Redis error and still populate L1
    await cache.set(key, page, is_finalized=False)
    assert len(cache.l1) == 1

    # get() should return L1 hit even with Redis down
    hit = await cache.get(key)
    assert hit is not None
    assert hit.total_fetched == 5
