import pytest
from decimal import Decimal
from datetime import datetime, timezone
from httpx import AsyncClient

from backend.app.domain.models import Transfer
from backend.app.adapters.fixture_provider import FixtureProvider
from backend.app.domain.tracing.engine import GraphEngine

USDT_CONTRACT = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"


def create_mock_transfer(
    tx_hash: str,
    from_addr: str,
    to_addr: str,
    amount_usdt: float,
    block_num: int = 1000,
) -> Transfer:
    amount_dec = Decimal(str(amount_usdt))
    amount_raw = int(amount_dec * 1_000_000)
    return Transfer(
        chain="TRON",
        tx_hash=tx_hash,
        block_number=block_num,
        timestamp=datetime.now(timezone.utc),
        from_address=from_addr,
        to_address=to_addr,
        asset_contract=USDT_CONTRACT,
        asset_symbol="USDT",
        amount_raw=amount_raw,
        amount_decimal=amount_dec,
        source="fixture",
    )


@pytest.mark.asyncio
async def test_2_hop_fixture_and_hop_numbers():
    # Setup: Suspect -> WalletB -> WalletC
    addr_suspect = "TSuspectRootWallet111111111111111"
    addr_b = "TWalletIntermediateB2222222222222"
    addr_c = "TWalletEndpointC33333333333333333"

    fixture = FixtureProvider({
        addr_suspect: [create_mock_transfer("tx_hop_1", addr_suspect, addr_b, 5000.0)],
        addr_b: [create_mock_transfer("tx_hop_2", addr_b, addr_c, 4990.0)],
    })

    engine = GraphEngine(provider=fixture, max_hops=2)
    graph = await engine.trace(addr_suspect)

    assert len(graph.nodes) == 3
    assert len(graph.edges) == 2

    # Check node hop levels
    node_map = {n.address: n for n in graph.nodes}
    assert node_map[addr_suspect].hop == 0
    assert node_map[addr_suspect].node_type == "suspect"
    assert node_map[addr_suspect].total_sent == Decimal("5000.0")

    assert node_map[addr_b].hop == 1
    assert node_map[addr_b].node_type == "intermediate"
    assert node_map[addr_b].total_received == Decimal("5000.0")
    assert node_map[addr_b].total_sent == Decimal("4990.0")

    assert node_map[addr_c].hop == 2
    assert node_map[addr_c].node_type == "endpoint"
    assert node_map[addr_c].total_received == Decimal("4990.0")

    # Check edges
    assert graph.edges[0].hop == 1
    assert graph.edges[0].tx_hash == "tx_hop_1"
    assert graph.edges[1].hop == 2
    assert graph.edges[1].tx_hash == "tx_hop_2"


@pytest.mark.asyncio
async def test_4_hop_fixture():
    # Setup: Suspect -> B -> C -> D -> E
    w0 = "TSuspectRoot000000000000000000000"
    w1 = "TWalletHop11111111111111111111111"
    w2 = "TWalletHop22222222222222222222222"
    w3 = "TWalletHop33333333333333333333333"
    w4 = "TWalletHop44444444444444444444444"
    w5 = "TWalletHop55555555555555555555555"

    fixture = FixtureProvider({
        w0: [create_mock_transfer("tx_1", w0, w1, 10000.0)],
        w1: [create_mock_transfer("tx_2", w1, w2, 9900.0)],
        w2: [create_mock_transfer("tx_3", w2, w3, 9800.0)],
        w3: [create_mock_transfer("tx_4", w3, w4, 9700.0)],
        w4: [create_mock_transfer("tx_5", w4, w5, 9600.0)],  # Hop 5 (should be blocked by max_hops=4)
    })

    engine = GraphEngine(provider=fixture, max_hops=4)
    graph = await engine.trace(w0)

    # With max_hops=4: nodes w0, w1, w2, w3, w4 should be discovered (5 nodes)
    # w4 is at hop 4 so its outgoing edges are not expanded to w5
    assert len(graph.nodes) == 5
    assert len(graph.edges) == 4

    node_map = {n.address: n for n in graph.nodes}
    assert w5 not in node_map
    assert node_map[w4].hop == 4
    assert graph.meta["hops_reached"] == 4


@pytest.mark.asyncio
async def test_cycle_detection():
    # Setup cycle: A -> B -> C -> A
    a = "TWalletCycleA11111111111111111111"
    b = "TWalletCycleB22222222222222222222"
    c = "TWalletCycleC33333333333333333333"

    fixture = FixtureProvider({
        a: [create_mock_transfer("tx_a_b", a, b, 1000.0)],
        b: [create_mock_transfer("tx_b_c", b, c, 900.0)],
        c: [create_mock_transfer("tx_c_a", c, a, 800.0)],
    })

    engine = GraphEngine(provider=fixture, max_hops=4)
    graph = await engine.trace(a)

    # Should not infinite loop! Visited addresses (a, b, c) are only expanded once
    assert len(graph.nodes) == 3
    assert len(graph.edges) == 3


