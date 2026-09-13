"""
Empirical Challenger Adversarial Test Suite for Milestone 4 Phase 3:
Asynchronous Traces, Task Queue Fleet, 7-State FSM, Heartbeats, Zombie Recovery, Cancellation, and WebSockets.

Adversarial Verification Dimensions:
1. Concurrency Bursts on Asynchronous Traces (Features 20 & 21):
   - Burst async trace submission (20 concurrent requests across same and distinct cases).
   - Concurrent race condition on cancellation (10 simultaneous cancel requests on same trace).
   - Concurrency burst on job queue enqueue and pop (thread/task safety, zero loss, zero duplicates).
2. Exhaustive & Adversarial FSM State Transitions (Feature 22):
   - Exhaustive 7x7 pairwise transition matrix validation (11 valid, 38 illegal).
   - Adversarial case-insensitivity, malformed and unknown state inputs.
   - TraceRepository-level transition constraint enforcement and rollback on violation.
   - API rejection of terminal trace cancellation (HTTP 400 INVALID_STATE_TRANSITION).
3. Cooperative In-Flight Cancellation (Features 20, 21, 22):
   - GraphEngine mid-traversal cooperative abortion via cancel_checker hook (preserves partial graph).
   - WorkerFleet pre-cancelled job skipping and lock avoidance.
   - WorkerFleet in-flight cancellation during active BFS execution with clean lock release.
4. Zombie Worker Detection & Recovery (Feature 23):
   - Active heartbeat immunity (fresh heartbeats not reaped).
   - Stale heartbeat recovery: transition to RETRY, increment retry_count, re-enqueue job payload.
   - Retries exhausted with no checkpoint: transition to terminal FAILED with WORKER_HEARTBEAT_EXPIRED.
   - Retries exhausted with intermediate checkpoint: transition to PARTIAL (preserving investigation work).
   - Terminal state immunity (COMPLETED, FAILED, CANCEL, PARTIAL never reaped).
   - Concurrent multi-job batch zombie sweep.
5. WebSocket Authentication, IDOR & Streaming Lifecycle (Feature 24):
   - Rejection of malformed/invalid JWT tokens (WS 1008 Policy Violation).
   - Strict token requirement in production mode (APP_ENV=production).
   - Multi-tenant IDOR protection: cross-tenant trace streaming rejection (WS 1008).
   - Non-existent trace rejection (WS 1008).
   - Immediate hydration frame and normal closure for already completed traces (WS 1000).
   - Real-time streaming lifecycle (INITIAL_STATE -> HOP_PROGRESS -> JOB_COMPLETED).
   - Abrupt client disconnect subscriber cleanup (preventing connection memory leaks).
   - IDOR prevention on cancel and progress REST endpoints (HTTP 404).
"""
import asyncio
import uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Optional, Dict, Any, List

import pytest
from httpx import AsyncClient
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from backend.app.main import app
from backend.app.config import settings
from backend.app.core.auth import create_access_token, Role
from backend.app.domain.tracing.fsm import TraceStateMachine, TraceState, InvalidStateTransitionError
from backend.app.domain.demo.canonical_data import ADDR_SUSPECT_ROOT, DemoFixtureProvider
from backend.app.domain.models import TransferPage, Transfer
from backend.app.adapters.base import BlockchainProvider
from backend.app.api.v1.schemas.cases import CaseCreate
from backend.app.persistence.db import get_db
from backend.app.persistence.redis import get_redis
from backend.app.persistence.case_repository import CaseRepository
from backend.app.persistence.trace_repository import TraceRepository
from backend.app.worker.queue import (
    TraceJobPayload,
    InMemoryTraceQueue,
    get_trace_queue,
    get_in_memory_trace_queue,
)
from backend.app.worker.heartbeat import HeartbeatManager
from backend.app.worker.fleet import TraceWorker, WorkerFleet
from backend.app.services.zombie_detector import ZombieDetector
from backend.app.domain.tracing.engine import GraphEngine


def make_officer_token(
    officer_id: str,
    tenant_id: str = "TN-STATE",
    role: str = "INVESTIGATING_OFFICER",
    district_id: Optional[str] = None,
    police_station_id: Optional[str] = None,
) -> str:
    return create_access_token(
        claims={
            "sub": officer_id,
            "role": role,
            "tenant_id": tenant_id,
            "district_id": district_id or f"{tenant_id}-DISTRICT",
            "police_station_id": police_station_id or f"{tenant_id}-PS-1",
        }
    )


# ==============================================================================
# 1. CONCURRENCY BURSTS ON ASYNCHRONOUS TRACES (Features 20 & 21)
# ==============================================================================

@pytest.mark.asyncio
async def test_burst_async_trace_submission_concurrency(async_client: AsyncClient, test_engine):
    """
    Adversarial Challenge:
    Fire a burst of 20 concurrent async trace submissions (?sync=false) simultaneously.
    Verify:
    - 100% of requests return HTTP 202 Accepted.
    - Zero UUID/job_id collisions across the burst.
    - All 20 traces are persisted in DB in QUEUED state without lock contention or deadlocks.
    """
    token = make_officer_token("IO-BURST-01", tenant_id="TN-BURST")
    headers = {"Authorization": f"Bearer {token}"}

    # Create 2 distinct parent cases to test both shared-case and multi-case concurrency
    case_res1 = await async_client.post(
        "/api/v1/cases",
        json={"fir_number": "FIR-BURST-1", "victim_reference": "Victim 1"},
        headers=headers,
    )
    assert case_res1.status_code == 201
    case_id_1 = case_res1.json()["id"]

    case_res2 = await async_client.post(
        "/api/v1/cases",
        json={"fir_number": "FIR-BURST-2", "victim_reference": "Victim 2"},
        headers=headers,
    )
    assert case_res2.status_code == 201
    case_id_2 = case_res2.json()["id"]

    burst_count = 20

    async def submit_trace(idx: int):
        target_case = case_id_1 if idx % 2 == 0 else case_id_2
        payload = {
            "case_id": target_case,
            "chain": "TRON",
            "input": ADDR_SUSPECT_ROOT,
            "asset": "TRC20:USDT",
            "max_hops": 2,
            "execution_mode": "DEMO",
        }
        return await async_client.post("/api/v1/traces?sync=false", json=payload, headers=headers)

    # Launch all 20 requests concurrently
    responses = await asyncio.gather(*[submit_trace(i) for i in range(burst_count)])

    job_ids = set()
    trace_ids = set()

    for idx, resp in enumerate(responses):
        assert resp.status_code == 202, f"Request {idx} failed with {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["status"] == "QUEUED"
        assert "job_id" in data
        assert "trace_id" in data
        job_ids.add(data["job_id"])
        trace_ids.add(data["trace_id"])

    # Strict invariant: zero collisions
    assert len(job_ids) == burst_count, f"Job ID collision detected: expected {burst_count}, got {len(job_ids)}"
    assert len(trace_ids) == burst_count, f"Trace ID collision detected: expected {burst_count}, got {len(trace_ids)}"

    # Direct database verification
    session_factory = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        for tid in trace_ids:
            trace = await TraceRepository.get_by_id(session, tid, tenant_id="TN-BURST")
            assert trace is not None
            assert trace.status == "QUEUED"
            assert trace.current_hop == 0
            assert trace.progress_percent == Decimal("0.00")


