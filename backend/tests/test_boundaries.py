import pytest
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from backend.app.adapters.base import (
    BlockchainProvider,
    ProviderTimeoutError,
    ProviderRateLimitError,
)
from backend.app.domain.models import Transfer, TransferPage, InvestigationGraph, GraphNode, GraphEdge, PrunedRecord
from backend.app.domain.boundaries import BoundaryCode, TraceExecutionStatus
from backend.app.domain.tracing.engine import GraphEngine
from backend.app.domain.attribution.engine import AttributionEngine
from backend.app.domain.attribution.registry import VASPRegistry
from backend.app.domain.reports.dossier_generator import EvidenceDossierGenerator
from backend.app.domain.reports.bnss94_generator import BNSS94DraftGenerator
from backend.app.domain.reports.models import ReportType
from backend.app.persistence.models import Case, Trace
from backend.app.persistence.trace_repository import TraceRepository
from backend.app.persistence.report_repository import ReportRepository


USDT_CONTRACT = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"


def make_transfer(
    tx_hash: str,
    from_addr: str,
    to_addr: str,
    amount_usdt: float,
    block_num: int = 1000,
    ts: Optional[datetime] = None,
) -> Transfer:
    amount_dec = Decimal(str(amount_usdt))
    amount_raw = int(amount_dec * 1_000_000)
    return Transfer(
        chain="TRON",
        tx_hash=tx_hash,
        block_number=block_num,
        timestamp=ts or datetime.now(timezone.utc),
        from_address=from_addr,
        to_address=to_addr,
        asset_contract=USDT_CONTRACT,
        asset_symbol="USDT",
        amount_raw=amount_raw,
        amount_decimal=amount_dec,
        source="fixture",
    )


class FaultyProvider(BlockchainProvider):
    """Provider that can simulate timeouts or rate limits on specific addresses."""

    def __init__(self, fixtures: Dict[str, List[Transfer]], timeouts: List[str] = None, rate_limits: List[str] = None):
        self.fixtures = fixtures
        self.timeouts = set(timeouts or [])
        self.rate_limits = set(rate_limits or [])

    async def get_transfers(
        self,
        address: str,
        asset_contract: Optional[str] = None,
        cursor: Optional[str] = None,
        limit: int = 20,
        direction: Optional[str] = None,
    ) -> TransferPage:
        if address in self.timeouts:
            raise ProviderTimeoutError(f"Simulated timeout fetching {address}")
        if address in self.rate_limits:
            raise ProviderRateLimitError(f"Simulated HTTP 429 rate limit fetching {address}")

        txs = self.fixtures.get(address, [])
        return TransferPage(
            transfers=txs,
            next_cursor=None,
            has_more=False,
            cached=False,
            total_fetched=len(txs),
        )


# ============================================================================
# 1. INPUT VALIDATION TESTS (Address, Chain, Asset)
# ============================================================================

@pytest.mark.asyncio
async def test_invalid_address_case_rejection(async_client):
    """Case creation with invalid address format returns 400 with INVALID_ADDRESS."""
    payload = {
        "fir_number": "FIR-BOUNDARY-001",
        "chain": "TRON",
        "asset": "USDT",
        "suspect_wallet": "invalid_tron_address_123",
        "victim_reference": "Victim A",
    }
    resp = await async_client.post("/api/v1/cases", json=payload)
    assert resp.status_code == 400
    assert "INVALID_ADDRESS" in str(resp.json()["detail"])


@pytest.mark.asyncio
async def test_invalid_address_trace_rejection(async_client):
    """Trace initiation with invalid address format returns 400 with INVALID_ADDRESS."""
    case_payload = {
        "fir_number": "FIR-BOUNDARY-002",
        "chain": "TRON",
        "asset": "USDT",
        "suspect_wallet": "TMuA6YqfCeX8EhbfYEg5y7S4Dqz9Dw92eP",
    }
    c_resp = await async_client.post("/api/v1/cases", json=case_payload)
    assert c_resp.status_code == 201
    case_id = c_resp.json()["id"]

    trace_payload = {
        "case_id": case_id,
        "chain": "TRON",
        "asset": "USDT",
        "input_type": "address",
        "input": "not_a_tron_wallet",
        "max_hops": 2,
    }
    t_resp = await async_client.post("/api/v1/traces", json=trace_payload)
    assert t_resp.status_code == 400
    assert "INVALID_ADDRESS" in str(t_resp.json()["detail"])