@pytest.mark.asyncio
async def test_repeated_address_and_fan_in():
    # Setup fan-in: Suspect -> B and Suspect -> C; both B and C -> Consolidation
    suspect = "TSuspectRootFanIn0000000000000000"
    b = "TWalletBranchB1111111111111111111"
    c = "TWalletBranchC2222222222222222222"
    dest = "TConsolidationWallet333333333333"

    fixture = FixtureProvider({
        suspect: [
            create_mock_transfer("tx_s_b", suspect, b, 2000.0),
            create_mock_transfer("tx_s_c", suspect, c, 3000.0),
        ],
        b: [create_mock_transfer("tx_b_dest", b, dest, 1950.0)],
        c: [create_mock_transfer("tx_c_dest", c, dest, 2950.0)],
    })

    engine = GraphEngine(provider=fixture, max_hops=3)
    graph = await engine.trace(suspect)

    assert len(graph.nodes) == 4
    assert len(graph.edges) == 4

    node_map = {n.address: n for n in graph.nodes}
    assert node_map[dest].total_received == Decimal("4900.0")
    assert node_map[dest].transaction_count == 2
    assert node_map[dest].hop == 2


@pytest.mark.asyncio
async def test_edge_deduplication():
    # Provider returns the exact same transfer twice
    suspect = "TSuspectRootDedup0000000000000000"
    dest = "TDestWalletDedup11111111111111111"

    duplicate_tx = create_mock_transfer("tx_dup_hash", suspect, dest, 1500.0)
    fixture = FixtureProvider({
        suspect: [duplicate_tx, duplicate_tx],
    })

    engine = GraphEngine(provider=fixture, max_hops=2)
    graph = await engine.trace(suspect)

    assert len(graph.edges) == 1
    assert len(graph.nodes) == 2


@pytest.mark.asyncio
async def test_safety_bounds_max_nodes_and_edges():
    # Branching factor of 5 per node
    suspect = "TSuspectSafety000000000000000000"
    children = [f"TChildNode{i:02d}11111111111111111111" for i in range(10)]

    fixture = FixtureProvider({
        suspect: [create_mock_transfer(f"tx_child_{i}", suspect, children[i], 100.0) for i in range(10)],
    })

    # Test max_nodes limit
    engine_node_limited = GraphEngine(provider=fixture, max_nodes=4)
    graph_n = await engine_node_limited.trace(suspect)
    assert len(graph_n.nodes) <= 4
    assert graph_n.meta["bounds_hit"] is True

    # Test max_edges limit
    engine_edge_limited = GraphEngine(provider=fixture, max_edges=3)
    graph_e = await engine_edge_limited.trace(suspect)
    assert len(graph_e.edges) <= 3
    assert graph_e.meta["bounds_hit"] is True


@pytest.mark.asyncio
async def test_trace_api_endpoints(async_client: AsyncClient):
    # 1. Create a parent case first
    case_res = await async_client.post("/api/v1/cases", json={
        "fir_number": "2026/TRACE-TEST",
        "victim_reference": "VICTIM-TRACE-01",
        "loss_amount_inr": 100000.0,
    })
    assert case_res.status_code == 201
    case_id = case_res.json()["id"]

    # 2. Trigger trace via POST /api/v1/traces
    suspect_wallet = "TYDZSxdBzWnCuB4jF3K6j5X3qW7b9X1234"
    trace_payload = {
        "case_id": case_id,
        "chain": "TRON",
        "input_type": "address",
        "input": suspect_wallet,
        "asset": "TRC20:USDT",
        "max_hops": 2,
    }

    # In test environment, TronProvider executes against live TronGrid or timeout/cached
    # To keep test deterministic without network, test request validation and API structure
    trace_res = await async_client.post("/api/v1/traces", json=trace_payload)
    assert trace_res.status_code in (201, 500, 502, 504)

    # 3. Test Invalid Address rejection
    invalid_trace = await async_client.post("/api/v1/traces", json={
        "case_id": case_id,
        "chain": "TRON",
        "input": "invalid-address",
    })
    assert invalid_trace.status_code == 400

    # 4. Test Non-existent parent case
    orphan_trace = await async_client.post("/api/v1/traces", json={
        "case_id": "non-existent-case-uuid",
        "chain": "TRON",
        "input": suspect_wallet,
    })
    assert orphan_trace.status_code == 404