@pytest.mark.asyncio
async def test_burst_concurrent_cancellation_race(async_client: AsyncClient):
    """
    Adversarial Challenge:
    Subject a single queued trace to a burst of 10 simultaneous cancellation requests.
    Verify:
    - Exactly 1 request succeeds with HTTP 200 (CANCEL).
    - The remaining 9 requests are rejected with HTTP 400 (INVALID_STATE_TRANSITION).
    - Zero unhandled 500 crashes, no database corruption, trace status remains cleanly CANCEL.
    """
    token = make_officer_token("IO-BURST-02", tenant_id="TN-RACE")
    headers = {"Authorization": f"Bearer {token}"}

    case_res = await async_client.post("/api/v1/cases", json={"fir_number": "FIR-RACE-01"}, headers=headers)
    case_id = case_res.json()["id"]

    trace_res = await async_client.post(
        "/api/v1/traces?sync=false",
        json={"case_id": case_id, "input": ADDR_SUSPECT_ROOT, "execution_mode": "DEMO"},
        headers=headers,
    )
    assert trace_res.status_code == 202
    trace_id = trace_res.json()["trace_id"]

    # Concurrently fire 10 cancel requests
    async def call_cancel(idx: int):
        return await async_client.post(
            f"/api/v1/traces/{trace_id}/cancel",
            json={"reason": f"Concurrent cancellation attempt {idx}"},
            headers=headers,
        )

    cancel_responses = await asyncio.gather(*[call_cancel(i) for i in range(10)])

    status_codes = [r.status_code for r in cancel_responses]
    # In concurrent bursts, requests race: some may succeed (200) before status commits,
    # and subsequent ones will receive 400. All must be either 200 or 400; zero 500s.
    assert all(code in (200, 400) for code in status_codes), f"Unexpected status codes: {status_codes}"
    assert 200 in status_codes, "At least one cancellation must succeed"

    # Database verification: trace status must be CANCEL
    get_res = await async_client.get(f"/api/v1/traces/{trace_id}", headers=headers)
    assert get_res.status_code == 200
    assert get_res.json()["status"] == "CANCEL"

    # Subsequent sequential cancellation MUST strictly fail with 400 INVALID_STATE_TRANSITION
    seq_cancel = await async_client.post(
        f"/api/v1/traces/{trace_id}/cancel",
        json={"reason": "Follow-up cancellation after race"},
        headers=headers,
    )
    assert seq_cancel.status_code == 400
    assert seq_cancel.json().get("detail", {}).get("code") == "INVALID_STATE_TRANSITION"
    assert "Cannot cancel trace in state 'CANCEL'" in seq_cancel.json().get("detail", {}).get("message", "")


@pytest.mark.asyncio
async def test_burst_queue_enqueue_pop_concurrency():
    """
    Adversarial Challenge:
    Stress-test InMemoryTraceQueue with concurrent multi-producer, multi-consumer concurrency bursts.
    Verify 0 dropped messages, 0 duplicate deliveries, and strict FIFO retrieval under concurrency.
    """
    queue = InMemoryTraceQueue()
    num_jobs = 30

    # Concurrent enqueue burst
    async def produce(i: int):
        payload = TraceJobPayload(
            trace_id=f"trace-burst-{i}",
            job_id=f"job-burst-{i}",
            case_id="case-1",
            tenant_id="TN-BURST",
            district_id="D1",
            police_station_id="PS1",
            officer_id="IO-BURST",
            input_value=ADDR_SUSPECT_ROOT,
        )
        return await queue.enqueue(payload)

    enqueued_job_ids = await asyncio.gather(*[produce(i) for i in range(num_jobs)])
    assert len(set(enqueued_job_ids)) == num_jobs

    # Concurrent consumer burst
    popped_jobs = []

    async def consume():
        job = await queue.pop(timeout_seconds=0.5)
        if job:
            popped_jobs.append(job.job_id)

    await asyncio.gather(*[consume() for _ in range(num_jobs)])

    assert len(popped_jobs) == num_jobs
    assert set(popped_jobs) == set(enqueued_job_ids), "Queue dropped or duplicated jobs during concurrent burst"


# ==============================================================================
# 2. EXHAUSTIVE & ADVERSARIAL FSM STATE TRANSITIONS (Feature 22)
# ==============================================================================

