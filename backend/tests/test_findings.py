import pytest
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from httpx import AsyncClient

from backend.app.domain.models import InvestigationGraph, GraphNode, GraphEdge, PrunedRecord
from backend.app.domain.attribution.models import (
    AttributionReport,
    VASPCandidate,
    FactorScores,
    FactorExplanations,
)
from backend.app.domain.attribution.sweep import SweepResult
from backend.app.domain.attribution.temporal import TemporalResult
from backend.app.domain.attribution.fan_in import FanInResult
from backend.app.domain.evidence.models import EvidenceItem, EvidenceType, EvidenceClassification
from backend.app.domain.boundaries import BoundaryCode
from backend.app.domain.findings.models import FindingSeverity, FindingType, FindingStatus
from backend.app.domain.findings.generator import FindingsGenerator


def create_test_graph(
    hops: int = 4,
    nodes_count: int = 6,
    boundary_code: str = None,
    mixer_addr: str = None,
    bridge_addr: str = None,
) -> InvestigationGraph:
    nodes = []
    edges = []
    now = datetime.now(timezone.utc)

    # Root suspect
    root_addr = "TSuspectRootWallet111111111111111"
    nodes.append(GraphNode(
        id=root_addr,
        address=root_addr,
        chain="TRON",
        node_type="suspect",
        hop=0,
        total_received=Decimal("0"),
        total_sent=Decimal("10000.00"),
        transaction_count=1,
    ))

    prev_addr = root_addr
    for h in range(1, hops + 1):
        if mixer_addr and h == hops:
            curr_addr = mixer_addr
            n_type = "mixer"
        elif bridge_addr and h == hops:
            curr_addr = bridge_addr
            n_type = "bridge"
        elif h == hops:
            curr_addr = f"TDepositEndpoint{h}11111111111111"
            n_type = "endpoint"
        else:
            curr_addr = f"TIntermediateWallet{h}11111111111"
            n_type = "intermediate"

        nodes.append(GraphNode(
            id=curr_addr,
            address=curr_addr,
            chain="TRON",
            node_type=n_type,
            hop=h,
            total_received=Decimal("9900.00"),
            total_sent=Decimal("9800.00") if h < hops else Decimal("0"),
            transaction_count=2,
        ))

        edges.append(GraphEdge(
            id=f"edge_hop_{h}",
            tx_hash=f"txhash_hop_{h}_00000000000000000000",
            from_address=prev_addr,
            to_address=curr_addr,
            amount=Decimal("9900.00"),
            amount_raw=9900000000,
            asset="TRC20:USDT",
            timestamp=now + timedelta(minutes=h * 15),
            hop=h,
            source="fixture",
            relevance_score=Decimal("1.0"),
            pruned=False,
        ))
        prev_addr = curr_addr

    meta = {
        "source_wallet": root_addr,
        "max_hops": hops,
        "hops_reached": hops,
        "total_nodes": len(nodes),
        "total_edges": len(edges),
        "bounds_hit": bool(boundary_code),
        "is_partial": bool(boundary_code),
        "boundary_reached": boundary_code,
    }

    boundary_dict = None
    if boundary_code:
        boundary_dict = {
            "code": boundary_code,
            "category": "OBFUSCATION" if "MIXER" in boundary_code or "BRIDGE" in boundary_code else "LIMIT",
            "address": mixer_addr or bridge_addr or prev_addr,
            "hop": hops,
            "is_partial": True,
        }

    return InvestigationGraph(nodes=nodes, edges=edges, pruned_records=[], meta=meta, boundary=boundary_dict)


