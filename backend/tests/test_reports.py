import io
import pytest
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from httpx import AsyncClient

from reportlab.pdfgen import canvas

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
)
from backend.app.domain.reports.graph_drawer import render_graph_drawing
from backend.app.domain.reports.dossier_generator import EvidenceDossierGenerator
from backend.app.domain.reports.bnss94_generator import BNSS94DraftGenerator
from backend.app.domain.reports.models import ReportType
from backend.app.persistence.models import Case, Trace
from backend.app.persistence.report_repository import ReportRepository
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession


def make_test_fixture_data():
    now = datetime(2026, 3, 10, 12, 0, 0, tzinfo=timezone.utc)
    suspect = "TSuspectWallet1111111111111111111"
    deposit = "TDepositConsolidation222222222222"
    binance = "TMuA6YqfCeX8EhbfYEg5y7S4Dqz9Dw92eP"

    node1 = GraphNode(id=suspect, address=suspect, chain="TRON", node_type="suspect", hop=0, total_received=Decimal("0"), total_sent=Decimal("50000.00"), transaction_count=1)
    node2 = GraphNode(id=deposit, address=deposit, chain="TRON", node_type="intermediate", hop=1, total_received=Decimal("50000.00"), total_sent=Decimal("49500.00"), transaction_count=2)
    node3 = GraphNode(id=binance, address=binance, chain="TRON", node_type="endpoint", hop=2, total_received=Decimal("49500.00"), total_sent=Decimal("0"), transaction_count=1)

    edge1 = GraphEdge(
        id="e1", tx_hash="tx_hop1_hash_abc123", from_address=suspect, to_address=deposit,
        amount=Decimal("50000.00"), amount_raw=50000000000, asset="TRC20:USDT",
        timestamp=now, hop=1, source="trongrid", relevance_score=Decimal("1.0"), pruned=False
    )
    edge2 = GraphEdge(
        id="e2", tx_hash="tx_hop2_hash_def456", from_address=deposit, to_address=binance,
        amount=Decimal("49500.00"), amount_raw=49500000000, asset="TRC20:USDT",
        timestamp=now + timedelta(minutes=15), hop=2, source="trongrid", relevance_score=Decimal("1.0"), pruned=False
    )

    pruned_rec = PrunedRecord(
        tx_hash="tx_dust_pruned_789", from_address=deposit, to_address="TDust333",
        amount=Decimal("2.50"), asset="TRC20:USDT", hop=2, reason="DUST",
        threshold=Decimal("10.00"), timestamp=now + timedelta(minutes=16), source="trongrid"
    )

    graph = InvestigationGraph(
        nodes=[node1, node2, node3],
        edges=[edge1, edge2],
        pruned_records=[pruned_rec],
        meta={"root_address": suspect, "max_hops": 3},
    )

    factors = FactorScores(
        direct_tag=0.0,
        downstream_vasp_match=1.0,
        sweep=1.0,
        fan_in=0.3,
        temporal=0.95,
    )
    explanations = FactorExplanations(
        direct_tag="Candidate wallet is not directly tagged in registry.",
        downstream_vasp_match="Funds sweep into verified Binance hot wallet.",
        sweep="Strong sweep consolidation (99.0%) into dominant exchange destination.",
        fan_in="Single-source deposit observed in traversal.",
        temporal="Automated sweep execution within 15 minutes.",
    )
    candidate = VASPCandidate(
        candidate_address=deposit,
        vasp_id="binance",
        vasp_name="Binance",
        hypothesis_label="Likely VASP: Binance",
        confidence=0.825,
        confidence_percentage=82.5,
        confidence_band="HIGH",
        verification_status="VERIFIED",
        factors=factors,
        explanations=explanations,
        evidence_bullet_points=[
            "Downstream VASP match: This candidate is not directly tagged; its funds sweep into a verified Binance wallet.",
            "Sweep consolidation: 99.0% swept to verified Binance wallet within 15 minutes.",
        ],
    )

    report = AttributionReport(
        trace_id="trace-test-rep-1",
        candidates=[candidate],
        best_candidate=candidate,
    )

    ev_item = EvidenceItem(
        id="ev_tx_abc123",
        case_id="case-test-rep-1",
        trace_id="trace-test-rep-1",
        evidence_type=EvidenceType.TRANSACTION_RECORD,
        classification=EvidenceClassification.OBSERVED,
        title="Transaction: 50,000.00 USDT",
        source="trongrid",
        source_reference="tx_hop1_hash_abc123",
        payload={"amount": "50000.00"},
        parent_evidence_ids=[],
        content_hash="a1b2c3d4e5f60718293a4b5c6d7e8f901234567890abcdef1234567890abcdef",
        collected_at=now,
        analysis_timestamp=now,
    )

    case = Case(
        id="case-test-rep-1",
        fir_number="FIR/2026/REP/401",
        victim_reference="Aarav Mehra (Task Fraud)",
        loss_amount_inr=Decimal("4150000.00"),
        ack_number="1930-DEL-40102",
        suspect_wallet=suspect,
        chain="TRON",
        asset="TRC20:USDT",
    )

    trace = Trace(
        id="trace-test-rep-1",
        case_id="case-test-rep-1",
        chain="TRON",
        input_value=suspect,
        asset="TRC20:USDT",
        graph_data=graph.model_dump(mode="json"),
    )

    return case, trace, graph, report, [ev_item]