@pytest.mark.asyncio
async def test_unsupported_chain_rejection(async_client):
    """Trace initiation with unsupported chain returns 400 with UNSUPPORTED_CHAIN."""
    case_payload = {
        "fir_number": "FIR-BOUNDARY-003",
        "chain": "TRON",
        "asset": "USDT",
        "suspect_wallet": "TMuA6YqfCeX8EhbfYEg5y7S4Dqz9Dw92eP",
    }
    c_resp = await async_client.post("/api/v1/cases", json=case_payload)
    assert c_resp.status_code == 201
    case_id = c_resp.json()["id"]

    trace_payload = {
        "case_id": case_id,
        "chain": "BITCOIN",
        "asset": "USDT",
        "input_type": "address",
        "input": "TMuA6YqfCeX8EhbfYEg5y7S4Dqz9Dw92eP",
        "max_hops": 2,
    }
    t_resp = await async_client.post("/api/v1/traces", json=trace_payload)
    assert t_resp.status_code == 400
    assert "UNSUPPORTED_CHAIN" in str(t_resp.json()["detail"])


@pytest.mark.asyncio
async def test_unsupported_asset_rejection(async_client):
    """Trace initiation with unsupported asset returns 400 with UNSUPPORTED_ASSET."""
    case_payload = {
        "fir_number": "FIR-BOUNDARY-004",
        "chain": "TRON",
        "asset": "USDT",
        "suspect_wallet": "TMuA6YqfCeX8EhbfYEg5y7S4Dqz9Dw92eP",
    }
    c_resp = await async_client.post("/api/v1/cases", json=case_payload)
    assert c_resp.status_code == 201
    case_id = c_resp.json()["id"]

    trace_payload = {
        "case_id": case_id,
        "chain": "TRON",
        "asset": "DOGECOIN",
        "input_type": "address",
        "input": "TMuA6YqfCeX8EhbfYEg5y7S4Dqz9Dw92eP",
        "max_hops": 2,
    }
    t_resp = await async_client.post("/api/v1/traces", json=trace_payload)
    assert t_resp.status_code == 400
    assert "UNSUPPORTED_ASSET" in str(t_resp.json()["detail"])


# ============================================================================
# 2. PROVIDER TIMEOUT & RATE LIMIT BOUNDARIES
# ============================================================================

@pytest.mark.asyncio
async def test_provider_timeout_on_root_raises_error():
    """Timeout on the suspect wallet raises ProviderTimeoutError to be handled by API."""
    suspect = "TSuspectTimeoutRoot11111111111111"
    provider = FaultyProvider(fixtures={}, timeouts=[suspect])

    engine = GraphEngine(provider=provider, max_hops=2)
    with pytest.raises(ProviderTimeoutError):
        await engine.trace(suspect)


@pytest.mark.asyncio
async def test_provider_timeout_on_intermediate_produces_partial_graph():
    """Timeout on intermediate hop captures partial graph, marks is_partial=True and PROVIDER_TIMEOUT."""
    suspect = "TSuspectRoot111111111111111111111"
    intermediate = "TIntermediateTimeout222222222222"

    tx1 = make_transfer("tx_root_to_int", suspect, intermediate, 1000.0)

    fixtures = {
        suspect: [tx1],
        intermediate: [],  # will timeout
    }
    provider = FaultyProvider(fixtures=fixtures, timeouts=[intermediate])

    engine = GraphEngine(provider=provider, max_hops=3)
    graph = await engine.trace(suspect)

    assert graph.meta["is_partial"] is True
    assert graph.meta["boundary_reached"] == BoundaryCode.PROVIDER_TIMEOUT
    assert "timed out" in graph.meta["investigator_explanation"].lower()
    # Preserves root and hop 1 edge
    assert len(graph.nodes) == 2
    assert len(graph.edges) == 1
    assert graph.edges[0].to_address == intermediate