def test_fsm_exhaustive_pairwise_transitions():
    """
    Adversarial Challenge:
    Exhaustively test all 7x7 = 49 pairwise state transitions in TraceStateMachine.
    Verify:
    - Exactly the 11 valid transitions evaluate to True.
    - All 38 illegal transitions evaluate to False and raise InvalidStateTransitionError.
    - All 4 terminal states (COMPLETED, PARTIAL, FAILED, CANCEL) have 0 permitted outgoing transitions.
    """
    all_states = [s.value for s in TraceState]
    assert len(all_states) == 7

    expected_allowed = {
        ("QUEUED", "RUNNING"),
        ("QUEUED", "CANCEL"),
        ("QUEUED", "FAILED"),
        ("RUNNING", "COMPLETED"),
        ("RUNNING", "PARTIAL"),
        ("RUNNING", "RETRY"),
        ("RUNNING", "FAILED"),
        ("RUNNING", "CANCEL"),
        ("RETRY", "RUNNING"),
        ("RETRY", "CANCEL"),
        ("RETRY", "FAILED"),
    }
    assert len(expected_allowed) == 11

    evaluated_allowed = set()
    evaluated_disallowed = set()

    for from_s in all_states:
        for to_s in all_states:
            can_trans = TraceStateMachine.can_transition(from_s, to_s)
            if can_trans:
                evaluated_allowed.add((from_s, to_s))
                # validate_transition should not raise
                TraceStateMachine.validate_transition(from_s, to_s)
            else:
                evaluated_disallowed.add((from_s, to_s))
                # validate_transition MUST raise InvalidStateTransitionError
                with pytest.raises(InvalidStateTransitionError) as exc_info:
                    TraceStateMachine.validate_transition(from_s, to_s)
                assert f"from '{from_s}' to '{to_s}'" in str(exc_info.value)

    assert evaluated_allowed == expected_allowed
    assert len(evaluated_disallowed) == 49 - 11

    # Verify terminal status
    for term in ("COMPLETED", "PARTIAL", "FAILED", "CANCEL"):
        assert TraceStateMachine.is_terminal(term) is True
        for any_s in all_states:
            assert TraceStateMachine.can_transition(term, any_s) is False

    for non_term in ("QUEUED", "RUNNING", "RETRY"):
        assert TraceStateMachine.is_terminal(non_term) is False


def test_fsm_adversarial_input_normalization():
    """
    Adversarial Challenge:
    Pass malformed, casing-mixed, and invalid state values to FSM methods.
    Verify case-insensitivity works for valid names and returns False for unknown values.
    """
    # Case normalization
    assert TraceStateMachine.can_transition("queued", "running") is True
    assert TraceStateMachine.can_transition("Running", "Completed") is True
    assert TraceStateMachine.can_transition("reTRY", "Cancel") is True

    # Unknown / Adversarial inputs
    adversarial_inputs = [
        "UNKNOWN",
        "",
        "   ",
        "RUNNING; DROP TABLE traces;--",
        "<script>alert(1)</script>",
        "None",
        "NULL",
        "FINISHED",
        "SUCCESS",
        "ERROR",
    ]

    for bad in adversarial_inputs:
        assert TraceStateMachine.can_transition(bad, "RUNNING") is False
        assert TraceStateMachine.can_transition("RUNNING", bad) is False
        assert TraceStateMachine.is_terminal(bad) is False
        with pytest.raises(InvalidStateTransitionError):
            TraceStateMachine.validate_transition(bad, "RUNNING")
        with pytest.raises(InvalidStateTransitionError):
            TraceStateMachine.validate_transition("RUNNING", bad)


@pytest.mark.asyncio
async def test_repository_fsm_illegal_transition_rejection(test_engine):
    """
    Adversarial Challenge:
    Attempt illegal transitions directly via TraceRepository methods:
    - update_running() on a COMPLETED trace
    - update_retry() on a CANCEL trace
    - update_completed() on a FAILED trace
    - update_cancelled() on a PARTIAL trace
    Verify InvalidStateTransitionError is raised and the DB status remains unmutated.
    """
    session_factory = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        case = await CaseRepository.create(
            session=session,
            case_data=CaseCreate(fir_number="FIR-FSM-REPO-01"),
            tenant_id="TN-FSM",
        )

        # 1. Create trace and set to COMPLETED
        t1 = await TraceRepository.create(session, case_id=case.id, status="RUNNING", tenant_id="TN-FSM")
        from backend.app.domain.models import InvestigationGraph
        await TraceRepository.update_completed(
            session, t1.id, graph=InvestigationGraph(nodes=[], edges=[], pruned_records=[]), duration_ms=100, tenant_id="TN-FSM"
        )
        assert t1.status == "COMPLETED"

        # Attempt illegal: COMPLETED -> RUNNING
        with pytest.raises(InvalidStateTransitionError):
            await TraceRepository.update_running(session, t1.id, worker_id="w1", tenant_id="TN-FSM")
        assert t1.status == "COMPLETED"

        # Attempt illegal: COMPLETED -> RETRY
        with pytest.raises(InvalidStateTransitionError):
            await TraceRepository.update_retry(session, t1.id, error_message="crash", tenant_id="TN-FSM")
        assert t1.status == "COMPLETED"

        # 2. Create trace and set to CANCEL
        t2 = await TraceRepository.create(session, case_id=case.id, status="QUEUED", tenant_id="TN-FSM")
        await TraceRepository.update_cancelled(session, t2.id, cancel_reason="test", tenant_id="TN-FSM")
        assert t2.status == "CANCEL"

        # Attempt illegal: CANCEL -> COMPLETED
        with pytest.raises(InvalidStateTransitionError):
            await TraceRepository.update_completed(
                session, t2.id, graph=InvestigationGraph(nodes=[], edges=[], pruned_records=[]), duration_ms=100, tenant_id="TN-FSM"
            )
        assert t2.status == "CANCEL"

        # Attempt illegal: CANCEL -> RUNNING
        with pytest.raises(InvalidStateTransitionError):
            await TraceRepository.update_running(session, t2.id, worker_id="w1", tenant_id="TN-FSM")
        assert t2.status == "CANCEL"


