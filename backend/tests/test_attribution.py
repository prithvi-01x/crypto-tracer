import math
import pytest
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from httpx import AsyncClient

from backend.app.domain.models import InvestigationGraph, GraphNode, GraphEdge
from backend.app.domain.attribution.models import VASPEntry
from backend.app.domain.attribution.registry import VASPRegistry, default_registry
from backend.app.domain.attribution.sweep import SweepAnalyzer
from backend.app.domain.attribution.fan_in import FanInAnalyzer
from backend.app.domain.attribution.temporal import TemporalAnalyzer
from backend.app.domain.attribution.engine import AttributionEngine
from backend.app.persistence.models import Trace
from backend.app.persistence.attribution_repository import AttributionRepository

USDT_CONTRACT = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"
BINANCE_HOT = "TMuA6YqfCeX8EhbfYEg5y7S4Dqz9Dw92eP"
OKX_HOT = "TDezC4rW5AwtC564hVvA19oR91jW111111"


def make_graph_edge(
    edge_id: str,
    tx_hash: str,
    from_addr: str,
    to_addr: str,
    amount_usdt: float,
    dt: datetime,
    hop: int = 1,
) -> GraphEdge:
    amount_dec = Decimal(str(amount_usdt))
    return GraphEdge(
        id=edge_id,
        tx_hash=tx_hash,
        from_address=from_addr,
        to_address=to_addr,
        amount=amount_dec,
        amount_raw=int(amount_dec * 1_000_000),
        asset="TRC20:USDT",
        timestamp=dt,
        hop=hop,
        source="test_fixture",
        relevance_score=Decimal("1.0"),
        pruned=False,
    )


def make_graph_node(
    address: str,
    node_type: str = "intermediate",
    hop: int = 1,
    total_received: float = 0.0,
    total_sent: float = 0.0,
) -> GraphNode:
    return GraphNode(
        id=address,
        address=address,
        chain="TRON",
        node_type=node_type,
        hop=hop,
        total_received=Decimal(str(total_received)),
        total_sent=Decimal(str(total_sent)),
        transaction_count=1,
    )


def test_vasp_registry_lookups():
    registry = VASPRegistry()
    
    # Check known Binance hot wallet
    binance_entry = registry.get(BINANCE_HOT)
    assert binance_entry is not None
    assert binance_entry.vasp_id == "binance"
    assert "Binance" in binance_entry.entity_name
    assert binance_entry.verification_status == "VERIFIED"
    assert binance_entry.address_type == "hot_wallet"

    # Check OKX hot wallet
    okx_entry = registry.get(OKX_HOT)
    assert okx_entry is not None
    assert okx_entry.vasp_id == "okx"
    assert okx_entry.verification_status == "VERIFIED"

    # Check unknown address
    unknown = registry.get("TUnknownAddress111111111111111111111111")
    assert unknown is None
    assert not registry.is_known_vasp("TUnknownAddress111111111111111111111111")

    # Check versioning and listing
    assert registry.VERSION == "2026.1.0"
    all_entries = registry.list_all()
    assert len(all_entries) >= 7


def test_sweep_analyzer_calculations():
    analyzer = SweepAnalyzer(default_registry)
    now = datetime.now(timezone.utc)
    
    cand_addr = "TCandidateDepositWallet1111111111111"
    suspect_addr = "TSuspectWallet000000000000000000000"
    binance_dest = BINANCE_HOT

    # Scenario: Received $10,000, swept $9,800 to Binance (98% sweep ratio)
    edges = [
        make_graph_edge("e1", "tx_in_1", suspect_addr, cand_addr, 10000.00, now, hop=1),
        make_graph_edge("e2", "tx_sweep_1", cand_addr, binance_dest, 9800.00, now + timedelta(minutes=45), hop=2),
    ]
    nodes = [
        make_graph_node(suspect_addr, node_type="suspect", hop=0, total_sent=10000.00),
        make_graph_node(cand_addr, node_type="intermediate", hop=1, total_received=10000.00, total_sent=9800.00),
        make_graph_node(binance_dest, node_type="endpoint", hop=2, total_received=9800.00),
    ]
    graph = InvestigationGraph(nodes=nodes, edges=edges)

    res = analyzer.analyze(cand_addr, graph)
    assert res.received_usdt == Decimal("10000.00")
    assert res.swept_usdt == Decimal("9800.00")
    assert res.sweep_ratio == 0.98
    assert res.dominant_destination == binance_dest
    assert res.destination_entity == "Binance"
    assert res.destination_verified is True
    assert res.is_sweep is True
    assert res.is_strong_sweep is True
    assert res.score == 1.0  # ratio >= 0.90 with dominant concentration >= 0.85 -> score 1.0