@pytest.mark.asyncio
async def test_provider_rate_limit_intermediate_produces_partial_graph():
    """HTTP 429 on intermediate hop marks is_partial=True and PROVIDER_RATE_LIMITED."""
    suspect = "TSuspectRootRate1111111111111111"
    intermediate = "TIntermediateRate22222222222222"

    tx1 = make_transfer("tx_rate_int", suspect, intermediate, 2500.0)

    fixtures = {
        suspect: [tx1],
        intermediate: [],  # will rate limit
    }
    provider = FaultyProvider(fixtures=fixtures, rate_limits=[intermediate])

    engine = GraphEngine(provider=provider, max_hops=3)
    graph = await engine.trace(suspect)

    assert graph.meta["is_partial"] is True
    assert graph.meta["boundary_reached"] == BoundaryCode.PROVIDER_RATE_LIMITED
    assert "rate limit" in graph.meta["investigator_explanation"].lower()
    assert len(graph.nodes) == 2
    assert len(graph.edges) == 1


# ============================================================================
# 3. GRAPH TRAVERSAL BOUNDARIES (Empty, Dust Pruned, Max Hops, Safety Limits)
# ============================================================================

@pytest.mark.asyncio
async def test_no_transfers_found_boundary():
    """Suspect wallet with 0 transactions produces NO_TRANSFERS_FOUND boundary."""
    suspect = "TSuspectEmpty0000000000000000000"
    provider = FaultyProvider(fixtures={suspect: []})

    engine = GraphEngine(provider=provider, max_hops=2)
    graph = await engine.trace(suspect)

    assert len(graph.nodes) == 1
    assert len(graph.edges) == 0
    assert graph.meta["boundary_reached"] == BoundaryCode.NO_TRANSFERS_FOUND
    assert "no outgoing transactions found" in graph.meta["investigator_explanation"].lower()

    # Attribution engine handling for 0 edges
    attr_engine = AttributionEngine()
    report = attr_engine.evaluate_trace("trace_empty_1", graph)
    assert len(report.candidates) == 0
    assert "no on-chain transaction edges" in report.meta["explanation"].lower()


@pytest.mark.asyncio
async def test_no_relevant_path_boundary_when_all_pruned():
    """Suspect wallet with only dust transactions produces NO_RELEVANT_PATH boundary."""
    suspect = "TSuspectDustOnly1111111111111111"
    tx_dust1 = make_transfer("tx_dust_1", suspect, "TDustDest1111111111111111111111", 0.10)
    tx_dust2 = make_transfer("tx_dust_2", suspect, "TDustDest2222222222222222222222", 0.50)

    provider = FaultyProvider(fixtures={suspect: [tx_dust1, tx_dust2]})

    # min_relevant_usd = 10.0, both transfers pruned
    engine = GraphEngine(provider=provider, max_hops=2, min_relevant_usd=10.0)
    graph = await engine.trace(suspect)

    assert len(graph.nodes) == 1
    assert len(graph.edges) == 0
    assert len(graph.pruned_records) == 2
    assert graph.meta["boundary_reached"] == BoundaryCode.NO_RELEVANT_PATH
    assert "pruned due to relevance filtering" in graph.meta["investigator_explanation"]


