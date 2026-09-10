import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from backend.app.persistence.db import get_db
from backend.app.persistence.models import Case, Trace
from backend.app.persistence.case_repository import CaseRepository
from backend.app.persistence.trace_repository import TraceRepository
from backend.app.persistence.evidence_repository import EvidenceRepository
from backend.app.persistence.audit_repository import AuditRepository
from backend.app.persistence.attribution_repository import AttributionRepository
from backend.app.domain.evidence.generator import EvidenceGenerator
from backend.app.domain.evidence.models import AuditEvent, AuditEventType
from backend.app.domain.evidence.hasher import compute_content_hash
from backend.app.domain.tracing.engine import GraphEngine
from backend.app.domain.attribution.engine import AttributionEngine
from backend.app.domain.demo.canonical_data import (
    CANONICAL_CASE_ID,
    CANONICAL_FIR,
    CANONICAL_VICTIM,
    CANONICAL_LOSS_INR,
    CANONICAL_ACK,
    CANONICAL_CHAIN,
    CANONICAL_ASSET,
    CANONICAL_NOTES,
    ADDR_SUSPECT_ROOT,
    ADDR_HOP1_LAYERING,
    ADDR_HOP2_CONSOLIDATION,
    ADDR_HOP3_CANDIDATE,
    ADDR_HOP4_BINANCE_HOT,
    DemoFixtureProvider,
)

router = APIRouter(prefix="/demo", tags=["Demo Replay"])


def get_canonical_scenario_dict() -> Dict[str, Any]:
    return {
        "scenario_title": "SIH 2026: 4-Hop TRC-20 USDT Scam Layering into Binance",
        "narrative": (
            "A complainant reported ₹50 Lakhs fraud originating from a task-based investment scheme. "
            "Crypto-Tracer ingests the unhosted suspect wallet, traverses 4 hops through mule and consolidation accounts, "
            "filters dust noise, detects a 99.8% automated sweep consolidation within 14 minutes into Binance Hot Wallet 4, "
            "and generates Section 63 BSA compliant evidence and Section 94 BNSS production requests."
        ),
        "fir_number": CANONICAL_FIR,
        "victim": CANONICAL_VICTIM,
        "reported_loss_inr": float(CANONICAL_LOSS_INR),
        "reported_loss_usdt": 60000.0,
        "chain": CANONICAL_CHAIN,
        "asset": CANONICAL_ASSET,
        "hops": [
            {
                "hop": 0,
                "role": "Root Suspect Unhosted Wallet",
                "address": ADDR_SUSPECT_ROOT,
                "description": "Primary theft intake wallet receiving victim deposits.",
            },
            {
                "hop": 1,
                "role": "Layering Intermediary Mule",
                "address": ADDR_HOP1_LAYERING,
                "description": "First-tier split account (50,000 USDT) with dust noise.",
            },
            {
                "hop": 2,
                "role": "Mule Consolidation Node",
                "address": ADDR_HOP2_CONSOLIDATION,
                "description": "Aggregates multi-source syndicate funds (49,850 USDT).",
            },
            {
                "hop": 3,
                "role": "VASP Deposit Candidate",
                "address": ADDR_HOP3_CANDIDATE,
                "description": "Exchange deposit account candidate with 99.8% sweep behavior.",
            },
            {
                "hop": 4,
                "role": "Verified VASP Endpoint (Binance Hot Wallet 4)",
                "address": ADDR_HOP4_BINANCE_HOT,
                "description": "Consolidation omnibus hot wallet verified via public audit.",
            },
        ],
    }