def test_sweep_analyzer_no_sweep_and_partial_sweep():
    analyzer = SweepAnalyzer(default_registry)
    now = datetime.now(timezone.utc)
    cand_addr = "TCandidateWallet22222222222222222"
    suspect_addr = "TSuspectWallet000000000000000000000"
    other_addr = "TOtherWallet333333333333333333333333"

    # Scenario: Received $10,000, sent $1,000 (ratio 0.10 -> < 0.20 -> score 0.0)
    edges = [
        make_graph_edge("e1", "tx_in_1", suspect_addr, cand_addr, 10000.00, now, hop=1),
        make_graph_edge("e2", "tx_small_out", cand_addr, other_addr, 1000.00, now + timedelta(hours=1), hop=2),
    ]
    nodes = [
        make_graph_node(suspect_addr, node_type="suspect", hop=0, total_sent=10000.00),
        make_graph_node(cand_addr, node_type="intermediate", hop=1, total_received=10000.00, total_sent=1000.00),
    ]
    graph = InvestigationGraph(nodes=nodes, edges=edges)

    res = analyzer.analyze(cand_addr, graph)
    assert res.sweep_ratio == 0.10
    assert res.is_sweep is False
    assert res.score == 0.0


def test_fan_in_analyzer():
    analyzer = FanInAnalyzer()
    now = datetime.now(timezone.utc)
    dest_wallet = BINANCE_HOT

    edges = []
    nodes = [make_graph_node(dest_wallet, node_type="endpoint", hop=2)]
    for i in range(5):
        s_addr = f"TSenderWallet{i}111111111111111111111"
        nodes.append(make_graph_node(s_addr, node_type="intermediate", hop=1))
        edges.append(
            make_graph_edge(
                f"e_fan_{i}",
                f"tx_fan_in_{i}",
                s_addr,
                dest_wallet,
                2000.00,
                now + timedelta(minutes=i * 10),
                hop=2,
            )
        )

    graph = InvestigationGraph(nodes=nodes, edges=edges)
    res = analyzer.analyze(dest_wallet, graph)

    assert res.distinct_senders_count == 5
    assert res.is_high_fan_in is True
    assert res.score == 1.0  # >= 5 senders -> 1.0
    assert "High fan-in consolidation" in res.explanation


def test_temporal_analyzer_exponential_decay():
    analyzer = TemporalAnalyzer(tau_hours=4.0)
    now = datetime.now(timezone.utc)
    cand_addr = "TDepositWalletTemporal1111111111111"

    # Immediate sweep: delay = 0 hours -> score = exp(0) = 1.0
    edges_zero_delay = [
        make_graph_edge("e1", "tx_in", "TSender", cand_addr, 5000.0, now, hop=1),
        make_graph_edge("e2", "tx_out", cand_addr, "TReceiver", 5000.0, now, hop=2),
    ]
    graph_zero = InvestigationGraph(nodes=[], edges=edges_zero_delay)
    res_zero = analyzer.analyze(cand_addr, graph_zero)
    assert res_zero.delay_seconds == 0.0
    assert res_zero.delay_hours == 0.0
    assert res_zero.score == 1.0

    # 4 hours delay: delay = 4.0 hours -> score = exp(-4/4) = exp(-1) ~= 0.3679
    edges_4h_delay = [
        make_graph_edge("e1", "tx_in", "TSender", cand_addr, 5000.0, now, hop=1),
        make_graph_edge("e2", "tx_out", cand_addr, "TReceiver", 5000.0, now + timedelta(hours=4), hop=2),
    ]
    graph_4h = InvestigationGraph(nodes=[], edges=edges_4h_delay)
    res_4h = analyzer.analyze(cand_addr, graph_4h)
    assert res_4h.delay_hours == 4.0
    expected_score = round(math.exp(-1.0), 4)
    assert res_4h.score == expected_score