@pytest.mark.asyncio
async def test_max_hops_reached_boundary():
    """Deep chain respects max_hops and marks MAX_HOPS_REACHED."""
    w0 = "TRoot000000000000000000000000000"
    w1 = "THop1111111111111111111111111111"
    w2 = "THop2222222222222222222222222222"
    w3 = "THop3333333333333333333333333333"

    fixtures = {
        w0: [make_transfer("tx_1", w0, w1, 1000.0)],
        w1: [make_transfer("tx_2", w1, w2, 990.0)],
        w2: [make_transfer("tx_3", w2, w3, 980.0)],
    }
    provider = FaultyProvider(fixtures=fixtures)

    engine = GraphEngine(provider=provider, max_hops=2)
    graph = await engine.trace(w0)

    assert graph.meta["hops_reached"] == 2
    assert graph.meta["boundary_reached"] == BoundaryCode.MAX_HOPS_REACHED
    # w3 should not be expanded
    assert len(graph.edges) == 2


@pytest.mark.asyncio
async def test_max_nodes_safety_bound_halts_traversal():
    """Fan-out exceeding max_nodes triggers MAX_NODES_REACHED and marks is_partial=True."""
    root = "TRootFanOut000000000000000000000"
    txs = [
        make_transfer(f"tx_fan_{i}", root, f"TDestLeaf{i}0000000000000000000000", 100.0)
        for i in range(10)
    ]
    provider = FaultyProvider(fixtures={root: txs})

    # Restrict max_nodes to 4
    engine = GraphEngine(provider=provider, max_hops=2, max_nodes=4)
    graph = await engine.trace(root)

    assert graph.meta["bounds_hit"] is True
    assert graph.meta["is_partial"] is True
    assert graph.meta["boundary_reached"] == BoundaryCode.MAX_NODES_REACHED
    assert len(graph.nodes) <= 4


# ============================================================================
# 4. OBFUSCATION & CROSS-CHAIN BOUNDARIES (Mixers & Bridges)
# ============================================================================

@pytest.mark.asyncio
async def test_mixer_boundary_halts_expansion_and_marks_category():
    """Tornado Cash mock mixer halts traversal at mixer node; never claims de-anonymization."""
    suspect = "TSuspectMixer0000000000000000000"
    mixer = "TTornadoCashTronMockMixer111111111"
    mixer_out = "TPostMixerWallet2222222222222222"

    fixtures = {
        suspect: [make_transfer("tx_deposit_mixer", suspect, mixer, 50000.0)],
        mixer: [make_transfer("tx_mixer_outflow", mixer, mixer_out, 49900.0)],
    }
    provider = FaultyProvider(fixtures=fixtures)

    engine = GraphEngine(provider=provider, max_hops=3)
    graph = await engine.trace(suspect)

    # Must halt at mixer: mixer node present, but mixer_out NOT expanded!
    assert len(graph.nodes) == 2
    assert len(graph.edges) == 1
    assert graph.edges[0].to_address == mixer

    node_map = {n.address: n for n in graph.nodes}
    assert node_map[mixer].node_type == "mixer"
    assert graph.meta["boundary_reached"] == BoundaryCode.MIXER_BOUNDARY
    assert graph.meta["is_partial"] is True

    # Attribution engine verification
    attr_engine = AttributionEngine()
    report = attr_engine.evaluate_trace("trace_mixer_1", graph)
    assert len(report.candidates) >= 1
    mixer_candidate = report.candidates[0]
    assert mixer_candidate.entity_category == "mixer"
    assert "Mixer Boundary" in mixer_candidate.hypothesis_label
    assert "de-anonymization cannot be claimed" in mixer_candidate.explanations.direct_tag.lower()


@pytest.mark.asyncio
async def test_bridge_boundary_halts_expansion():
    """Cross-chain bridge halts single-chain TRON traversal and flags bridge category."""
    suspect = "TSuspectBridge000000000000000000"
    bridge = "TAllbridgeCrossChainGateway1111111"
    bridge_out = "TExternalChainWallet333333333333"

    fixtures = {
        suspect: [make_transfer("tx_bridge_deposit", suspect, bridge, 10000.0)],
        bridge: [make_transfer("tx_bridge_post", bridge, bridge_out, 9950.0)],
    }
    provider = FaultyProvider(fixtures=fixtures)

    engine = GraphEngine(provider=provider, max_hops=3)
    graph = await engine.trace(suspect)

    assert len(graph.nodes) == 2
    assert len(graph.edges) == 1
    assert graph.edges[0].to_address == bridge

    node_map = {n.address: n for n in graph.nodes}
    assert node_map[bridge].node_type == "bridge"
    assert graph.meta["boundary_reached"] == BoundaryCode.BRIDGE_BOUNDARY
    assert graph.meta["is_partial"] is True

    # Attribution engine verification
    attr_engine = AttributionEngine()
    report = attr_engine.evaluate_trace("trace_bridge_1", graph)
    assert len(report.candidates) >= 1
    bridge_candidate = report.candidates[0]
    assert bridge_candidate.entity_category == "bridge"
    assert "cross-chain bridge gateway" in bridge_candidate.explanations.direct_tag.lower()