@router.get("/status")
async def get_demo_status(db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    """
    Check availability of the canonical SIH demo case, its pre-computed trace,
    and return canonical scenario narrative and wallet topology specifications.
    """
    scenario = get_canonical_scenario_dict()
    case = await CaseRepository.get_by_id(db, CANONICAL_CASE_ID)
    if not case:
        # Also check by FIR
        res = await db.execute(select(Case).where(Case.fir_number == CANONICAL_FIR))
        case = res.scalars().first()

    if not case:
        return {
            "loaded": False,
            "case_id": None,
            "trace_id": None,
            "message": "Canonical demo case is not yet seeded. Call POST /api/v1/demo/seed.",
            "scenario": scenario,
        }

    traces = await TraceRepository.list_by_case_id(db, case.id)
    active_trace = traces[0] if traces else None

    return {
        "loaded": True,
        "case_id": case.id,
        "fir_number": case.fir_number,
        "suspect_wallet": case.suspect_wallet,
        "trace_id": active_trace.id if active_trace else None,
        "trace_status": active_trace.status if active_trace else None,
        "execution_mode": getattr(active_trace, "execution_mode", "DEMO") if active_trace else "DEMO",
        "scenario": scenario,
    }


@router.post("/seed", status_code=status.HTTP_201_CREATED)
async def seed_canonical_demo(
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Deterministic Demo Reset & Seed Endpoint.
    Idempotently purges previous demo runs and initializes the canonical SIH case,
    executing the 4-hop trace, attribution analysis, and evidence generation in sub-second time.
    """
    # 1. Clean up existing canonical case if present
    existing_cases = await db.execute(
        select(Case).where((Case.id == CANONICAL_CASE_ID) | (Case.fir_number == CANONICAL_FIR))
    )
    for c in existing_cases.scalars().all():
        await db.delete(c)
    await db.commit()

    # 2. Create the clean canonical Case record
    canonical_case = Case(
        id=CANONICAL_CASE_ID,
        fir_number=CANONICAL_FIR,
        victim_reference=CANONICAL_VICTIM,
        loss_amount_inr=CANONICAL_LOSS_INR,
        ack_number=CANONICAL_ACK,
        suspect_wallet=ADDR_SUSPECT_ROOT,
        chain=CANONICAL_CHAIN,
        asset=CANONICAL_ASSET,
        notes=CANONICAL_NOTES,
        status="OPEN",
        created_at=datetime.now(timezone.utc),
    )
    db.add(canonical_case)
    await db.commit()
    await db.refresh(canonical_case)

    # 3. Create the canonical Trace record
    trace_record = await TraceRepository.create(
        session=db,
        case_id=canonical_case.id,
        chain=CANONICAL_CHAIN,
        input_type="address",
        input_value=ADDR_SUSPECT_ROOT,
        asset=CANONICAL_ASSET,
        max_hops=4,
        min_relevant_usd=Decimal("1.00"),
        execution_mode="DEMO",
    )

    # 4. Execute deterministic Demo GraphEngine traversal
    demo_provider = DemoFixtureProvider()
    engine = GraphEngine(
        provider=demo_provider,
        max_hops=4,
        min_relevant_usd=Decimal("1.00"),
    )

    graph = await engine.trace(source_address=ADDR_SUSPECT_ROOT)
    graph.meta["execution_mode"] = "DEMO"
    duration_ms = max(int(graph.meta.get("duration_ms", 12)), 12)

    updated_trace = await TraceRepository.update_completed(
        session=db,
        trace_id=trace_record.id,
        graph=graph,
        duration_ms=duration_ms,
        boundary_code=graph.meta.get("boundary_reached"),
        investigator_summary=graph.meta.get("investigator_explanation"),
        status="COMPLETED",
    )

    # 5. Execute VASP Attribution Engine evaluation
    attr_engine = AttributionEngine()
    attr_report = attr_engine.evaluate_trace(trace_id=updated_trace.id, graph=graph)
    await AttributionRepository.save_report(db, attr_report)

    # 6. Generate Complete Evidence Chain (Section 63 BSA)
    evidence_items = EvidenceGenerator.generate_trace_evidence(
        case_id=canonical_case.id,
        trace_id=updated_trace.id,
        graph=graph,
        attribution_report=attr_report,
        config_snapshot={
            "max_hops": 4,
            "min_relevant_usd": "1.00",
            "execution_mode": "DEMO",
            "provider": "DemoFixtureProvider",
        },
    )
    await EvidenceRepository.save_evidence_items(db, evidence_items)

    # 7. Record Investigator Audit Event
    now_utc = datetime.now(timezone.utc)
    audit_ev = AuditEvent(
        id=str(uuid.uuid4()),
        case_id=canonical_case.id,
        trace_id=updated_trace.id,
        actor_id="investigator_demo",
        event_type=AuditEventType.TRACE_STARTED,
        action_summary="Seeded and executed canonical SIH 2026 demonstration replay trace.",
        metadata={"execution_mode": "DEMO", "hops": 4, "nodes": len(graph.nodes), "edges": len(graph.edges)},
        content_hash=compute_content_hash({"case_id": canonical_case.id, "action": "DEMO_SEEDED", "timestamp": now_utc.isoformat()}),
        created_at=now_utc,
    )
    await AuditRepository.record_event(db, audit_ev)

    best_candidate = attr_report.best_candidate
    return {
        "status": "READY",
        "message": "Canonical SIH 2026 demo case seeded and ready for judge presentation.",
        "case_id": canonical_case.id,
        "fir_number": canonical_case.fir_number,
        "trace_id": updated_trace.id,
        "suspect_wallet": canonical_case.suspect_wallet,
        "execution_mode": "DEMO",
        "attribution": {
            "attributed_vasp": best_candidate.vasp_name if best_candidate else "Unknown",
            "confidence": float(best_candidate.confidence) if best_candidate else 0.0,
            "confidence_band": best_candidate.confidence_band if best_candidate else "NONE",
            "candidate_address": best_candidate.candidate_address if best_candidate else None,
            "hypothesis_label": best_candidate.hypothesis_label if best_candidate else None,
        },
        "graph_metrics": {
            "nodes": len(graph.nodes),
            "edges": len(graph.edges),
            "pruned_transfers": len(graph.pruned_records),
            "hops": graph.meta.get("hops_reached", 4),
            "duration_ms": duration_ms,
        },
        "evidence_items_count": len(evidence_items),
    }