def test_attribution_engine_composite_score_exact_formula():
    """
    Verify: confidence = 0.35 * effective_entity_tag + 0.35 * sweep + 0.15 * fan_in + 0.15 * temporal
    where effective_entity_tag = direct_tag (if directly tagged) else 0.80 * downstream_vasp_match.
    """
    engine = AttributionEngine(registry=default_registry)
    now = datetime.now(timezone.utc)

    suspect = "TSuspectRoot00000000000000000000000"
    deposit_cand = "TIntermDeposit1111111111111111111111"
    binance_hot = BINANCE_HOT

    t_in = now
    t_out = now + timedelta(minutes=30)

    edges = [
        make_graph_edge("e1", "tx_hop1", suspect, deposit_cand, 10000.00, t_in, hop=1),
        make_graph_edge("e2", "tx_hop2", deposit_cand, binance_hot, 9900.00, t_out, hop=2),
    ]
    nodes = [
        make_graph_node(suspect, node_type="suspect", hop=0, total_sent=10000.00),
        make_graph_node(deposit_cand, node_type="intermediate", hop=1, total_received=10000.00, total_sent=9900.00),
        make_graph_node(binance_hot, node_type="endpoint", hop=2, total_received=9900.00),
    ]
    graph = InvestigationGraph(nodes=nodes, edges=edges)

    report = engine.evaluate_trace("trace_test_001", graph)

    assert report.trace_id == "trace_test_001"
    assert len(report.candidates) >= 1
    best = report.best_candidate
    assert best is not None

    f = best.factors
    # deposit_cand is not directly tagged:
    assert f.direct_tag == 0.0
    assert f.downstream_vasp_match == 1.0

    effective_entity_tag = 0.80 * f.downstream_vasp_match
    expected_confidence = round(
        0.35 * effective_entity_tag + 0.35 * f.sweep + 0.15 * f.fan_in + 0.15 * f.temporal,
        4
    )
    assert best.confidence == expected_confidence
    assert best.confidence_percentage == round(best.confidence * 100.0, 1)

    # Check legal disclaimer and hypothesis wording
    assert "Attribution is an investigative hypothesis" in report.disclaimer
    assert "not legal proof of account ownership" in report.disclaimer
    assert best.hypothesis_label.startswith("Likely VASP:")
    assert "(Evidence-backed attribution hypothesis)" in best.hypothesis_label
    assert best.confidence_band in ["VERY HIGH", "HIGH", "MODERATE", "LOW"]


def test_direct_verified_address():
    """
    1. A true direct_tag must mean the candidate address itself is directly present in the verified VASP registry.
    """
    engine = AttributionEngine(registry=default_registry)
    now = datetime.now(timezone.utc)
    suspect = "TSuspectRootDirectTag00000000000000"
    binance_hot = BINANCE_HOT

    edges = [
        make_graph_edge("e1", "tx_direct", suspect, binance_hot, 50000.00, now, hop=1),
    ]
    nodes = [
        make_graph_node(suspect, node_type="suspect", hop=0, total_sent=50000.00),
        make_graph_node(binance_hot, node_type="endpoint", hop=1, total_received=50000.00),
    ]
    graph = InvestigationGraph(nodes=nodes, edges=edges)

    report = engine.evaluate_trace("trace_direct_002", graph)
    best = report.best_candidate
    assert best is not None
    assert best.candidate_address == binance_hot
    assert best.vasp_id == "binance"
    # True direct tag
    assert best.factors.direct_tag == 1.0
    assert best.factors.downstream_vasp_match == 0.0
    assert best.verification_status == "VERIFIED"
    assert "Direct tag match: Wallet is a verified hot_wallet belonging to Binance" in best.explanations.direct_tag
    assert "N/A" in best.explanations.downstream_vasp_match
    assert any("Direct tag evidence" in ep for ep in best.evidence_bullet_points)