# ============================================================================
# 5. ATTRIBUTION ANTI-FABRICATION & LOW CONFIDENCE BOUNDARY
# ============================================================================

@pytest.mark.asyncio
async def test_low_confidence_never_fabricates_vasp():
    """Low-confidence endpoint (< 0.40) is classified as Unidentified/Unhosted, never a fabricated VASP."""
    suspect = "TSuspectUnhosted0000000000000000"
    unhosted = "TUnhostedEndpointWallet999999999"

    # Suspect sends funds, but endpoint does not sweep anywhere and is not in registry
    fixtures = {
        suspect: [make_transfer("tx_to_unhosted", suspect, unhosted, 500.0)],
        unhosted: [],
    }
    provider = FaultyProvider(fixtures=fixtures)

    engine = GraphEngine(provider=provider, max_hops=2)
    graph = await engine.trace(suspect)

    attr_engine = AttributionEngine()
    report = attr_engine.evaluate_trace("trace_low_conf_1", graph)

    assert len(report.candidates) >= 1
    candidate = report.candidates[0]
    assert candidate.confidence < 0.40
    assert candidate.is_low_confidence is True
    assert candidate.vasp_id == "unknown_entity"
    assert "Unidentified" in candidate.vasp_name or "Unhosted" in candidate.vasp_name
    # Verification that no exchange (e.g. Binance, Huobi, KuCoin) was falsely tagged
    assert candidate.vasp_name not in ["Binance", "Huobi / HTX", "KuCoin", "OKX", "Kraken", "Coinbase"]


# ============================================================================
# 6. REPORT GENERATION BOUNDARIES & PARTIAL DOSSIER EXPORT
# ============================================================================

@pytest.mark.asyncio
async def test_partial_trace_evidence_dossier_compiles_with_disclosure():
    """Partial trace Evidence Dossier compiles successfully and contains operational boundary disclosures."""
    suspect = "TSuspectDossier00000000000000000"
    mixer = "TTornadoCashTronMockMixer111111111"

    node1 = GraphNode(id=suspect, address=suspect, chain="TRON", node_type="suspect", hop=0, total_received=Decimal("0"), total_sent=Decimal("10000.00"), transaction_count=1)
    node2 = GraphNode(id=mixer, address=mixer, chain="TRON", node_type="mixer", hop=1, total_received=Decimal("10000.00"), total_sent=Decimal("0"), transaction_count=1)

    edge1 = GraphEdge(
        id="e1", tx_hash="tx_mixer_hop1", from_address=suspect, to_address=mixer,
        amount=Decimal("10000.00"), amount_raw=10000000000, asset="TRC20:USDT",
        timestamp=datetime.now(timezone.utc), hop=1, source="trongrid", relevance_score=Decimal("1.0"), pruned=False
    )

    graph = InvestigationGraph(
        nodes=[node1, node2],
        edges=[edge1],
        pruned_records=[],
        meta={
            "root_address": suspect,
            "max_hops": 3,
            "is_partial": True,
            "boundary_reached": BoundaryCode.MIXER_BOUNDARY,
            "investigator_explanation": "Traversal halted at mixer boundary.",
        },
    )

    case = Case(
        id="case_partial_test",
        fir_number="FIR-PARTIAL-001",
        victim_reference="Victim Test",
        loss_amount_inr=Decimal("100000.00"),
        ack_number="1930-TEST-001",
        suspect_wallet=suspect,
        chain="TRON",
        asset="TRC20:USDT",
    )

    trace = Trace(
        id="trace_partial_test",
        case_id="case_partial_test",
        chain="TRON",
        input_value=suspect,
        asset="TRC20:USDT",
        status="PARTIAL",
        boundary_code="MIXER_BOUNDARY",
        investigator_summary="Traversal halted at mixer boundary.",
        graph_data=graph.model_dump(mode="json"),
    )

    pdf_bytes, sha256_hash, meta = EvidenceDossierGenerator.generate_pdf(
        case=case,
        trace=trace,
        graph=graph,
        attribution_report=None,
        evidence_items=[],
        notes="Partial trace audit due to mixer encounter.",
    )

    assert len(pdf_bytes) > 0
    assert sha256_hash is not None
    assert meta["report_hash"] == sha256_hash