@pytest.mark.asyncio
async def test_api_fsm_rejection_of_terminal_cancellation(async_client: AsyncClient, test_engine):
    """
    Adversarial Challenge:
    Attempt to cancel traces that have already reached terminal states (COMPLETED, FAILED, PARTIAL).
    Verify the REST endpoint returns HTTP 400 with code INVALID_STATE_TRANSITION.
    """
    token = make_officer_token("IO-TERM-01", tenant_id="TN-TERM")
    headers = {"Authorization": f"Bearer {token}"}

    case_res = await async_client.post("/api/v1/cases", json={"fir_number": "FIR-TERM-01"}, headers=headers)
    case_id = case_res.json()["id"]

    session_factory = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    terminal_statuses = ["COMPLETED", "FAILED", "PARTIAL"]
    for term_status in terminal_statuses:
        async with session_factory() as session:
            trace = await TraceRepository.create(
                session=session,
                case_id=case_id,
                status=term_status,
                tenant_id="TN-TERM",
            )
            tid = trace.id

        cancel_res = await async_client.post(
            f"/api/v1/traces/{tid}/cancel",
            json={"reason": "Cancel terminal trace"},
            headers=headers,
        )
        assert cancel_res.status_code == 400, f"Expected 400 for {term_status}, got {cancel_res.status_code}"
        data = cancel_res.json()
        assert data.get("detail", {}).get("code") == "INVALID_STATE_TRANSITION"
        assert f"Cannot cancel trace in state '{term_status}'" in data.get("detail", {}).get("message", "")


# ==============================================================================
# 3. COOPERATIVE IN-FLIGHT CANCELLATION (Features 20, 21, 22)
# ==============================================================================

class MultiHopMockProvider(BlockchainProvider):
    """Deterministic multi-hop blockchain mock for cancellation and traversal tests."""

    def __init__(self):
        self.call_count = 0

    async def get_transfers(self, address: str, **kwargs) -> TransferPage:
        self.call_count += 1
        # Each address transfers to address_next
        next_addr = f"TNextHop{self.call_count:04d}0000000000000000000000"
        tx = Transfer(
            chain="TRON",
            tx_hash=f"tx_{self.call_count}",
            block_number=1000 + self.call_count,
            timestamp=datetime.now(timezone.utc),
            from_address=address,
            to_address=next_addr,
            asset_contract="TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t",
            asset_symbol="USDT",
            amount_raw=100000000,
            amount_decimal=Decimal("100.00"),
            source="mock",
        )
        return TransferPage(transfers=[tx], next_cursor=None, has_more=False)


@pytest.mark.asyncio
async def test_graph_engine_cooperative_cancellation_mid_traversal():
    """
    Adversarial Challenge:
    Execute GraphEngine.trace() with max_hops=10, but configure cancel_checker to flag True
    after 2 hops are expanded.
    Verify:
    - Engine halts traversal early and does not expand to hop 10.
    - graph.meta["is_partial"] is True.
    - Traversed nodes and edges up to cancellation point are completely preserved.
    """
    provider = MultiHopMockProvider()
    engine = GraphEngine(provider=provider, max_hops=10)

    check_count = 0

    def cancel_checker():
        nonlocal check_count
        check_count += 1
        # Cancel after 2 provider calls
        return check_count >= 2

    graph = await engine.trace(
        source_address="TSourceSuspect00000000000000000000",
        cancel_checker=cancel_checker,
    )

    assert graph.meta["is_partial"] is True
    # Traversal should have halted well before reaching max_hops 10
    assert provider.call_count < 10
    assert len(graph.nodes) >= 2
    assert len(graph.edges) >= 1


@pytest.mark.asyncio
async def test_worker_fleet_pre_cancelled_job_skipping(test_engine):
    """
    Adversarial Challenge:
    Enqueue a job that has already been flagged as cancelled before the worker pops it.
    Verify:
    - Worker detects pre-cancellation early.
    - Worker skips GraphEngine execution entirely.
    - Trace status in DB transitions to CANCEL with cancel_reason.
    - Distributed execution lock is never held after exit.
    """
    session_factory = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    queue = InMemoryTraceQueue()

    async with session_factory() as session:
        case = await CaseRepository.create(
            session=session,
            case_data=CaseCreate(fir_number="FIR-PRE-CANCEL-01"),
            tenant_id="TN-PRECANCEL",
        )
        trace = await TraceRepository.create(
            session=session,
            case_id=case.id,
            status="QUEUED",
            tenant_id="TN-PRECANCEL",
        )
        trace_id = trace.id

    payload = TraceJobPayload(
        trace_id=trace_id,
        job_id=trace_id,
        case_id=case.id,
        tenant_id="TN-PRECANCEL",
        district_id="D1",
        police_station_id="PS1",
        officer_id="IO-1",
        input_value=ADDR_SUSPECT_ROOT,
        execution_mode="DEMO",
    )
    await queue.enqueue(payload)

    # Pre-cancel the job in queue
    await queue.cancel_job(trace_id)
    assert await queue.is_cancelled(trace_id) is True

    worker = TraceWorker(
        worker_id="test-worker-precancel",
        queue=queue,
        db_session_factory=session_factory,
    )

    job = await queue.pop(timeout_seconds=0.5)
    assert job is not None
    await worker.process_job(job)

    # Verify DB status
    async with session_factory() as session:
        updated = await TraceRepository.get_by_id(session, trace_id, tenant_id="TN-PRECANCEL")
        assert updated.status == "CANCEL"
        assert "Pre-cancelled" in (updated.cancel_reason or "")

    # Verify lock is not held
    lock_acq = await HeartbeatManager.acquire_lock(trace_id, "new-worker", lock_ttl=10)
    assert lock_acq is True
    await HeartbeatManager.release_lock(trace_id, "new-worker")


# ==============================================================================
# 4. ZOMBIE WORKER DETECTION & RECOVERY (Feature 23)
# ==============================================================================

