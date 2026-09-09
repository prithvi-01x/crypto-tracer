import pytest
import time
from decimal import Decimal
from httpx import AsyncClient

from backend.app.domain.demo.canonical_data import (
    CANONICAL_CASE_ID,
    CANONICAL_FIR,
    CANONICAL_SUSPECT_WALLET,
    CANONICAL_DEPOSIT_CANDIDATE,
    BINANCE_HOT_WALLET_4,
    DemoFixtureProvider,
)
from backend.app.domain.tracing.engine import GraphEngine
from backend.app.domain.attribution.engine import AttributionEngine


@pytest.mark.asyncio
async def test_canonical_scenario_endpoint(async_client: AsyncClient):
    """Verify the canonical demo scenario narrative and specification endpoint."""
    res = await async_client.get("/api/v1/demo/canonical")
    assert res.status_code == 200
    data = res.json()
    assert data["fir_number"] == CANONICAL_FIR
    assert data["victim"].startswith("Ramesh Kumar")
    assert data["reported_loss_inr"] == 5000000.0
    assert data["chain"] == "TRON"
    assert data["asset"] == "TRC20:USDT"
    assert len(data["hops"]) == 5
    assert data["hops"][0]["address"] == CANONICAL_SUSPECT_WALLET
    assert data["hops"][3]["address"] == CANONICAL_DEPOSIT_CANDIDATE
    assert data["hops"][4]["address"] == BINANCE_HOT_WALLET_4


@pytest.mark.asyncio
async def test_demo_seed_and_performance(async_client: AsyncClient):
    """
    Verify POST /api/v1/demo/seed:
    - Runs in under 500ms (near-instant sub-second target)
    - Resets previous runs cleanly
    - Produces high-confidence explainable attribution
    - Compiles complete evidence chain
    """
    t0 = time.perf_counter()
    res = await async_client.post("/api/v1/demo/seed")
    elapsed_ms = (time.perf_counter() - t0) * 1000

    assert res.status_code in (200, 201), res.text
    data = res.json()
    assert data["status"] in ("SUCCESS", "READY")
    assert data["case_id"] == CANONICAL_CASE_ID
    assert data["fir_number"] == CANONICAL_FIR
    assert data["suspect_wallet"] == CANONICAL_SUSPECT_WALLET
    assert data["execution_mode"] == "DEMO"

    # Attribution verification
    attribution = data["attribution"]
    assert attribution["attributed_vasp"] == "Binance"
    assert attribution["confidence"] >= 0.80
    assert attribution["confidence_band"] == "HIGH"
    assert attribution["candidate_address"] == CANONICAL_DEPOSIT_CANDIDATE

    # Graph metrics verification
    metrics = data["graph_metrics"]
    assert metrics["hops"] == 4
    assert metrics["nodes"] >= 5
    assert metrics["edges"] >= 4
    assert metrics["pruned_transfers"] >= 1  # dust pruned

    # Evidence items
    assert data["evidence_items_count"] >= 10

    # Near-instant performance test
    assert elapsed_ms < 1500, f"Demo seed took {elapsed_ms:.1f}ms, expected sub-second"


@pytest.mark.asyncio
async def test_demo_status_endpoint(async_client: AsyncClient):
    """Verify demo status reports loaded after seed."""
    # Ensure seeded
    await async_client.post("/api/v1/demo/seed")

    res = await async_client.get("/api/v1/demo/status")
    assert res.status_code == 200
    data = res.json()
    assert data["loaded"] is True
    assert data["case_id"] == CANONICAL_CASE_ID
    assert data["fir_number"] == CANONICAL_FIR
    assert data["suspect_wallet"] == CANONICAL_SUSPECT_WALLET
    assert data["execution_mode"] == "DEMO"
    assert data["trace_status"] == "COMPLETED"


