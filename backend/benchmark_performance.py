import asyncio
import time
from decimal import Decimal
from datetime import datetime, timezone
import statistics

from backend.app.domain.demo.canonical_data import (
    ADDR_SUSPECT_ROOT,
    CANONICAL_DEPOSIT_CANDIDATE,
    DemoFixtureProvider,
)
from backend.app.domain.tracing.engine import GraphEngine
from backend.app.domain.attribution.engine import AttributionEngine
from backend.app.domain.evidence.generator import EvidenceGenerator
from backend.app.domain.reports.dossier_generator import EvidenceDossierGenerator
from backend.app.domain.reports.bnss94_generator import BNSS94DraftGenerator
from backend.app.persistence.models import Case, Trace
from backend.app.persistence.db import async_session_factory
from backend.app.api.v1.endpoints.demo import seed_canonical_demo


async def benchmark_operations():
    results = {}

    print("================================================================================")
    print(" CRYPTO-TRACER PHASE 11: PERFORMANCE BENCHMARK SUITE")
    print("================================================================================\n")

    # 1. Benchmark Graph Traversal (In-Memory BFS Traversal)
    print("Benchmarking In-Memory 4-Hop Graph Traversal...")
    provider = DemoFixtureProvider()
    engine = GraphEngine(provider=provider, max_hops=4, min_relevant_usd=Decimal("1.0"), max_branches_per_node=5)
    
    durations = []
    sample_graph = None
    for _ in range(10):
        t0 = time.perf_counter()
        sample_graph = await engine.trace(source_address=ADDR_SUSPECT_ROOT)
        durations.append((time.perf_counter() - t0) * 1000)
    results["In-Memory Graph Traversal (4-Hop BFS)"] = durations

    # 2. Benchmark VASP Attribution Engine
    print("Benchmarking Explainable VASP Attribution Engine...")
    attr_engine = AttributionEngine()
    durations = []
    sample_report = None
    for _ in range(10):
        t0 = time.perf_counter()
        sample_report = attr_engine.evaluate_trace(trace_id="bench-trace", graph=sample_graph)
        durations.append((time.perf_counter() - t0) * 1000)
    results["VASP Attribution Evaluation (All Factors)"] = durations

    # 3. Benchmark Section 63 BSA Evidence Generation (Full Hash DAG)
    print("Benchmarking Section 63 BSA Evidence DAG Generation...")
    durations = []
    sample_evidence = None
    for _ in range(10):
        t0 = time.perf_counter()
        sample_evidence = EvidenceGenerator.generate_trace_evidence(
            case_id="bench-case",
            trace_id="bench-trace",
            graph=sample_graph,
            attribution_report=sample_report,
            config_snapshot={"max_hops": 4, "min_relevant_usd": 1.0, "execution_mode": "DEMO"},
        )
        durations.append((time.perf_counter() - t0) * 1000)
    results["Evidence DAG Generation (59 Items + Hashes)"] = durations

    # Create dummy Case and Trace models for PDF generation
    dummy_case = Case(
        id="bench-case",
        fir_number="FIR-2026-DEL-CY-0812",
        victim_reference="Ramesh Kumar",
        loss_amount_inr=Decimal("5000000.00"),
        ack_number="1930-DEL-2026-0812",
        suspect_wallet=ADDR_SUSPECT_ROOT,
        chain="TRON",
        asset="TRC20:USDT",
    )
    dummy_trace = Trace(
        id="bench-trace",
        case_id="bench-case",
        chain="TRON",
        input_value=ADDR_SUSPECT_ROOT,
        asset="TRC20:USDT",
        max_hops=4,
        execution_mode="DEMO",
    )

    # 4. Benchmark Evidence Dossier PDF Compilation
    print("Benchmarking Section 63 BSA Evidence Dossier PDF Generation...")
    durations = []
    for _ in range(5):
        t0 = time.perf_counter()
        pdf_bytes, report_hash, meta = EvidenceDossierGenerator.generate_pdf(
            case=dummy_case,
            trace=dummy_trace,
            graph=sample_graph,
            attribution_report=sample_report,
            evidence_items=sample_evidence,
            investigator_name="IO-Cyber-Delhi",
            include_graph_snapshot=False,
        )
        durations.append((time.perf_counter() - t0) * 1000)
    results["Evidence Dossier PDF Generation (Multi-Page)"] = durations

    # 5. Benchmark Section 94 BNSS Notice PDF Compilation
    print("Benchmarking Section 94 BNSS Notice PDF Generation...")
    durations = []
    for _ in range(5):
        t0 = time.perf_counter()
        pdf_bytes, report_hash, meta = BNSS94DraftGenerator.generate_pdf(
            case=dummy_case,
            trace=dummy_trace,
            attribution_report=sample_report,
            target_vasp_override="Binance",
            candidate_address_override=CANONICAL_DEPOSIT_CANDIDATE,
            investigator_name="IO-Cyber-Delhi",
        )
        durations.append((time.perf_counter() - t0) * 1000)
    results["Section 94 BNSS Notice PDF Generation"] = durations

    # 6. Benchmark Full End-to-End DEMO Seed Pipeline (Database + Tracing + Attribution + Evidence)
    print("Benchmarking Full DEMO Pipeline (POST /demo/seed)...")
    durations = []
    async with async_session_factory() as session:
        for _ in range(5):
            t0 = time.perf_counter()
            await seed_canonical_demo(db=session)
            durations.append((time.perf_counter() - t0) * 1000)
    results["Full DEMO Pipeline (Seed + Traversal + DB Persist)"] = durations

    # Print Formatted Results Table
    print("\n" + "=" * 80)
    print(f"{'OPERATION / PIPELINE STAGE':<45} | {'MIN':>8} | {'AVG':>8} | {'MAX':>8}")
    print("=" * 80)
    for op_name, times in results.items():
        min_t = min(times)
        avg_t = statistics.mean(times)
        max_t = max(times)
        print(f"{op_name:<45} | {min_t:7.1f}ms | {avg_t:7.1f}ms | {max_t:7.1f}ms")
    print("=" * 80)
    print("\nBenchmark completed successfully.")


if __name__ == "__main__":
    asyncio.run(benchmark_operations())