@pytest.mark.asyncio
async def test_section94_bnss_blocked_for_mixer_or_low_confidence(async_client, test_engine):
    """Attempting to generate Section 94 notice for mixer returns 400 Bad Request."""
    suspect = "TSuspectRootS9411111111111111111"
    mixer = "TTornadoCashTronMockMixer111111111"

    # 1. Create case
    case_payload = {
        "fir_number": "FIR-MIXER-S94-001",
        "chain": "TRON",
        "asset": "USDT",
        "suspect_wallet": suspect,
    }
    c_resp = await async_client.post("/api/v1/cases", json=case_payload)
    assert c_resp.status_code == 201
    case_id = c_resp.json()["id"]

    # 2. Persist a trace record pointing to mixer boundary
    node1 = GraphNode(id=suspect, address=suspect, chain="TRON", node_type="suspect", hop=0, total_received=Decimal("0"), total_sent=Decimal("10000.00"), transaction_count=1)
    node2 = GraphNode(id=mixer, address=mixer, chain="TRON", node_type="mixer", hop=1, total_received=Decimal("10000.00"), total_sent=Decimal("0"), transaction_count=1)

    edge1 = GraphEdge(
        id="e1", tx_hash="tx_mixer_hop1", from_address=suspect, to_address=mixer,
        amount=Decimal("10000.00"), amount_raw=10000000000, asset="TRC20:USDT",
        timestamp=datetime.now(timezone.utc), hop=1, source="trongrid", relevance_score=Decimal("1.0"), pruned=False
    )

    graph = InvestigationGraph(
        nodes=[node1, node2],
        edges=[edge1],
        pruned_records=[],
        meta={
            "root_address": suspect,
            "max_hops": 3,
            "is_partial": True,
            "boundary_reached": BoundaryCode.MIXER_BOUNDARY,
            "investigator_explanation": "Traversal halted at mixer boundary.",
        },
    )

    session_factory = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        trace_record = Trace(
            case_id=case_id,
            chain="TRON",
            input_type="address",
            input_value=suspect,
            asset="USDT",
            status="PARTIAL",
            node_count=2,
            edge_count=1,
            boundary_code="MIXER_BOUNDARY",
            investigator_summary="Traversal halted at mixer boundary.",
            graph_data=graph.model_dump(mode="json"),
        )
        session.add(trace_record)
        await session.commit()
        await session.refresh(trace_record)
        trace_id = trace_record.id

    # 3. Attempt Section 94 generation targeting the mixer
    bnss_res = await async_client.post(
        f"/api/v1/cases/{case_id}/reports/bnss94",
        json={
            "trace_id": trace_id,
            "target_vasp": "Tornado Cash",
            "candidate_address": mixer,
            "investigator_name": "IO-Vikram-742",
            "police_station": "Cyber Cell, Crime Branch",
        },
    )
    assert bnss_res.status_code == 400
    assert "SECTION_94_PROHIBITED" in str(bnss_res.json()["detail"]) or "mixer" in str(bnss_res.json()["detail"]).lower()