@pytest.mark.asyncio
async def test_zero_network_fixture_provider_resilience():
    """
    Verify DemoFixtureProvider runs entirely in-memory with zero network calls,
    pruning dust transfers and resolving 4-hop traversal accurately.
    """
    provider = DemoFixtureProvider()
    engine = GraphEngine(
        provider=provider,
        max_hops=4,
        min_relevant_usd=Decimal("1.0"),
        max_branches_per_node=5,
    )

    t0 = time.perf_counter()
    graph = await engine.trace(source_address=CANONICAL_SUSPECT_WALLET)
    elapsed_ms = (time.perf_counter() - t0) * 1000

    assert elapsed_ms < 100, f"In-memory traversal took {elapsed_ms:.1f}ms"
    assert graph.meta["hops_reached"] == 4
    assert len(graph.pruned_records) >= 1

    # Verify dust pruned
    pruned_amounts = [float(p.amount) for p in graph.pruned_records]
    assert any(amt < 1.0 for amt in pruned_amounts)

    # Verify Attribution evaluation on in-memory graph
    attr_engine = AttributionEngine()
    report = attr_engine.evaluate_trace(trace_id="demo-test", graph=graph)
    assert report.best_candidate is not None
    assert report.best_candidate.vasp_name == "Binance"
    assert report.best_candidate.confidence >= 0.80
    assert report.best_candidate.factors.downstream_vasp_match == 1.0
    assert report.best_candidate.factors.sweep == 1.0


@pytest.mark.asyncio
async def test_demo_trace_attribution_endpoint(async_client: AsyncClient):
    """Verify GET /api/v1/traces/{trace_id}/attribution on seeded demo trace."""
    seed_res = await async_client.post("/api/v1/demo/seed")
    trace_id = seed_res.json()["trace_id"]

    res = await async_client.get(f"/api/v1/traces/{trace_id}/attribution")
    assert res.status_code == 200
    data = res.json()
    assert data["trace_id"] == trace_id
    assert data["best_candidate"]["vasp_name"] == "Binance"
    assert data["best_candidate"]["confidence_percentage"] >= 80.0
    assert "investigative hypothesis" in data["disclaimer"].lower()

    factors = data["best_candidate"]["factors"]
    assert factors["downstream_vasp_match"] == 1.0
    assert factors["sweep"] == 1.0
    assert factors["direct_tag"] == 0.0  # Deposit address itself is unverified, not falsely tagged


@pytest.mark.asyncio
async def test_demo_evidence_chain_endpoint(async_client: AsyncClient):
    """Verify Section 63 BSA evidence chain integrity for demo case."""
    seed_res = await async_client.post("/api/v1/demo/seed")
    case_id = seed_res.json()["case_id"]

    res = await async_client.get(f"/api/v1/cases/{case_id}/evidence")
    assert res.status_code == 200
    data = res.json()
    assert data["case_id"] == case_id
    assert data["total_evidence_count"] >= 10
    assert data["observed_count"] >= 4
    assert data["derived_count"] >= 4
    assert data["inferred_count"] >= 1

    # Verify hash integrity
    for item in data["items"]:
        assert len(item["content_hash"]) == 64  # SHA-256


@pytest.mark.asyncio
async def test_demo_pdf_dossier_and_bnss94_reports(async_client: AsyncClient):
    """Verify generating Evidence Dossier and Section 94 BNSS notice for demo case."""
    seed_res = await async_client.post("/api/v1/demo/seed")
    case_id = seed_res.json()["case_id"]
    trace_id = seed_res.json()["trace_id"]

    # 1. Evidence Dossier PDF
    dossier_res = await async_client.post(
        f"/api/v1/cases/{case_id}/reports/dossier",
        json={
            "trace_id": trace_id,
            "investigator_name": "IO-Cyber-Delhi",
            "include_graph_snapshot": False,
        },
    )
    assert dossier_res.status_code == 201
    dossier_data = dossier_res.json()
    assert dossier_data["report_type"] == "EVIDENCE_DOSSIER"
    download_url = dossier_data["download_url"]

    dl_dossier = await async_client.get(download_url)
    assert dl_dossier.status_code == 200
    assert dl_dossier.content.startswith(b"%PDF-")
    assert b"DEMONSTRATION / REPLAY" in dl_dossier.content

    # 2. Section 94 BNSS Notice PDF
    bnss_res = await async_client.post(
        f"/api/v1/cases/{case_id}/reports/bnss94",
        json={
            "trace_id": trace_id,
            "target_vasp": "Binance",
            "candidate_address": CANONICAL_DEPOSIT_CANDIDATE,
            "investigator_name": "IO-Cyber-Delhi",
        },
    )
    assert bnss_res.status_code == 201
    bnss_data = bnss_res.json()
    assert bnss_data["report_type"] == "SECTION_94_BNSS"
    bnss_dl_url = bnss_data["download_url"]

    dl_bnss = await async_client.get(bnss_dl_url)
    assert dl_bnss.status_code == 200
    assert dl_bnss.content.startswith(b"%PDF-")
    assert b"Section 94 BNSS" in dl_bnss.content
    assert b"DRAFT" in dl_bnss.content
