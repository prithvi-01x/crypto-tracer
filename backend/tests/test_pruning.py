import pytest
from decimal import Decimal
from datetime import datetime, timezone
from backend.app.domain.models import Transfer
from backend.app.adapters.fixture_provider import FixtureProvider
from backend.app.domain.tracing.engine import GraphEngine
from backend.app.domain.tracing.pruner import RelevancePruner

USDT_CONTRACT = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"


def make_transfer(
    tx_hash: str,
    from_addr: str,
    to_addr: str,
    amount_usdt: float,
    asset_symbol: str = "USDT",
    block_num: int = None,
    source: str = "trongrid_test",
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
        asset_symbol=asset_symbol,
        amount_raw=amount_raw,
        amount_decimal=amount_dec,
        source=source,
    )


@pytest.mark.asyncio
async def test_dust_threshold_pruning():
    suspect = "TSuspectDustWallet111111111111111"
    dest_dust = "TDustRecipient22222222222222222"
    dest_valid = "TValidRecipient33333333333333333"

    fixture = FixtureProvider({
        suspect: [
            make_transfer("tx_dust_1", suspect, dest_dust, 0.45),
            make_transfer("tx_valid_1", suspect, dest_valid, 2500.0),
        ]
    })

    engine = GraphEngine(provider=fixture, max_hops=2, min_relevant_usd=Decimal("1.00"))
    graph = await engine.trace(suspect)

    # Only suspect and valid recipient should be graph nodes
    node_addresses = {n.address for n in graph.nodes}
    assert suspect in node_addresses
    assert dest_valid in node_addresses
    assert dest_dust not in node_addresses
    assert len(graph.edges) == 1
    assert graph.edges[0].tx_hash == "tx_valid_1"

    # Pruned record check
    assert len(graph.pruned_records) == 1
    pruned = graph.pruned_records[0]
    assert pruned.tx_hash == "tx_dust_1"
    assert pruned.reason == "DUST"
    assert pruned.amount == Decimal("0.45")
    assert pruned.threshold == Decimal("1.00")
    assert pruned.hop == 1
    assert pruned.from_address == suspect
    assert pruned.to_address == dest_dust
    assert pruned.source == "trongrid_test"


@pytest.mark.asyncio
async def test_configurable_min_relevant_usd():
    suspect = "TSuspectConfigThresh111111111111"
    dest_low = "TLowValueRecipient22222222222222"
    dest_high = "THighValueRecipient3333333333333"

    fixture = FixtureProvider({
        suspect: [
            make_transfer("tx_low", suspect, dest_low, 50.0),
            make_transfer("tx_high", suspect, dest_high, 500.0),
        ]
    })

    # Custom threshold of $100.00
    engine = GraphEngine(provider=fixture, max_hops=2, min_relevant_usd=Decimal("100.00"))
    graph = await engine.trace(suspect)

    assert len(graph.edges) == 1
    assert graph.edges[0].tx_hash == "tx_high"
    assert len(graph.pruned_records) == 1
    assert graph.pruned_records[0].tx_hash == "tx_low"
    assert graph.pruned_records[0].reason == "DUST"
    assert graph.pruned_records[0].threshold == Decimal("100.00")


@pytest.mark.asyncio
async def test_asset_mismatch_pruning():
    suspect = "TSuspectAssetMismatch11111111111"
    dest_trx = "TTrxRecipient2222222222222222222"
    dest_usdt = "TUsdtRecipient333333333333333333"

    fixture = FixtureProvider({
        suspect: [
            make_transfer("tx_trx", suspect, dest_trx, 1000.0, asset_symbol="TRX"),
            make_transfer("tx_usdt", suspect, dest_usdt, 1000.0, asset_symbol="USDT"),
        ]
    })

    engine = GraphEngine(provider=fixture, max_hops=2, target_asset="USDT")
    graph = await engine.trace(suspect)

    assert len(graph.edges) == 1
    assert graph.edges[0].tx_hash == "tx_usdt"
    assert len(graph.pruned_records) == 1
    assert graph.pruned_records[0].tx_hash == "tx_trx"
    assert graph.pruned_records[0].reason == "ASSET_MISMATCH"
    assert graph.pruned_records[0].threshold == Decimal("0")