def test_generator_sweep_consolidation_and_rapid_sweep():
    graph = create_test_graph(hops=4)
    cand_addr = "TCandidateDepositWallet3333333333"

    candidate = VASPCandidate(
        candidate_address=cand_addr,
        vasp_id="binance",
        vasp_name="Binance",
        hypothesis_label="Likely VASP: Binance",
        confidence=0.825,
        confidence_percentage=82.5,
        confidence_band="HIGH",
        verification_status="VERIFIED",
        entity_category="vasp",
        factors=FactorScores(
            direct_tag=0.0,
            downstream_vasp_match=1.0,
            sweep=1.0,
            fan_in=0.75,
            temporal=0.92,
        ),
        explanations=FactorExplanations(
            direct_tag="None",
            downstream_vasp_match="Funds sweep into verified Binance hot wallet",
            sweep="Swept 99.8% of incoming volume",
            fan_in="Consolidated from 3 feeders",
            temporal="Swept within 14m 2s of receipt",
        ),
        sweep_details=SweepResult(
            received_usdt=Decimal("60000.00"),
            swept_usdt=Decimal("59900.00"),
            sweep_ratio=0.998,
            dominant_destination="TMuA6YqfCeX8EhbfYEg5y7S4Dqz9Dw92eP",
            destination_entity="Binance",
            destination_verified=True,
            is_sweep=True,
            is_strong_sweep=True,
            score=1.0,
            explanation="Swept 99.8% of incoming volume into dominant destination",
        ),
        temporal_details=TemporalResult(
            delay_seconds=842.0,
            delay_hours=0.2339,
            delay_formatted="14 minutes, 2 seconds",
            score=0.92,
            explanation="Funds swept within 14m 2s of receipt",
        ),
        fan_in_details=FanInResult(
            distinct_senders_count=3,
            is_high_fan_in=True,
            score=0.75,
            explanation="3 distinct senders",
        ),
    )

    report = AttributionReport(
        trace_id="test_trace_01",
        engine_version="0.1.0",
        disclaimer="Investigative hypothesis",
        candidates=[candidate],
        best_candidate=candidate,
    )

    now = datetime.now(timezone.utc)
    ev_sweep = EvidenceItem(
        id=f"ev_sweep_{cand_addr[:16]}",
        case_id="case_01",
        trace_id="test_trace_01",
        evidence_type=EvidenceType.SWEEP_ANALYSIS,
        classification=EvidenceClassification.DERIVED,
        title="Sweep Consolidation Analysis",
        description="Sweep analysis",
        source="sweep_analyzer",
        source_reference=cand_addr,
        payload={"sweep_ratio": 0.998},
        content_hash="hash_sweep_12345",
        collected_at=now,
        analysis_timestamp=now,
    )

    findings = FindingsGenerator.generate_findings(
        case_id="case_01",
        trace_id="test_trace_01",
        graph=graph,
        attribution_report=report,
        evidence_items=[ev_sweep],
    )

    # 1. Check Sweep Consolidation
    consolidation_f = next((f for f in findings if f.finding_type == FindingType.VASP_CONSOLIDATION), None)
    assert consolidation_f is not None
    assert consolidation_f.severity == FindingSeverity.HIGH
    assert consolidation_f.related_address == cand_addr
    assert consolidation_f.related_vasp == "Binance"
    assert "99.8%" in consolidation_f.description
    assert consolidation_f.graph_node_id == cand_addr
    assert len(consolidation_f.evidence_refs) >= 1
    assert consolidation_f.evidence_refs[0].id == ev_sweep.id

    # 2. Check Rapid Sweep
    rapid_f = next((f for f in findings if f.finding_type == FindingType.RAPID_SWEEP), None)
    assert rapid_f is not None
    assert rapid_f.severity == FindingSeverity.HIGH
    assert "14m 2s" in rapid_f.description
    assert rapid_f.related_address == cand_addr

    # 3. Check Fan-In Concentration
    fan_in_f = next((f for f in findings if f.finding_type == FindingType.FAN_IN_CONCENTRATION), None)
    assert fan_in_f is not None
    assert fan_in_f.severity == FindingSeverity.MEDIUM
    assert "3 feeder addresses" in fan_in_f.description

    # 4. Check Multi-Hop Layering
    layering_f = next((f for f in findings if f.finding_type == FindingType.MULTI_HOP_LAYERING), None)
    assert layering_f is not None
    assert layering_f.severity == FindingSeverity.MEDIUM
    assert "4 intermediate hops" in layering_f.description

    # 5. Check Trace Completed
    completed_f = next((f for f in findings if f.finding_type == FindingType.TRACE_COMPLETED), None)
    assert completed_f is not None
    assert completed_f.severity == FindingSeverity.INFO


