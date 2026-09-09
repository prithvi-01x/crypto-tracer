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
    SweepResult,
    FanInResult,
    TemporalResult,
)
from backend.app.domain.evidence.models import (
    EvidenceClassification,
    EvidenceType,
    AuditEventType,
    EvidenceItem,
    AuditEvent,
)
from backend.app.domain.evidence.hasher import (
    compute_content_hash,
    canonicalize_payload,
)
from backend.app.domain.evidence.generator import EvidenceGenerator
from backend.app.persistence.models import Trace, Case
from backend.app.persistence.evidence_repository import EvidenceRepository
from backend.app.persistence.audit_repository import AuditRepository
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession


def make_test_edge(
    edge_id: str,
    tx_hash: str,
    from_addr: str,
    to_addr: str,
    amount_usdt: float,
    dt: datetime,
    hop: int = 1,
    pruned: bool = False,
    relevance_score: float = 1.0,
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
        source="trongrid",
        relevance_score=Decimal(str(relevance_score)),
        pruned=pruned,
    )


def make_test_node(
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


def test_deterministic_hashing_consistency():
    now = datetime(2026, 3, 10, 12, 0, 0, tzinfo=timezone.utc)
    payload_1 = {
        "tx_hash": "abc123hash",
        "amount": Decimal("1000.50"),
        "timestamp": now,
        "nested": {"z": 1, "a": 2},
    }
    # Keys in reverse order, same semantic data
    payload_2 = {
        "nested": {"a": 2, "z": 1},
        "amount": Decimal("1000.50"),
        "tx_hash": "abc123hash",
        "timestamp": now,
    }

    hash_1 = compute_content_hash(payload_1)
    hash_2 = compute_content_hash(payload_2)

    assert hash_1 == hash_2
    assert len(hash_1) == 64

    # Any mutation modifies the hash
    modified_payload = payload_1.copy()
    modified_payload["amount"] = Decimal("1000.51")
    hash_mod = compute_content_hash(modified_payload)
    assert hash_mod != hash_1


def test_audit_hash_deterministic():
    now = datetime(2026, 3, 10, 12, 0, 0, tzinfo=timezone.utc)
    payload_1 = {
        "case_id": "case-1",
        "event_type": "CASE_OPENED",
        "actor_id": "Investigator Alice",
        "timestamp": now.isoformat(),
        "action_summary": "Opened case for FIR/2026/001",
        "metadata": {"fir": "FIR/2026/001"},
    }
    payload_2 = {
        "metadata": {"fir": "FIR/2026/001"},
        "action_summary": "Opened case for FIR/2026/001",
        "timestamp": now.isoformat(),
        "actor_id": "Investigator Alice",
        "event_type": "CASE_OPENED",
        "case_id": "case-1",
    }
    hash_1 = compute_content_hash(payload_1)
    hash_2 = compute_content_hash(payload_2)
    assert hash_1 == hash_2
    assert len(hash_1) == 64


def test_evidence_generator_dag_creation():
    now = datetime(2026, 3, 10, 10, 0, 0, tzinfo=timezone.utc)
    suspect = "TSuspectWallet1111111111111111111"
    intermediate = "TIntermediateWallet2222222222222"
    binance_hot = "TMuA6YqfCeX8EhbfYEg5y7S4Dqz9Dw92eP"

    edge1 = make_test_edge("e1", "tx_1", suspect, intermediate, 10000.0, now, hop=1)
    edge2 = make_test_edge("e2", "tx_2", intermediate, binance_hot, 9950.0, now + timedelta(minutes=15), hop=2)

    node1 = make_test_node(suspect, "suspect", hop=0)
    node2 = make_test_node(intermediate, "intermediate", hop=1, total_received=10000.0, total_sent=9950.0)
    node3 = make_test_node(binance_hot, "endpoint", hop=2, total_received=9950.0)

    pruned = PrunedRecord(
        tx_hash="tx_pruned_3",
        from_address=intermediate,
        to_address="TDustWallet333",
        amount=Decimal("5.0"),
        asset="TRC20:USDT",
        hop=2,
        reason="DUST",
        threshold=Decimal("10.0"),
        timestamp=now + timedelta(minutes=16),
        source="trongrid",
    )

    graph = InvestigationGraph(
        nodes=[node1, node2, node3],
        edges=[edge1, edge2],
        pruned_records=[pruned],
        meta={"root_address": suspect, "max_hops": 3},
    )

    factors = FactorScores(
        direct_tag=0.0,
        downstream_vasp_match=1.0,
        sweep=1.0,
        fan_in=0.6,
        temporal=1.0,
    )
    explanations = FactorExplanations(
        direct_tag="Candidate is not directly tagged in registry.",
        downstream_vasp_match="Funds sweep into verified Binance hot wallet.",
        sweep="99.5% sweep detected.",
        fan_in="Moderate fan-in observed.",
        temporal="Rapid sweep within 15 minutes.",
    )
    sweep_res = SweepResult(
        sweep_ratio=0.995,
        dominant_ratio=1.0,
        received_usdt=Decimal("10000.00"),
        swept_usdt=Decimal("9950.00"),
        dominant_destination=binance_hot,
        destination_entity="Binance",
        destination_verified=True,
        is_sweep=True,
        is_strong_sweep=True,
        score=1.0,
        explanation="99.5% sweep detected.",
    )
    fan_in_res = FanInResult(
        distinct_senders_count=2,
        senders=[suspect],
        is_high_fan_in=False,
        score=0.6,
        explanation="Moderate fan-in observed.",
    )
    temporal_res = TemporalResult(
        deposit_time=now,
        sweep_time=now + timedelta(minutes=15),
        delay_seconds=900.0,
        delay_hours=0.25,
        delay_formatted="15 minutes",
        score=1.0,
        explanation="Rapid sweep within 15 minutes.",
    )

    candidate = VASPCandidate(
        candidate_address=intermediate,
        vasp_id="binance",
        vasp_name="Binance",
        hypothesis_label="Likely VASP: Binance",
        confidence=0.89,
        confidence_percentage=89.0,
        confidence_band="VERY HIGH",
        verification_status="VERIFIED",
        factors=factors,
        explanations=explanations,
        evidence_bullet_points=[
            "Downstream VASP match: This candidate is not directly tagged; its funds sweep into a verified Binance wallet.",
            "Sweep: 99.50% swept to verified Binance wallet within 15.0 minutes.",
        ],
        sweep_details=sweep_res,
        fan_in_details=fan_in_res,
        temporal_details=temporal_res,
    )

    report = AttributionReport(
        trace_id="trace-test-123",
        candidates=[candidate],
        best_candidate=candidate,
    )

    evidence_items = EvidenceGenerator.generate_trace_evidence(
        case_id="case-test-123",
        trace_id="trace-test-123",
        graph=graph,
        attribution_report=report,
    )

    assert len(evidence_items) > 0

    # 1. Check classifications
    classifications = {item.classification for item in evidence_items}
    assert EvidenceClassification.OBSERVED in classifications
    assert EvidenceClassification.DERIVED in classifications
    assert EvidenceClassification.INFERRED in classifications

    # 2. Check OBSERVED transaction items
    observed_tx_items = [
        item for item in evidence_items
        if item.classification == EvidenceClassification.OBSERVED and item.evidence_type == EvidenceType.TRANSACTION_RECORD
    ]
    assert len(observed_tx_items) == 2  # edge1 and edge2
    for tx_item in observed_tx_items:
        assert tx_item.parent_evidence_ids == []
        assert tx_item.source_reference is not None
        assert len(tx_item.content_hash) == 64

    # 3. Check DERIVED pruning decision item
    pruning_items = [
        item for item in evidence_items
        if item.evidence_type == EvidenceType.PRUNING_DECISION
    ]
    assert len(pruning_items) == 1
    assert pruning_items[0].payload["reason"] == "DUST"
    assert len(pruning_items[0].content_hash) == 64

    # 4. Check DERIVED sweep analysis links to observed tx items
    derived_sweep_items = [
        item for item in evidence_items
        if item.evidence_type == EvidenceType.SWEEP_ANALYSIS
    ]
    assert len(derived_sweep_items) == 1
    assert len(derived_sweep_items[0].parent_evidence_ids) > 0

    # 5. Check INFERRED attribution score item
    inferred_items = [
        item for item in evidence_items
        if item.classification == EvidenceClassification.INFERRED
    ]
    assert len(inferred_items) == 1
    attr_item = inferred_items[0]
    assert attr_item.evidence_type == EvidenceType.VASP_ATTRIBUTION
    assert attr_item.payload["confidence"] == 0.89
    assert attr_item.payload["vasp_id"] == "binance"
    # Must link to derived sweep, fan-in, temporal, and registry items
    assert len(attr_item.parent_evidence_ids) == 4


@pytest.mark.asyncio
async def test_evidence_and_audit_repositories(test_engine):
    session_factory = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        # Create case and trace
        case = Case(
            fir_number="FIR/2026/TEST/REPO",
            victim_reference="Victim Repo",
            loss_amount_inr=Decimal("5000.00"),
            ack_number="1930-REPO",
            suspect_wallet="TSuspectRepo111",
            chain="TRON",
            asset="USDT",
        )
        session.add(case)
        await session.commit()
        await session.refresh(case)

        trace = Trace(
            case_id=case.id,
            chain="TRON",
            input_type="address",
            input_value="TSuspectRepo111",
            asset="USDT",
            status="completed",
        )
        session.add(trace)
        await session.commit()
        await session.refresh(trace)

        # 1. Evidence persistence
        now = datetime.now(timezone.utc)
        item1 = EvidenceItem(
            id="ev_test_1",
            case_id=case.id,
            trace_id=trace.id,
            evidence_type=EvidenceType.TRANSACTION_RECORD,
            classification=EvidenceClassification.OBSERVED,
            title="Tx 1",
            source="trongrid",
            source_reference="tx_hash_1",
            payload={"amount": "5000", "tx_hash": "tx_hash_1"},
            parent_evidence_ids=[],
            content_hash=compute_content_hash({"amount": "5000", "tx_hash": "tx_hash_1"}),
            collected_at=now,
            analysis_timestamp=now,
        )
        item2 = EvidenceItem(
            id="ev_test_2",
            case_id=case.id,
            trace_id=trace.id,
            evidence_type=EvidenceType.VASP_ATTRIBUTION,
            classification=EvidenceClassification.INFERRED,
            title="Attribution: Binance",
            source="attribution_engine",
            source_reference="candidate_TAddr2",
            payload={"confidence": 0.95, "vasp": "Binance"},
            parent_evidence_ids=["ev_test_1"],
            content_hash=compute_content_hash({"confidence": 0.95, "vasp": "Binance"}),
            collected_at=now,
            analysis_timestamp=now,
        )

        saved = await EvidenceRepository.save_evidence_items(session, [item1, item2])
        assert len(saved) == 2

        # Query by trace
        trace_items = await EvidenceRepository.get_by_trace_id(session, trace.id)
        assert len(trace_items) == 2

        # Query by classification filter
        observed_items = await EvidenceRepository.get_by_trace_id(session, trace.id, classification=EvidenceClassification.OBSERVED)
        assert len(observed_items) == 1
        assert observed_items[0].id == "ev_test_1"

        # Query by ID
        fetched = await EvidenceRepository.get_by_id(session, "ev_test_2")
        assert fetched is not None
        assert fetched.evidence_type == "VASP_ATTRIBUTION"
        assert fetched.parent_evidence_ids == ["ev_test_1"]

        # 2. Audit Event persistence
        audit_ev = AuditEvent(
            id="audit_test_1",
            case_id=case.id,
            trace_id=trace.id,
            actor_id="IO Vikram",
            event_type=AuditEventType.CASE_OPENED,
            action_summary="Case opened for cyber investigation",
            metadata={"case_id": case.id},
            content_hash=compute_content_hash({"case_id": case.id, "actor": "IO Vikram"}),
            created_at=now,
        )
        recorded = await AuditRepository.record_event(session, audit_ev)
        assert recorded.id == "audit_test_1"

        case_audits = await AuditRepository.get_by_case_id(session, case.id)
        assert len(case_audits) == 1
        assert case_audits[0].event_type == AuditEventType.CASE_OPENED
        assert case_audits[0].actor_id == "IO Vikram"


@pytest.mark.asyncio
async def test_evidence_api_endpoints(async_client: AsyncClient, test_engine):
    suspect = "TSuspectApiTest1111111111111111111"
    # 1. Create a case
    case_res = await async_client.post(
        "/api/v1/cases",
        json={
            "fir_number": "FIR/2026/EVID/001",
            "victim_reference": "Victim Evidence Test",
            "loss_amount": "25000.00",
            "ack_1930": "1930-EVID-101",
            "suspect_wallet": suspect,
            "chain": "TRON",
            "asset": "USDT",
        },
    )
    assert case_res.status_code == 201
    case_id = case_res.json()["id"]

    now = datetime.now(timezone.utc)
    deposit = "TDepositApiTest2222222222222222222"
    binance = "TMuA6YqfCeX8EhbfYEg5y7S4Dqz9Dw92eP"

    graph_data = {
        "nodes": [
            {"id": suspect, "address": suspect, "chain": "TRON", "node_type": "suspect", "hop": 0, "total_received": "0", "total_sent": "25000", "transaction_count": 1},
            {"id": deposit, "address": deposit, "chain": "TRON", "node_type": "intermediate", "hop": 1, "total_received": "25000", "total_sent": "24900", "transaction_count": 2},
            {"id": binance, "address": binance, "chain": "TRON", "node_type": "endpoint", "hop": 2, "total_received": "24900", "total_sent": "0", "transaction_count": 1},
        ],
        "edges": [
            {"id": "e1", "tx_hash": "tx_api_1", "from_address": suspect, "to_address": deposit, "amount": "25000.00", "amount_raw": 25000000000, "asset": "TRC20:USDT", "timestamp": now.isoformat(), "hop": 1, "source": "trongrid", "relevance_score": "1.0", "pruned": False},
            {"id": "e2", "tx_hash": "tx_api_2", "from_address": deposit, "to_address": binance, "amount": "24900.00", "amount_raw": 24900000000, "asset": "TRC20:USDT", "timestamp": (now + timedelta(minutes=10)).isoformat(), "hop": 2, "source": "trongrid", "relevance_score": "1.0", "pruned": False},
        ],
        "pruned_records": [],
        "meta": {"root_address": suspect, "max_hops": 2},
    }

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

    # 2. Trigger attribution (which generates and persists evidence and audit events)
    attr_resp = await async_client.get(f"/api/v1/traces/{trace_id}/attribution")
    assert attr_resp.status_code == 200
    attr_data = attr_resp.json()
    assert len(attr_data["candidates"]) >= 1

    # 3. Query GET /api/v1/traces/{trace_id}/evidence
    ev_resp = await async_client.get(f"/api/v1/traces/{trace_id}/evidence")
    assert ev_resp.status_code == 200
    ev_data = ev_resp.json()
    assert ev_data["trace_id"] == trace_id
    assert ev_data["total_evidence_count"] > 0
    assert len(ev_data["items"]) > 0

    # Verify breakdown counts
    assert ev_data["observed_count"] >= 2  # transactions
    assert ev_data["derived_count"] >= 3   # metrics, sweeps, hops
    assert ev_data["inferred_count"] >= 1  # attribution score

    # 4. Query classification filtering: ?classification=OBSERVED
    obs_resp = await async_client.get(f"/api/v1/traces/{trace_id}/evidence?classification=OBSERVED")
    assert obs_resp.status_code == 200
    obs_data = obs_resp.json()
    for item in obs_data["items"]:
        assert item["classification"] == "OBSERVED"

    # 5. Query single evidence item
    inferred_items = [i for i in ev_data["items"] if i["classification"] == "INFERRED"]
    assert len(inferred_items) > 0
    inferred_id = inferred_items[0]["id"]

    single_ev = await async_client.get(f"/api/v1/evidence/{inferred_id}")
    assert single_ev.status_code == 200
    assert single_ev.json()["id"] == inferred_id

    # 6. Test Human Review Gate: POST /api/v1/cases/{case_id}/attributions/{candidate_address}/review
    review_resp = await async_client.post(
        f"/api/v1/cases/{case_id}/attributions/{deposit}/review",
        json={
            "trace_id": trace_id,
            "decision": "ACCEPT",
            "notes": "Confirmed 99.6% sweep directly into Binance hot wallet within 10 minutes. High confidence attribution approved for 91 CrPC notice preparation.",
            "actor_id": "IO-Rao-742",
        },
    )
    assert review_resp.status_code == 200
    rev_data = review_resp.json()
    assert rev_data["decision"] == "ACCEPT"
    assert rev_data["candidate_address"] == deposit
    assert rev_data["evidence_id"] is not None
    assert rev_data["audit_event_id"] is not None

    # Verify the created HUMAN_ACTION evidence item
    human_ev = await async_client.get(f"/api/v1/evidence/{rev_data['evidence_id']}")
    assert human_ev.status_code == 200
    assert human_ev.json()["classification"] == "HUMAN_ACTION"
    assert human_ev.json()["payload"]["actor_id"] == "IO-Rao-742"

    # 7. Test Audit Trail: GET /api/v1/cases/{case_id}/audit
    audit_resp = await async_client.get(f"/api/v1/cases/{case_id}/audit")
    assert audit_resp.status_code == 200
    audit_events = audit_resp.json()
    assert len(audit_events) >= 2  # ATTRIBUTION_VIEWED / ATTRIBUTION_ACCEPTED
    assert any(e["event_type"] == "ATTRIBUTION_ACCEPTED" for e in audit_events)

    # 8. Test Manual Audit Logging: POST /api/v1/cases/{case_id}/audit
    manual_audit = await async_client.post(
        f"/api/v1/cases/{case_id}/audit",
        json={
            "trace_id": trace_id,
            "event_type": "EVIDENCE_REVIEWED",
            "actor_id": "IO-Rao-742",
            "action_summary": "Investigator reviewed cryptographic hash and DAG chain of evidence.",
            "metadata": {"reviewed_items_count": ev_data["total_evidence_count"]},
        },
    )
    assert manual_audit.status_code == 201
    assert manual_audit.json()["event_type"] == "EVIDENCE_REVIEWED"
    assert len(manual_audit.json()["content_hash"]) == 64