@pytest.mark.asyncio
async def test_branch_ranking_and_max_branch_limit():
    suspect = "TSuspectBranchFanOut111111111111"
    # Create 8 outgoing transfers with varying amounts
    transfers = [
        make_transfer(f"tx_branch_{i}", suspect, f"TRecipient{i:02d}11111111111111111", float(i * 100))
        for i in range(1, 9)  # 100, 200, 300, 400, 500, 600, 700, 800
    ]

    fixture = FixtureProvider({suspect: transfers})

    # Limit to top 3 branches per node
    engine = GraphEngine(provider=fixture, max_hops=2, max_branches_per_node=3)
    graph = await engine.trace(suspect)

    # Top 3 should be kept (800, 700, 600)
    assert len(graph.edges) == 3
    included_amounts = {e.amount for e in graph.edges}
    assert included_amounts == {Decimal("800.0"), Decimal("700.0"), Decimal("600.0")}

    # Remaining 5 should be pruned with BRANCH_LIMIT_EXCEEDED
    assert len(graph.pruned_records) == 5
    for p in graph.pruned_records:
        assert p.reason == "BRANCH_LIMIT_EXCEEDED"
        assert p.threshold == Decimal("3")
    pruned_amounts = {p.amount for p in graph.pruned_records}
    assert pruned_amounts == {Decimal("500.0"), Decimal("400.0"), Decimal("300.0"), Decimal("200.0"), Decimal("100.0")}


@pytest.mark.asyncio
async def test_three_tier_transfer_categorization_and_metadata():
    suspect = "TSuspectThreeTier111111111111111"
    dest1 = "TDestOne111111111111111111111111"
    dest2 = "TDestTwo222222222222222222222222"
    dest_dust = "TDustDest33333333333333333333333"

    # 4 raw transfers:
    # - 1 dust (0.20)
    # - 2 valid distinct transfers (100.0 and 200.0)
    # - 1 duplicate edge of dest1 (100.0)
    tx1 = make_transfer("tx_tier_1", suspect, dest1, 100.0, block_num=None)
    tx2 = make_transfer("tx_tier_2", suspect, dest2, 200.0, block_num=None)
    tx_dust = make_transfer("tx_dust", suspect, dest_dust, 0.20, block_num=None)
    tx_dup = make_transfer("tx_tier_1", suspect, dest1, 100.0, block_num=None)

    fixture = FixtureProvider({
        suspect: [tx1, tx2, tx_dust, tx_dup]
    })

    engine = GraphEngine(provider=fixture, max_hops=3, min_relevant_usd=Decimal("1.00"))
    graph = await engine.trace(suspect)

    # 1. Raw fetched: 4 transfers
    assert graph.meta["raw_transfers_fetched_count"] == 4

    # 2. Traversal relevant: 3 transfers passed pruner (tx1, tx2, tx_dup; tx_dust was pruned)
    assert graph.meta["traversal_relevant_transfers_count"] == 3

    # 3. Graph edges included: 2 edges (tx_dup was deduplicated)
    assert graph.meta["edges_included_count"] == 2
    assert len(graph.edges) == 2

    # Pruned records: 1
    assert graph.meta["pruned_transfers_count"] == 1
    assert len(graph.pruned_records) == 1

    # Deterministic metadata checks
    assert graph.meta["max_hops"] == 3
    assert graph.meta["max_hops_configured"] == 3
    assert graph.meta["min_relevant_usd"] == 1.0

    # block_number is None without inventing a value
    for edge in graph.edges:
        assert edge.block_number is None
        assert isinstance(edge.amount, Decimal)
        assert edge.source == "trongrid_test"


@pytest.mark.asyncio
async def test_pruned_branch_not_expanded():
    """
    Ensure that when a branch is pruned, the engine does NOT expand further hops from that pruned recipient.
    """
    w0 = "TSuspectRootNoExpand000000000000"
    w1_dust = "TDustHop1Wallet11111111111111111"
    w1_valid = "TValidHop1Wallet2222222222222222"
    w2_from_dust = "THop2FromDust3333333333333333333"
    w2_from_valid = "THop2FromValid44444444444444444"

    fixture = FixtureProvider({
        w0: [
            make_transfer("tx_dust_hop1", w0, w1_dust, 0.50),
            make_transfer("tx_valid_hop1", w0, w1_valid, 500.0),
        ],
        w1_dust: [
            make_transfer("tx_should_not_exist", w1_dust, w2_from_dust, 10000.0),
        ],
        w1_valid: [
            make_transfer("tx_valid_hop2", w1_valid, w2_from_valid, 490.0),
        ],
    })

    engine = GraphEngine(provider=fixture, max_hops=3, min_relevant_usd=Decimal("1.00"))
    graph = await engine.trace(w0)

    addresses = {n.address for n in graph.nodes}
    assert w0 in addresses
    assert w1_valid in addresses
    assert w2_from_valid in addresses

    # The dust branch recipient and its descendants must NEVER enter the graph
    assert w1_dust not in addresses
    assert w2_from_dust not in addresses

    # Edges should only be the valid path
    edge_txs = {e.tx_hash for e in graph.edges}
    assert edge_txs == {"tx_valid_hop1", "tx_valid_hop2"}