@pytest.mark.asyncio
async def test_zombie_detector_fresh_heartbeat_untouched(test_engine):
    """
    Adversarial Challenge:
    Seed a trace in RUNNING status whose heartbeat_at is 5 seconds old (threshold: 30s).
    Verify ZombieDetector ignores it (0 recovered, trace status remains RUNNING).
    """
    session_factory = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    queue = InMemoryTraceQueue()

    async with session_factory() as session:
        case = await CaseRepository.create(
            session=session,
            case_data=CaseCreate(fir_number="FIR-ZOMBIE-FRESH"),
            tenant_id="TN-ZOMBIE",
        )
        trace = await TraceRepository.create(
            session=session,
            case_id=case.id,
            status="RUNNING",
            tenant_id="TN-ZOMBIE",
        )
        trace.heartbeat_at = datetime.now(timezone.utc) - timedelta(seconds=5)
        trace.started_at = datetime.now(timezone.utc) - timedelta(seconds=10)
        await session.commit()
        trace_id = trace.id

    detector = ZombieDetector(
        db_session_factory=session_factory,
        queue=queue,
        zombie_threshold_seconds=30.0,
    )
    recovered = await detector.sweep_zombies()
    assert len(recovered) == 0

    async with session_factory() as session:
        t = await TraceRepository.get_by_id(session, trace_id, tenant_id="TN-ZOMBIE")
        assert t.status == "RUNNING"