def test_downstream_only_vasp_match():
    """
    Candidate is not directly tagged and sends funds to Binance, but does NOT perform a sweep consolidation.
    direct_tag == 0.0, downstream_vasp_match == 1.0, sweep == 0.0.
    """
    engine = AttributionEngine(registry=default_registry)
    now = datetime.now(timezone.utc)
    cand_intermediate = "TUntaggedIntermediateDownstreamOnly1"
    suspect = "TSuspectSender00000000000000000000"
    binance = BINANCE_HOT

    # Received $50,000, but only forwarded $500 to Binance (sweep ratio 0.01 < 0.20 -> sweep = 0.0)
    edges = [
        make_graph_edge("e1", "tx_in", suspect, cand_intermediate, 50000.00, now, hop=1),
        make_graph_edge("e2", "tx_out_tiny", cand_intermediate, binance, 500.00, now + timedelta(hours=2), hop=2),
    ]
    nodes = [
        make_graph_node(suspect, node_type="suspect", hop=0, total_sent=50000.00),
        make_graph_node(cand_intermediate, node_type="intermediate", hop=1, total_received=50000.00, total_sent=500.00),
        make_graph_node(binance, node_type="endpoint", hop=2, total_received=500.00),
    ]
    graph = InvestigationGraph(nodes=nodes, edges=edges)

    report = engine.evaluate_trace("trace_downstream_only", graph)
    cand = next(c for c in report.candidates if c.candidate_address == cand_intermediate)

    # Must NOT have direct tag
    assert cand.factors.direct_tag == 0.0
    assert "not directly tagged" in cand.explanations.direct_tag

    # Has downstream match to verified Binance
    assert cand.factors.downstream_vasp_match == 1.0
    assert cand.explanations.downstream_vasp_match == "This candidate is not directly tagged; its funds sweep into a verified Binance wallet."

    # Sweep score must be 0.0
    assert cand.factors.sweep == 0.0

    # Overall confidence must remain LOW because there was no sweep consolidation
    assert cand.confidence < 0.50
    assert cand.confidence_band == "LOW"


def test_downstream_match_plus_sweep():
    """
    Candidate is not directly tagged; its funds sweep 99% into a verified Binance hot wallet.
    direct_tag == 0.0, downstream_vasp_match == 1.0, sweep == 1.0.
    """
    engine = AttributionEngine(registry=default_registry)
    now = datetime.now(timezone.utc)
    cand_intermediate = "TUntaggedIntermediateSweeper111111"
    suspect = "TSuspectSender00000000000000000000"
    binance = BINANCE_HOT

    edges = [
        make_graph_edge("e1", "tx_in", suspect, cand_intermediate, 20000.00, now, hop=1),
        make_graph_edge("e2", "tx_sweep", cand_intermediate, binance, 19800.00, now + timedelta(minutes=15), hop=2),
    ]
    nodes = [
        make_graph_node(suspect, node_type="suspect", hop=0, total_sent=20000.00),
        make_graph_node(cand_intermediate, node_type="intermediate", hop=1, total_received=20000.00, total_sent=19800.00),
        make_graph_node(binance, node_type="endpoint", hop=2, total_received=19800.00),
    ]
    graph = InvestigationGraph(nodes=nodes, edges=edges)

    report = engine.evaluate_trace("trace_sweep_match", graph)
    cand = next(c for c in report.candidates if c.candidate_address == cand_intermediate)

    # 1. No direct tag
    assert cand.factors.direct_tag == 0.0
    assert cand.explanations.direct_tag == "This candidate is not directly tagged in the VASP registry."

    # 2. Downstream match
    assert cand.factors.downstream_vasp_match == 1.0
    assert cand.explanations.downstream_vasp_match == "This candidate is not directly tagged; its funds sweep into a verified Binance wallet."

    # 3. Sweep score is 1.0
    assert cand.factors.sweep == 1.0

    # 4. High overall confidence
    assert cand.confidence >= 0.75
    assert cand.confidence_band in ["HIGH", "VERY HIGH"]

    # 5. Evidence list has Downstream VASP match and Sweep consolidation, NOT Direct tag evidence
    assert any("Downstream VASP match: This candidate is not directly tagged; its funds sweep into a verified Binance wallet." in ep for ep in cand.evidence_bullet_points)
    assert any("Sweep consolidation" in ep for ep in cand.evidence_bullet_points)
    assert not any("Direct tag evidence" in ep for ep in cand.evidence_bullet_points)