def test_graph_drawing_generation():
    case, trace, graph, report, ev_items = make_test_fixture_data()
    drawing = render_graph_drawing(graph, width=500, height=140)
    assert drawing is not None
    assert drawing.width == 500
    assert drawing.height == 140
    assert len(drawing.contents) > 0


def test_evidence_dossier_pdf_generation():
    case, trace, graph, report, ev_items = make_test_fixture_data()

    pdf_bytes, content_hash, meta = EvidenceDossierGenerator.generate_pdf(
        case=case,
        trace=trace,
        graph=graph,
        attribution_report=report,
        evidence_items=ev_items,
        investigator_name="IO-Vikram-742",
        investigator_rank="Inspector of Police",
        police_station="Cyber Crime Police Station, Central District",
        include_graph_snapshot=True,
    )

    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 5000
    # Must be valid PDF format
    assert pdf_bytes.startswith(b"%PDF-")
    assert len(content_hash) == 64
    assert meta["case_id"] == case.id
    assert meta["attributed_vasp"] == "Binance"

    # Wording checks on PDF text content
    pdf_text = pdf_bytes.decode("latin1", errors="ignore")
    # Must NOT contain "conclusive attribution"
    assert "conclusive attribution" not in pdf_text.lower()
    # Must contain "accepted attribution hypothesis" or "investigative finding"
    assert "accepted attribution hypothesis" in pdf_text.lower() or "investigative finding" in pdf_text.lower()
    # Must contain statutory reference
    assert "bhartiya" in pdf_text.lower() or "sakshya" in pdf_text.lower() or "section 63" in pdf_text.lower() or "bsa" in pdf_text.lower()


def test_bnss94_draft_pdf_generation():
    case, trace, graph, report, ev_items = make_test_fixture_data()

    pdf_bytes, content_hash, meta = BNSS94DraftGenerator.generate_pdf(
        case=case,
        trace=trace,
        attribution_report=report,
        investigator_name="IO-Vikram-742",
        police_station="Cyber Crime Police Station, Central District",
        court_jurisdiction="Court of Chief Judicial Magistrate, Patiala House",
        urgency_hours=48,
    )

    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 5000
    assert pdf_bytes.startswith(b"%PDF-")
    assert len(content_hash) == 64
    assert meta["target_vasp"] == "Binance"

    pdf_text = pdf_bytes.decode("latin1", errors="ignore")
    # Must NOT contain "conclusive attribution"
    assert "conclusive attribution" not in pdf_text.lower()
    # Must prominently contain DRAFT warning
    assert "draft" in pdf_text.lower()
    assert "officer review" in pdf_text.lower()
    # Must contain statutory Section 94 BNSS references
    assert "section 94" in pdf_text.lower()
    assert "bnss" in pdf_text.lower()