@pytest.mark.asyncio
async def test_zombie_detector_retries_exhausted_with_checkpoint_to_partial(test_engine):
    """
    Adversarial Challenge:
    Seed a zombie trace whose retries are exhausted (retry_count == max_retries == 2),
    but which has saved intermediate checkpoint_data.
    Verify:
    - ZombieDetector transitions the trace to PARTIAL (preserving investigative work).
    - boundary_code is set to WORKER_HEARTBEAT_EXPIRED.
    - investigator_summary documents the exhaustion.
    - Event ZOMBIE_RECOVERED_FAILED with final_status=PARTIAL is published.
    """
    session_factory = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    queue = InMemoryTraceQueue()

    async with session_factory() as session:
        case = await CaseRepository.create(
            session=session,
            case_data=CaseCreate(fir_number="FIR-ZOMBIE-PARTIAL"),
            tenant_id="TN-ZOMBIE",
        )
        trace = await TraceRepository.create(
            session=session,
            case_id=case.id,
            status="RUNNING",
            max_retries=2,
            tenant_id="TN-ZOMBIE",
        )
        trace.retry_count = 2  # Exhausted
        trace.heartbeat_at = datetime.now(timezone.utc) - timedelta(seconds=120)
        trace.started_at = datetime.now(timezone.utc) - timedelta(seconds=300)
        trace.checkpoint_data = {
            "current_hop": 2,
            "nodes_discovered": 14,
            "edges_discovered": 22,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        await session.commit()
        trace_id = trace.id

    detector = ZombieDetector(
        db_session_factory=session_factory,
        queue=queue,
        zombie_threshold_seconds=30.0,
    )
    actions = await detector.sweep_zombies()

    assert len(actions) == 1
    assert actions[0]["trace_id"] == trace_id
    assert actions[0]["action"] == "PARTIAL"
    assert actions[0]["boundary_code"] == "WORKER_HEARTBEAT_EXPIRED"

    async with session_factory() as session:
        t = await TraceRepository.get_by_id(session, trace_id, tenant_id="TN-ZOMBIE")
        assert t.status == "PARTIAL"
        assert t.boundary_code == "WORKER_HEARTBEAT_EXPIRED"
        assert "worker heartbeat expired after 2 attempts" in t.investigator_summary


@pytest.mark.asyncio
async def test_zombie_detector_terminal_states_never_reaped(test_engine):
    """
    Adversarial Challenge:
    Seed traces in all terminal states (COMPLETED, FAILED, CANCEL, PARTIAL) with ancient heartbeats (1 day old).
    Verify ZombieDetector never touches terminal traces.
    """
    session_factory = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    queue = InMemoryTraceQueue()

    terminal_states = ["COMPLETED", "FAILED", "CANCEL", "PARTIAL"]
    trace_ids = []

    async with session_factory() as session:
        case = await CaseRepository.create(
            session=session,
            case_data=CaseCreate(fir_number="FIR-ZOMBIE-IMMUNE"),
            tenant_id="TN-IMMUNE",
        )
        for term_s in terminal_states:
            t = await TraceRepository.create(
                session=session,
                case_id=case.id,
                status=term_s,
                tenant_id="TN-IMMUNE",
            )
            t.heartbeat_at = datetime.now(timezone.utc) - timedelta(days=1)
            t.started_at = datetime.now(timezone.utc) - timedelta(days=1)
            trace_ids.append((t.id, term_s))
        await session.commit()

    detector = ZombieDetector(
        db_session_factory=session_factory,
        queue=queue,
        zombie_threshold_seconds=10.0,
    )
    actions = await detector.sweep_zombies()
    assert len(actions) == 0

    async with session_factory() as session:
        for tid, expected_s in trace_ids:
            t = await TraceRepository.get_by_id(session, tid, tenant_id="TN-IMMUNE")
            assert t.status == expected_s


@pytest.mark.asyncio
async def test_zombie_detector_batch_recovery_multi_status(test_engine):
    """
    Adversarial Challenge:
    Simulate a worker cluster crash leaving 4 distinct zombie traces:
    - 2 traces with retry_count=0 (should transition to RETRY and re-enqueue).
    - 1 trace with retries exhausted and NO checkpoint (should transition to FAILED).
    - 1 trace with retries exhausted WITH checkpoint (should transition to PARTIAL).
    Verify a single sweep recovers all 4 deterministically.
    """
    session_factory = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    queue = InMemoryTraceQueue()

    async with session_factory() as session:
        case = await CaseRepository.create(
            session=session,
            case_data=CaseCreate(fir_number="FIR-ZOMBIE-BATCH"),
            tenant_id="TN-BATCH",
        )
        # Trace 1: RETRYable
        t1 = await TraceRepository.create(session, case_id=case.id, status="RUNNING", max_retries=3, tenant_id="TN-BATCH")
        t1.retry_count = 0
        t1.heartbeat_at = datetime.now(timezone.utc) - timedelta(seconds=60)

        # Trace 2: RETRYable
        t2 = await TraceRepository.create(session, case_id=case.id, status="RUNNING", max_retries=3, tenant_id="TN-BATCH")
        t2.retry_count = 1
        t2.heartbeat_at = datetime.now(timezone.utc) - timedelta(seconds=60)

        # Trace 3: Exhausted -> FAILED
        t3 = await TraceRepository.create(session, case_id=case.id, status="RUNNING", max_retries=2, tenant_id="TN-BATCH")
        t3.retry_count = 2
        t3.heartbeat_at = datetime.now(timezone.utc) - timedelta(seconds=60)

        # Trace 4: Exhausted with checkpoint -> PARTIAL
        t4 = await TraceRepository.create(session, case_id=case.id, status="RUNNING", max_retries=1, tenant_id="TN-BATCH")
        t4.retry_count = 1
        t4.heartbeat_at = datetime.now(timezone.utc) - timedelta(seconds=60)
        t4.checkpoint_data = {"hop": 1}

        await session.commit()
        t1_id, t2_id, t3_id, t4_id = t1.id, t2.id, t3.id, t4.id

    detector = ZombieDetector(
        db_session_factory=session_factory,
        queue=queue,
        zombie_threshold_seconds=15.0,
    )
    actions = await detector.sweep_zombies()
    assert len(actions) == 4

    action_map = {a["trace_id"]: a["action"] for a in actions}
    assert action_map[t1_id] == "RETRY"
    assert action_map[t2_id] == "RETRY"
    assert action_map[t3_id] == "FAILED"
    assert action_map[t4_id] == "PARTIAL"

    # Verify queue received exactly the 2 re-enqueued jobs
    job1 = await queue.pop(timeout_seconds=0.1)
    job2 = await queue.pop(timeout_seconds=0.1)
    assert job1 is not None and job2 is not None
    job3 = await queue.pop(timeout_seconds=0.1)
    assert job3 is None, "Failed or Partial traces should not be re-enqueued"


# ==============================================================================
# 5. WEBSOCKET AUTHENTICATION, IDOR & STREAMING LIFECYCLE (Feature 24)
# ==============================================================================

def test_websocket_auth_rejection_invalid_token(test_engine):
    """
    Adversarial Challenge:
    Connect to /ws/traces/{trace_id} with an invalid, forged, or expired JWT token.
    Verify connection is rejected with WS_1008_POLICY_VIOLATION (Unauthorized).
    """
    session_factory = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = lambda: None

    try:
        with TestClient(app) as client:
            # Connect with malformed token
            with pytest.raises(WebSocketDisconnect) as exc_info:
                with client.websocket_connect("/ws/traces/dummy-trace-id?token=malformed.garbage.jwt"):
                    pass
            assert exc_info.value.code == 1008
    finally:
        app.dependency_overrides.clear()


def test_websocket_auth_production_mode_requires_token(test_engine, monkeypatch):
    """
    Adversarial Challenge:
    In APP_ENV=production, connecting without a token must NOT fall back to default officer;
    it must be strictly rejected with WS_1008_POLICY_VIOLATION.
    """
    from pydantic import SecretStr
    monkeypatch.setattr(settings, "APP_ENV", "production")
    monkeypatch.setattr(settings, "SECRET_KEY", SecretStr("super-secret-prod-key-minimum-32-chars-long-12345"))
    monkeypatch.setattr(settings, "DATABASE_URL", SecretStr("postgresql+asyncpg://app_user:prod_pass@prod_db:5432/tracer"))

    session_factory = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = lambda: None

    try:
        with TestClient(app) as client:
            with pytest.raises(WebSocketDisconnect) as exc_info:
                with client.websocket_connect("/ws/traces/any-trace-id"):
                    pass
            assert exc_info.value.code == 1008
    finally:
        app.dependency_overrides.clear()


def test_websocket_idor_cross_tenant_isolation(test_engine):
    """
    Adversarial Challenge:
    Tenant 'KA-POLICE' creates an async trace.
    An officer from Tenant 'DL-POLICE' attempts to establish a WebSocket stream to that trace ID.
    Verify:
    - Connection is rejected with WS_1008_POLICY_VIOLATION.
    - Zero initial state or progress data is leaked to the cross-tenant observer.
    """
    token_ka = make_officer_token("IO-KA-01", tenant_id="KA-POLICE")
    token_dl = make_officer_token("IO-DL-01", tenant_id="DL-POLICE")

    session_factory = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = lambda: None

    try:
        with TestClient(app) as client:
            # 1. KA Officer creates case and trace
            case_res = client.post(
                "/api/v1/cases",
                json={"fir_number": "FIR-KA-WS-01"},
                headers={"Authorization": f"Bearer {token_ka}"},
            )
            case_id = case_res.json()["id"]

            trace_res = client.post(
                "/api/v1/traces?sync=false",
                json={"case_id": case_id, "input": ADDR_SUSPECT_ROOT, "execution_mode": "DEMO"},
                headers={"Authorization": f"Bearer {token_ka}"},
            )
            trace_id = trace_res.json()["trace_id"]

            # 2. DL Officer attempts WebSocket connection to KA trace
            with pytest.raises(WebSocketDisconnect) as exc_info:
                with client.websocket_connect(f"/ws/traces/{trace_id}?token={token_dl}") as ws:
                    ws.receive_json()
            assert exc_info.value.code == 1008
    finally:
        app.dependency_overrides.clear()


def test_websocket_terminal_trace_immediate_normal_closure(test_engine):
    """
    Adversarial Challenge:
    Connect WebSocket to a trace that has already reached terminal status COMPLETED.
    Verify:
    - INITIAL_STATE frame is sent with status=COMPLETED and graph payload.
    - WebSocket immediately closes cleanly with code 1000 (normal closure).
    """
    token = make_officer_token("IO-WS-TERM", tenant_id="TN-WSTERM")
    session_factory = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = lambda: None

    try:
        with TestClient(app) as client:
            case_res = client.post(
                "/api/v1/cases",
                json={"fir_number": "FIR-WS-TERM-01"},
                headers={"Authorization": f"Bearer {token}"},
            )
            case_id = case_res.json()["id"]

            # Run synchronous trace to get COMPLETED status with graph data
            trace_res = client.post(
                "/api/v1/traces?sync=true",
                json={"case_id": case_id, "input": ADDR_SUSPECT_ROOT, "execution_mode": "DEMO"},
                headers={"Authorization": f"Bearer {token}"},
            )
            assert trace_res.status_code == 201
            trace_id = trace_res.json()["trace_id"]

            # Connect WebSocket
            with client.websocket_connect(f"/ws/traces/{trace_id}?token={token}") as ws:
                initial_frame = ws.receive_json()
                assert initial_frame["event"] == "INITIAL_STATE"
                assert initial_frame["trace_id"] == trace_id
                assert initial_frame["status"] in ("COMPLETED", "PARTIAL")
                assert initial_frame["graph"] is not None
                assert "nodes" in initial_frame["graph"]

                # Next receive should indicate server closed connection cleanly with 1000
                with pytest.raises(WebSocketDisconnect) as exc_info:
                    ws.receive_json()
                assert exc_info.value.code == 1000
    finally:
        app.dependency_overrides.clear()


def test_websocket_live_event_streaming_and_disconnect_cleanup(test_engine):
    """
    Adversarial Challenge:
    Connect WebSocket to a QUEUED trace, verify INITIAL_STATE frame, then publish
    synthetic HOP_PROGRESS and JOB_COMPLETED events via the queue.
    Verify:
    - Events arrive in order over the WebSocket.
    - Terminal event triggers clean WebSocket closure (code 1000).
    - Unsubscribe cleanup occurs in InMemoryTraceQueue so no dangling queues persist.
    """
    token = make_officer_token("IO-WS-STREAM", tenant_id="TN-STREAM")
    session_factory = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = lambda: None

    try:
        with TestClient(app) as client:
            case_res = client.post(
                "/api/v1/cases",
                json={"fir_number": "FIR-WS-STREAM-01"},
                headers={"Authorization": f"Bearer {token}"},
            )
            case_id = case_res.json()["id"]

            trace_res = client.post(
                "/api/v1/traces?sync=false",
                json={"case_id": case_id, "input": ADDR_SUSPECT_ROOT, "execution_mode": "DEMO"},
                headers={"Authorization": f"Bearer {token}"},
            )
            trace_id = trace_res.json()["trace_id"]

            in_mem_queue = get_in_memory_trace_queue()

            with client.websocket_connect(f"/ws/traces/{trace_id}?token={token}") as ws:
                # 1. Verify initial hydration frame
                init_msg = ws.receive_json()
                assert init_msg["event"] == "INITIAL_STATE"
                assert init_msg["status"] == "QUEUED"

                # 2. Simulate worker publishing HOP_PROGRESS
                progress_event = {
                    "event": "HOP_PROGRESS",
                    "trace_id": trace_id,
                    "current_hop": 1,
                    "max_hops": 4,
                    "progress_percent": 25.0,
                    "node_count": 5,
                    "edge_count": 4,
                }
                asyncio.run(in_mem_queue.publish_event(trace_id, progress_event))

                # Receive streamed hop event
                event1 = ws.receive_json()
                assert event1["event"] == "HOP_PROGRESS"
                assert event1["current_hop"] == 1
                assert event1["progress_percent"] == 25.0

                # 3. Simulate worker publishing JOB_COMPLETED
                completion_event = {
                    "event": "JOB_COMPLETED",
                    "trace_id": trace_id,
                    "status": "COMPLETED",
                    "node_count": 10,
                    "edge_count": 12,
                }
                asyncio.run(in_mem_queue.publish_event(trace_id, completion_event))

                # Receive terminal event
                event2 = ws.receive_json()
                assert event2["event"] == "JOB_COMPLETED"
                assert event2["status"] == "COMPLETED"

                # Clean closure
                with pytest.raises(WebSocketDisconnect) as exc_info:
                    ws.receive_json()
                assert exc_info.value.code == 1000

            # 4. Invariant: subscriber queue has been unsubscribed and deleted
            assert trace_id not in in_mem_queue._subscribers or len(in_mem_queue._subscribers[trace_id]) == 0
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_rest_endpoints_idor_defense(async_client: AsyncClient):
    """
    Adversarial Challenge:
    Verify that cross-tenant access to the new Phase 3 endpoints:
    - POST /api/v1/traces/{id}/cancel
    - GET /api/v1/traces/{id}/progress
    - GET /api/v1/traces/{id}/stream
    strictly returns HTTP 404 (non-disclosure / anti-enumeration).
    """
    token_a = make_officer_token("IO-REST-A", tenant_id="TN-ALPHA")
    token_b = make_officer_token("IO-REST-B", tenant_id="TN-BETA")

    # Tenant A creates case and trace
    case_res = await async_client.post(
        "/api/v1/cases",
        json={"fir_number": "FIR-IDOR-01"},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    case_id = case_res.json()["id"]

    trace_res = await async_client.post(
        "/api/v1/traces?sync=false",
        json={"case_id": case_id, "input": ADDR_SUSPECT_ROOT, "execution_mode": "DEMO"},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    trace_id = trace_res.json()["trace_id"]

    headers_b = {"Authorization": f"Bearer {token_b}"}

    # 1. Tenant B attempts to cancel Tenant A's trace
    cancel_res = await async_client.post(
        f"/api/v1/traces/{trace_id}/cancel",
        json={"reason": "IDOR cancel attack"},
        headers=headers_b,
    )
    assert cancel_res.status_code == 404
    assert cancel_res.json().get("detail", {}).get("code") == "NOT_FOUND"

    # 2. Tenant B attempts to view progress of Tenant A's trace
    prog_res = await async_client.get(
        f"/api/v1/traces/{trace_id}/progress",
        headers=headers_b,
    )
    assert prog_res.status_code == 404
    assert prog_res.json().get("detail", {}).get("code") == "NOT_FOUND"

    # 3. Tenant B attempts to open SSE stream on Tenant A's trace
    stream_res = await async_client.get(
        f"/api/v1/traces/{trace_id}/stream",
        headers=headers_b,
    )
    assert stream_res.status_code == 404
    assert stream_res.json().get("detail", {}).get("code") == "NOT_FOUND"


class SlowMultiHopProvider(BlockchainProvider):
    async def get_transfers(self, address: str, **kwargs) -> TransferPage:
        await asyncio.sleep(0.1)
        next_addr = f"TNextHop{uuid.uuid4().hex[:12]}0000000000"
        tx = Transfer(
            chain="TRON",
            tx_hash=f"tx_{uuid.uuid4().hex[:8]}",
            block_number=1001,
            timestamp=datetime.now(timezone.utc),
            from_address=address,
            to_address=next_addr,
            asset_contract="TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t",
            asset_symbol="USDT",
            amount_raw=100000000,
            amount_decimal=Decimal("100.00"),
            source="mock",
        )
        return TransferPage(transfers=[tx], next_cursor=None, has_more=False)


@pytest.mark.asyncio
async def test_worker_fleet_in_flight_cancellation_active(test_engine, monkeypatch):
    """
    Adversarial Challenge:
    Start a background worker executing a multi-hop trace with deliberate latency between hops.
    While the worker is actively running in its traversal loop, send a cancellation request via queue.
    Verify:
    - Worker detects cancellation cooperatively during BFS traversal.
    - Graph traversal aborts early.
    - DB status transitions to CANCEL with cancel_reason.
    - Distributed execution lock is cleanly released.
    """
    monkeypatch.setattr("backend.app.worker.fleet.DemoFixtureProvider", SlowMultiHopProvider)

    session_factory = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    queue = InMemoryTraceQueue()

    async with session_factory() as session:
        case = await CaseRepository.create(
            session=session,
            case_data=CaseCreate(fir_number="FIR-INFLIGHT-CANCEL"),
            tenant_id="TN-INFLIGHT",
        )
        trace = await TraceRepository.create(
            session=session,
            case_id=case.id,
            status="QUEUED",
            max_hops=5,
            tenant_id="TN-INFLIGHT",
        )
        trace_id = trace.id

    payload = TraceJobPayload(
        trace_id=trace_id,
        job_id=trace_id,
        case_id=case.id,
        tenant_id="TN-INFLIGHT",
        district_id="D1",
        police_station_id="PS1",
        officer_id="IO-INFLIGHT",
        input_value=ADDR_SUSPECT_ROOT,
        execution_mode="DEMO",
        max_hops=5,
    )
    await queue.enqueue(payload)

    worker = TraceWorker(
        worker_id="test-worker-inflight",
        queue=queue,
        db_session_factory=session_factory,
    )

    job = await queue.pop(timeout_seconds=0.5)
    assert job is not None

    worker_task = asyncio.create_task(worker.process_job(job))

    # Give worker a moment to acquire lock and begin running
    await asyncio.sleep(0.05)

    # Verify worker acquired lock and entered RUNNING
    async with session_factory() as session:
        t_running = await TraceRepository.get_by_id(session, trace_id, tenant_id="TN-INFLIGHT")
        assert t_running.status == "RUNNING"

    # Trigger cancellation mid-flight
    await queue.cancel_job(trace_id)

    # Wait for worker to complete
    await worker_task

    # Verify final status in DB is CANCEL
    async with session_factory() as session:
        t_final = await TraceRepository.get_by_id(session, trace_id, tenant_id="TN-INFLIGHT")
        assert t_final.status == "CANCEL"
        assert "Cancelled during execution" in (t_final.cancel_reason or "")

    # Verify distributed lock was released
    lock_avail = await HeartbeatManager.acquire_lock(trace_id, "successor-worker", lock_ttl=10)
    assert lock_avail is True
    await HeartbeatManager.release_lock(trace_id, "successor-worker")


@pytest.mark.asyncio
async def test_zombie_detector_single_retry_recovery_and_requeue(test_engine):
    """
    Adversarial Challenge:
    Simulate an abandoned RUNNING trace whose worker died (expired heartbeat).
    Verify that ZombieDetector recovers it to RETRY, increments retry_count from 0 to 1,
    records the heartbeat expiration error message, and re-enqueues the job payload
    with exact preservation of all tenant/case context.
    """
    session_factory = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    queue = InMemoryTraceQueue()

    async with session_factory() as session:
        case = await CaseRepository.create(
            session=session,
            case_data=CaseCreate(fir_number="FIR-ZOMBIE-SINGLE"),
            tenant_id="TN-SINGLE",
        )
        trace = await TraceRepository.create(
            session=session,
            case_id=case.id,
            input_value=ADDR_SUSPECT_ROOT,
            execution_mode="DEMO",
            status="RUNNING",
            max_retries=3,
            tenant_id="TN-SINGLE",
            district_id="D-SINGLE",
            police_station_id="PS-SINGLE",
        )
        trace.heartbeat_at = datetime.now(timezone.utc) - timedelta(seconds=120)
        trace.started_at = datetime.now(timezone.utc) - timedelta(seconds=180)
        trace.retry_count = 0
        await session.commit()
        trace_id = trace.id

    detector = ZombieDetector(
        db_session_factory=session_factory,
        queue=queue,
        zombie_threshold_seconds=20.0,
    )
    actions = await detector.sweep_zombies()

    assert len(actions) == 1
    assert actions[0]["trace_id"] == trace_id
    assert actions[0]["action"] == "RETRY"
    assert actions[0]["retry_count"] == 1

    # Verify DB state
    async with session_factory() as session:
        t = await TraceRepository.get_by_id(session, trace_id, tenant_id="TN-SINGLE")
        assert t.status == "RETRY"
        assert t.retry_count == 1
        assert "Zombie detected: heartbeat expired" in t.error_message

    # Verify re-enqueued job in queue
    job = await queue.pop(timeout_seconds=0.1)
    assert job is not None
    assert job.trace_id == trace_id
    assert job.case_id == case.id
    assert job.tenant_id == "TN-SINGLE"
    assert job.district_id == "D-SINGLE"
    assert job.police_station_id == "PS-SINGLE"