def test_no_direct_tag():
    """
    Verify that an untagged address NEVER receives a direct_tag > 0.0.
    """
    engine = AttributionEngine(registry=default_registry)
    now = datetime.now(timezone.utc)
    untagged_addr = "TRandomUntaggedWalletAddress999999"

    # Untagged address receives and sweeps
    edges = [
        make_graph_edge("e1", "tx_in", "TSender", untagged_addr, 10000.00, now, hop=1),
        make_graph_edge("e2", "tx_out", untagged_addr, BINANCE_HOT, 9900.00, now + timedelta(minutes=10), hop=2),
    ]
    nodes = [
        make_graph_node("TSender", node_type="suspect", hop=0, total_sent=10000.00),
        make_graph_node(untagged_addr, node_type="intermediate", hop=1, total_received=10000.00, total_sent=9900.00),
        make_graph_node(BINANCE_HOT, node_type="endpoint", hop=2, total_received=9900.00),
    ]
    graph = InvestigationGraph(nodes=nodes, edges=edges)

    report = engine.evaluate_trace("trace_no_direct", graph)
    cand = next(c for c in report.candidates if c.candidate_address == untagged_addr)

    assert cand.factors.direct_tag == 0.0
    assert cand.explanations.direct_tag == "This candidate is not directly tagged in the VASP registry."