@pytest.mark.asyncio
async def test_reports_api_endpoints(async_client: AsyncClient, test_engine):
    suspect = "TSuspectApiReports1111111111111111111"
    # 1. Create case
    case_res = await async_client.post(
        "/api/v1/cases",
        json={
            "fir_number": "FIR/2026/REP/901",
            "victim_reference": "Rohit Verma",
            "loss_amount": "200000.00",
            "ack_1930": "1930-REP-901",
            "suspect_wallet": suspect,
            "chain": "TRON",
            "asset": "USDT",
        },
    )
    assert case_res.status_code == 201
    case_id = case_res.json()["id"]

    now = datetime.now(timezone.utc)
    deposit = "TDepositApiRep2222222222222222222"
    binance = "TMuA6YqfCeX8EhbfYEg5y7S4Dqz9Dw92eP"

    graph_data = {
        "nodes": [
            {"id": suspect, "address": suspect, "chain": "TRON", "node_type": "suspect", "hop": 0, "total_received": "0", "total_sent": "5000", "transaction_count": 1},
            {"id": deposit, "address": deposit, "chain": "TRON", "node_type": "intermediate", "hop": 1, "total_received": "5000", "total_sent": "4950", "transaction_count": 2},
            {"id": binance, "address": binance, "chain": "TRON", "node_type": "endpoint", "hop": 2, "total_received": "4950", "total_sent": "0", "transaction_count": 1},
        ],
        "edges": [
            {"id": "e1", "tx_hash": "tx_rep_1", "from_address": suspect, "to_address": deposit, "amount": "5000.00", "amount_raw": 5000000000, "asset": "TRC20:USDT", "timestamp": now.isoformat(), "hop": 1, "source": "trongrid", "relevance_score": "1.0", "pruned": False},
            {"id": "e2", "tx_hash": "tx_rep_2", "from_address": deposit, "to_address": binance, "amount": "4950.00", "amount_raw": 4950000000, "asset": "TRC20:USDT", "timestamp": (now + timedelta(minutes=10)).isoformat(), "hop": 2, "source": "trongrid", "relevance_score": "1.0", "pruned": False},
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

    # 2. Call POST /api/v1/cases/{case_id}/reports/dossier
    dossier_res = await async_client.post(
        f"/api/v1/cases/{case_id}/reports/dossier",
        json={
            "trace_id": trace_id,
            "investigator_name": "IO-Vikram-742",
            "investigator_rank": "Inspector of Police",
            "police_station": "Cyber Cell, Crime Branch",
            "include_graph_snapshot": True,
            "notes": "Electronic evidence prepared for charge-sheet filing.",
        },
    )
    assert dossier_res.status_code == 201
    dossier_data = dossier_res.json()
    assert dossier_data["report_type"] == "EVIDENCE_DOSSIER"
    assert dossier_data["case_id"] == case_id
    assert len(dossier_data["content_hash"]) == 64
    assert dossier_data["file_size_bytes"] > 5000
    dossier_id = dossier_data["id"]

    # 3. Call POST /api/v1/cases/{case_id}/reports/bnss94
    bnss_res = await async_client.post(
        f"/api/v1/cases/{case_id}/reports/bnss94",
        json={
            "trace_id": trace_id,
            "target_vasp": "Binance",
            "candidate_address": deposit,
            "investigator_name": "IO-Vikram-742",
            "police_station": "Cyber Cell, Crime Branch",
            "court_jurisdiction": "Court of Chief Judicial Magistrate",
            "urgency_hours": 48,
        },
    )
    assert bnss_res.status_code == 201
    bnss_data = bnss_res.json()
    assert bnss_data["report_type"] == "SECTION_94_BNSS"
    assert len(bnss_data["content_hash"]) == 64
    bnss_id = bnss_data["id"]

    # 4. Call GET /api/v1/cases/{case_id}/reports
    list_res = await async_client.get(f"/api/v1/cases/{case_id}/reports")
    assert list_res.status_code == 200
    reports_list = list_res.json()
    assert len(reports_list) == 2
    report_types = {r["report_type"] for r in reports_list}
    assert "EVIDENCE_DOSSIER" in report_types
    assert "SECTION_94_BNSS" in report_types

    # 5. Call GET /api/v1/reports/{report_id}
    single_res = await async_client.get(f"/api/v1/reports/{dossier_id}")
    assert single_res.status_code == 200
    assert single_res.json()["id"] == dossier_id

    # 6. Call GET /api/v1/reports/{report_id}/download
    dl_res = await async_client.get(f"/api/v1/reports/{dossier_id}/download")
    assert dl_res.status_code == 200
    assert dl_res.headers["content-type"] == "application/pdf"
    assert len(dl_res.content) > 5000
    assert dl_res.content.startswith(b"%PDF-")

    # 7. Verify Audit Event logged
    audit_res = await async_client.get(f"/api/v1/cases/{case_id}/audit")
    assert audit_res.status_code == 200
    events = audit_res.json()
    assert any(e["event_type"] == "REPORT_GENERATED" for e in events)