def test_generator_mixer_boundary_detection():
    mixer_addr = "TMixerPoolAddress111111111111111111"
    graph = create_test_graph(hops=2, boundary_code="MIXER_BOUNDARY", mixer_addr=mixer_addr)

    findings = FindingsGenerator.generate_findings(
        case_id="case_mixer",
        trace_id="trace_mixer",
        graph=graph,
    )

    mixer_f = next((f for f in findings if f.finding_type == FindingType.MIXER_ENCOUNTERED), None)
    assert mixer_f is not None
    assert mixer_f.severity == FindingSeverity.HIGH
    assert mixer_f.related_address == mixer_addr
    assert "Mixer" in mixer_f.title
    assert "Cryptographic mixing" in mixer_f.description


def test_generator_bridge_boundary_detection():
    bridge_addr = "TBridgeGatewayAddress22222222222222"
    graph = create_test_graph(hops=3, boundary_code="BRIDGE_BOUNDARY", bridge_addr=bridge_addr)

    findings = FindingsGenerator.generate_findings(
        case_id="case_bridge",
        trace_id="trace_bridge",
        graph=graph,
    )

    bridge_f = next((f for f in findings if f.finding_type == FindingType.BRIDGE_ENCOUNTERED), None)
    assert bridge_f is not None
    assert bridge_f.severity == FindingSeverity.HIGH
    assert bridge_f.related_address == bridge_addr
    assert "Bridge" in bridge_f.title
    assert "external blockchain" in bridge_f.description


def test_generator_low_confidence_attribution():
    graph = create_test_graph(hops=1)
    cand_addr = "TUnknownWalletAddress99999999999999"

    candidate = VASPCandidate(
        candidate_address=cand_addr,
        vasp_id="unidentified",
        vasp_name="Unidentified Entity",
        hypothesis_label="Unidentified Entity",
        confidence=0.225,
        confidence_percentage=22.5,
        confidence_band="LOW",
        verification_status="UNVERIFIED",
        entity_category="unidentified",
        factors=FactorScores(
            direct_tag=0.0,
            downstream_vasp_match=0.0,
            sweep=0.0,
            fan_in=0.0,
            temporal=0.0,
        ),
        explanations=FactorExplanations(
            direct_tag="None",
            downstream_vasp_match="None",
            sweep="None",
            fan_in="None",
            temporal="None",
        ),
    )

    report = AttributionReport(
        trace_id="trace_low_conf",
        engine_version="0.1.0",
        disclaimer="Investigative hypothesis",
        candidates=[candidate],
        best_candidate=candidate,
    )

    findings = FindingsGenerator.generate_findings(
        case_id="case_low_conf",
        trace_id="trace_low_conf",
        graph=graph,
        attribution_report=report,
    )

    low_f = next((f for f in findings if f.finding_type == FindingType.LOW_CONFIDENCE_ATTRIBUTION), None)
    assert low_f is not None
    assert low_f.severity == FindingSeverity.LOW
    assert "22.5%" in low_f.description


def test_generator_empty_graph_and_duplicate_prevention():
    empty_graph = InvestigationGraph(nodes=[], edges=[], pruned_records=[], meta={})
    findings = FindingsGenerator.generate_findings(
        case_id="case_empty",
        trace_id="trace_empty",
        graph=empty_graph,
    )
    assert findings == []