def test_no_double_counting():
    """
    Verify that sweep mechanics and downstream VASP identity are strictly decoupled:
    - Sweep score evaluates ONLY the transaction consolidation mechanics (ratio & concentration).
    - Destination identity evaluates ONLY in downstream_vasp_match.
    """
    sweep_analyzer = SweepAnalyzer(registry=default_registry)
    engine = AttributionEngine(registry=default_registry)
    now = datetime.now(timezone.utc)

    # Graph A: Sweeps 99% to verified Binance hot wallet
    cand_a = "TCandidateSweeperToBinance1111111"
    edges_a = [
        make_graph_edge("ea1", "tx_in_a", "TSuspect", cand_a, 10000.00, now, hop=1),
        make_graph_edge("ea2", "tx_out_a", cand_a, BINANCE_HOT, 9900.00, now + timedelta(minutes=15), hop=2),
    ]
    nodes_a = [
        make_graph_node("TSuspect", node_type="suspect", hop=0, total_sent=10000.00),
        make_graph_node(cand_a, node_type="intermediate", hop=1, total_received=10000.00, total_sent=9900.00),
        make_graph_node(BINANCE_HOT, node_type="endpoint", hop=2, total_received=9900.00),
    ]
    graph_a = InvestigationGraph(nodes=nodes_a, edges=edges_a)

    # Graph B: Identical sweep of 99%, but to an unknown untagged address
    cand_b = "TCandidateSweeperToUnknown2222222"
    unknown_dest = "TUnknownDestinationWallet77777777"
    edges_b = [
        make_graph_edge("eb1", "tx_in_b", "TSuspect", cand_b, 10000.00, now, hop=1),
        make_graph_edge("eb2", "tx_out_b", cand_b, unknown_dest, 9900.00, now + timedelta(minutes=15), hop=2),
    ]
    nodes_b = [
        make_graph_node("TSuspect", node_type="suspect", hop=0, total_sent=10000.00),
        make_graph_node(cand_b, node_type="intermediate", hop=1, total_received=10000.00, total_sent=9900.00),
        make_graph_node(unknown_dest, node_type="endpoint", hop=2, total_received=9900.00),
    ]
    graph_b = InvestigationGraph(nodes=nodes_b, edges=edges_b)

    # 1. Assert Pure Sweep Analyzer scores are identical (NO double counting in sweep)
    res_a = sweep_analyzer.analyze(cand_a, graph_a)
    res_b = sweep_analyzer.analyze(cand_b, graph_b)
    assert res_a.score == res_b.score == 1.0

    # 2. Assert Attribution Engine evaluates factors cleanly
    report_a = engine.evaluate_trace("trace_a", graph_a)
    report_b = engine.evaluate_trace("trace_b", graph_b)

    cand_res_a = next(c for c in report_a.candidates if c.candidate_address == cand_a)
    cand_res_b = next(c for c in report_b.candidates if c.candidate_address == cand_b)

    # Both have direct_tag == 0.0
    assert cand_res_a.factors.direct_tag == 0.0
    assert cand_res_b.factors.direct_tag == 0.0

    # Sweep scores are identical
    assert cand_res_a.factors.sweep == cand_res_b.factors.sweep == 1.0

    # Destination VASP matches correctly differ
    assert cand_res_a.factors.downstream_vasp_match == 1.0
    assert cand_res_b.factors.downstream_vasp_match == 0.0

    # The difference in confidence score is exactly the entity tag weight: 0.35 * 0.80 * 1.0 = 0.28
    diff = cand_res_a.confidence - cand_res_b.confidence
    assert round(diff, 4) == round(0.35 * 0.80 * 1.0, 4)


def test_attribution_low_confidence_unidentified():
    """
    An unknown wallet with no sweep and no registry tags should result in LOW confidence.
    """
    engine = AttributionEngine()
    now = datetime.now(timezone.utc)
    suspect = "TSuspectRoot00000000000000000000000"
    unknown_dest = "TUnknownRandomAddress9999999999999"

    edges = [
        make_graph_edge("e1", "tx_rand", suspect, unknown_dest, 200.00, now, hop=1),
    ]
    nodes = [
        make_graph_node(suspect, node_type="suspect", hop=0, total_sent=200.00),
        make_graph_node(unknown_dest, node_type="endpoint", hop=1, total_received=200.00),
    ]
    graph = InvestigationGraph(nodes=nodes, edges=edges)

    report = engine.evaluate_trace("trace_unknown_003", graph)
    best = report.best_candidate
    assert best is not None
    assert best.vasp_id == "unknown_entity"
    assert best.verification_status == "UNVERIFIED"
    assert best.factors.direct_tag == 0.0
    assert best.factors.downstream_vasp_match == 0.0
    assert best.confidence < 0.50
    assert best.confidence_band == "LOW"


@pytest.mark.asyncio
async def test_attribution_api_and_persistence(async_client: AsyncClient, test_engine):
    """
    Test GET /api/v1/traces/{trace_id}/attribution with persistence in DB.
    """
    now = datetime.now(timezone.utc)
    suspect = "TSuspectApiWallet000000000000000000"
    intermediate = "TDepositApiWallet11111111111111111"
    binance = BINANCE_HOT

    graph_data = {
        "nodes": [
            {"id": suspect, "address": suspect, "chain": "TRON", "node_type": "suspect", "hop": 0, "total_sent": "10000.00", "total_received": "0"},
            {"id": intermediate, "address": intermediate, "chain": "TRON", "node_type": "intermediate", "hop": 1, "total_received": "10000.00", "total_sent": "9950.00"},
            {"id": binance, "address": binance, "chain": "TRON", "node_type": "endpoint", "hop": 2, "total_received": "9950.00", "total_sent": "0"},
        ],
        "edges": [
            {
                "id": "e_api_1",
                "tx_hash": "tx_api_1",
                "from_address": suspect,
                "to_address": intermediate,
                "amount": "10000.00",
                "amount_raw": 10000000000,
                "asset": "TRC20:USDT",
                "timestamp": now.isoformat(),
                "hop": 1,
            },
            {
                "id": "e_api_2",
                "tx_hash": "tx_api_2",
                "from_address": intermediate,
                "to_address": binance,
                "amount": "9950.00",
                "amount_raw": 9950000000,
                "asset": "TRC20:USDT",
                "timestamp": (now + timedelta(minutes=20)).isoformat(),
                "hop": 2,
            },
        ],
        "meta": {"max_hops": 2, "traversal_algorithm": "BFS"},
    }

    # 1. Create a Case and a Trace in the test database
    case_res = await async_client.post(
        "/api/v1/cases",
        json={
            "fir_number": "FIR/2026/ATTR/001",
            "victim_reference": "Victim Attribution Test",
            "loss_amount": "10000.00",
            "ack_1930": "1930-ATTR-999",
            "suspect_wallet": suspect,
            "chain": "TRON",
            "asset": "USDT",
        },
    )
    assert case_res.status_code == 201
    case_id = case_res.json()["id"]

    from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
    session_factory = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        trace_record = Trace(
            case_id=case_id,
            chain="TRON",
            input_type="address",
            input_value=suspect,
            asset="USDT",
            status="completed",
            node_count=3,
            edge_count=2,
            graph_data=graph_data,
        )
        session.add(trace_record)
        await session.commit()
        await session.refresh(trace_record)
        trace_id = trace_record.id

    # 2. Call GET /api/v1/traces/{trace_id}/attribution
    resp = await async_client.get(f"/api/v1/traces/{trace_id}/attribution")
    assert resp.status_code == 200
    data = resp.json()

    assert data["trace_id"] == trace_id
    assert "Attribution is an investigative hypothesis" in data["disclaimer"]
    assert len(data["candidates"]) >= 1
    
    best = data["best_candidate"]
    assert best is not None
    assert "Binance" in best["vasp"] or "binance" in best["vasp_id"]
    assert best["confidence"] > 0.75
    assert best["confidence_band"] in ["HIGH", "VERY HIGH"]
    # Intermediate wallet has direct_tag == 0.0 and downstream_vasp_match == 1.0
    assert best["factors"]["direct_tag"] == 0.0
    assert best["factors"]["downstream_vasp_match"] == 1.0
    assert best["factors"]["sweep"] == 1.0
    assert len(best["evidence_bullet_points"]) > 0
    assert any("Downstream VASP match: This candidate is not directly tagged; its funds sweep into a verified Binance wallet." in ep for ep in best["evidence_bullet_points"])

    # 3. Verify persistence in PostgreSQL / test DB
    async with session_factory() as session:
        persisted = await AttributionRepository.get_by_trace_id(session, trace_id)
        assert len(persisted) >= 1
        top_db = persisted[0]
        assert float(top_db.confidence) == best["confidence"]
        assert top_db.confidence_band == best["confidence_band"]
        assert top_db.vasp_id == best["vasp_id"]
        assert float(top_db.direct_tag_score) == 0.0
        assert float(top_db.downstream_match_score) == 1.0


@pytest.mark.asyncio
async def test_attribution_trace_not_found(async_client: AsyncClient):
    resp = await async_client.get("/api/v1/traces/non-existent-trace-id/attribution")
    assert resp.status_code == 404