@pytest.mark.asyncio
async def test_api_case_findings_e2e_and_status_review(async_client: AsyncClient):
    # 1. Seed canonical demo case
    seed_res = await async_client.post("/api/v1/demo/seed")
    assert seed_res.status_code in (200, 201)
    seed_data = seed_res.json()
    case_id = seed_data["case_id"]
    trace_id = seed_data["trace_id"]

    # 2. Query GET /api/v1/cases/{case_id}/findings
    res = await async_client.get(f"/api/v1/cases/{case_id}/findings")
    assert res.status_code == 200
    data = res.json()

    assert data["case_id"] == case_id
    assert data["total"] >= 3
    assert data["open_count"] == data["total"]
    assert data["high_count"] >= 1  # VASP Consolidation and/or Rapid Sweep

    finding_types = [f["finding_type"] for f in data["findings"]]
    assert "VASP_CONSOLIDATION" in finding_types
    assert "RAPID_SWEEP" in finding_types

    # Verify first finding structure
    first_finding = data["findings"][0]
    finding_id = first_finding["finding_id"]
    assert first_finding["status"] == "OPEN"
    assert first_finding["related_address"] is not None
    assert len(first_finding["title"]) > 0

    # 3. Query GET /api/v1/traces/{trace_id}/findings
    trace_res = await async_client.get(f"/api/v1/traces/{trace_id}/findings")
    assert trace_res.status_code == 200
    trace_findings = trace_res.json()
    assert trace_findings["total"] == data["total"]

    # 4. Review Finding: Transition OPEN -> REVIEWED
    review_res = await async_client.post(
        f"/api/v1/cases/{case_id}/findings/{finding_id}/review",
        json={
            "status": "REVIEWED",
            "notes": "Verified against Binance omnibus cluster deposit logs.",
            "reviewed_by": "Inspector P. Sharma",
        },
    )
    assert review_res.status_code == 200
    rev_data = review_res.json()
    assert rev_data["finding_id"] == finding_id
    assert rev_data["status"] == "REVIEWED"
    assert rev_data["reviewed_by"] == "Inspector P. Sharma"
    assert rev_data["review_notes"] == "Verified against Binance omnibus cluster deposit logs."

    # 5. Verify persistence across subsequent GET calls
    reload_res = await async_client.get(f"/api/v1/cases/{case_id}/findings")
    assert reload_res.status_code == 200
    reloaded_data = reload_res.json()
    assert reloaded_data["reviewed_count"] == 1
    assert reloaded_data["open_count"] == data["total"] - 1

    updated_f = next(f for f in reloaded_data["findings"] if f["finding_id"] == finding_id)
    assert updated_f["status"] == "REVIEWED"
    assert updated_f["reviewed_by"] == "Inspector P. Sharma"

    # 6. Review Finding: Transition REVIEWED -> DISMISSED
    dismiss_res = await async_client.post(
        f"/api/v1/cases/{case_id}/findings/{finding_id}/review",
        json={
            "status": "DISMISSED",
            "notes": "Exclusion acknowledged by senior counsel.",
            "reviewed_by": "Inspector P. Sharma",
        },
    )
    assert dismiss_res.status_code == 200
    assert dismiss_res.json()["status"] == "DISMISSED"

    reload_dismiss = await async_client.get(f"/api/v1/cases/{case_id}/findings")
    assert reload_dismiss.json()["dismissed_count"] == 1


@pytest.mark.asyncio
async def test_second_case_isolation_and_empty_state(async_client: AsyncClient):
    """
    Verify a newly registered second case has zero false alerts and does NOT leak canonical demo findings.
    """
    create_res = await async_client.post(
        "/api/v1/cases",
        json={
            "fir_number": "FIR/2026/ISOLATION/999",
            "victim_reference": "Victim Second Case",
            "loss_amount_inr": 25000.0,
            "chain": "TRON",
            "asset": "TRC20:USDT",
        },
    )
    assert create_res.status_code == 201
    second_case_id = create_res.json()["id"]

    # Verify zero findings for new case
    findings_res = await async_client.get(f"/api/v1/cases/{second_case_id}/findings")
    assert findings_res.status_code == 200
    data = findings_res.json()
    assert data["case_id"] == second_case_id
    assert data["total"] == 0
    assert data["open_count"] == 0
    assert data["findings"] == []


@pytest.mark.asyncio
async def test_api_findings_404_handling(async_client: AsyncClient):
    # Non-existent case
    res_case = await async_client.get("/api/v1/cases/non-existent-case-id-12345/findings")
    assert res_case.status_code == 404

    # Non-existent trace
    res_trace = await async_client.get("/api/v1/traces/non-existent-trace-id-12345/findings")
    assert res_trace.status_code == 404

    # Non-existent finding review
    res_review = await async_client.post(
        "/api/v1/cases/some-case-id/findings/non-existent-finding-id/review",
        json={"status": "REVIEWED"},
    )
    assert res_review.status_code == 404
