"""
Milestone 4 Phase 3 Test Suite: Asynchronous Tracing & Task Queues (Features 20–24).
Tests:
- Feature 20: HTTP 202 Accepted Async Trace Submission & Cancellation
- Feature 21: Background Worker Fleet & In-Memory Queue Execution
- Feature 22: 7-State FSM Transitions & Validation
- Feature 23: Worker Heartbeats, Progress Snapshots & Zombie Job Recovery
- Feature 24: WebSocket Real-Time Streaming & SSE
"""
import asyncio
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import pytest
from httpx import AsyncClient
from starlette.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from backend.app.main import app
from backend.app.config import settings
from backend.app.core.auth import create_access_token, Role
from backend.app.domain.tracing.fsm import TraceStateMachine, TraceState, InvalidStateTransitionError
from backend.app.domain.demo.canonical_data import ADDR_SUSPECT_ROOT
from backend.app.api.v1.schemas.cases import CaseCreate
from backend.app.persistence.db import get_db
from backend.app.persistence.redis import get_redis
from backend.app.persistence.trace_repository import TraceRepository
from backend.app.worker.queue import (
    TraceJobPayload,
    InMemoryTraceQueue,
    get_trace_queue,
)
from backend.app.worker.heartbeat import HeartbeatManager
from backend.app.worker.fleet import TraceWorker, WorkerFleet
from backend.app.services.zombie_detector import ZombieDetector


def make_officer_token(officer_id: str, tenant_id: str = "TN-STATE", role: str = "INVESTIGATING_OFFICER") -> str:
    return create_access_token(
        claims={
            "sub": officer_id,
            "role": role,
            "tenant_id": tenant_id,
            "district_id": f"{tenant_id}-DISTRICT",
            "police_station_id": f"{tenant_id}-PS-1",
        }
    )


# ============================================================================
# 1. Feature 22: 7-State FSM Tests
# ============================================================================

def test_trace_fsm_valid_transitions():
    """Verify all permitted FSM transitions defined in specification."""
    # From QUEUED
    assert TraceStateMachine.can_transition("QUEUED", "RUNNING") is True
    assert TraceStateMachine.can_transition("QUEUED", "CANCEL") is True
    assert TraceStateMachine.can_transition("QUEUED", "FAILED") is True
    assert TraceStateMachine.can_transition("QUEUED", "COMPLETED") is False

    # From RUNNING
    assert TraceStateMachine.can_transition("RUNNING", "COMPLETED") is True
    assert TraceStateMachine.can_transition("RUNNING", "PARTIAL") is True
    assert TraceStateMachine.can_transition("RUNNING", "RETRY") is True
    assert TraceStateMachine.can_transition("RUNNING", "FAILED") is True
    assert TraceStateMachine.can_transition("RUNNING", "CANCEL") is True
    assert TraceStateMachine.can_transition("RUNNING", "QUEUED") is False

    # From RETRY
    assert TraceStateMachine.can_transition("RETRY", "RUNNING") is True
    assert TraceStateMachine.can_transition("RETRY", "CANCEL") is True
    assert TraceStateMachine.can_transition("RETRY", "FAILED") is True
    assert TraceStateMachine.can_transition("RETRY", "COMPLETED") is False

    # Terminal states have 0 transitions
    for term in ("COMPLETED", "PARTIAL", "FAILED", "CANCEL"):
        assert TraceStateMachine.is_terminal(term) is True
        for next_s in ("QUEUED", "RUNNING", "COMPLETED", "PARTIAL", "FAILED", "RETRY", "CANCEL"):
            assert TraceStateMachine.can_transition(term, next_s) is False


def test_trace_fsm_invalid_transition_raises_error():
    """Verify illegal transitions raise InvalidStateTransitionError."""
    with pytest.raises(InvalidStateTransitionError) as exc_info:
        TraceStateMachine.validate_transition("COMPLETED", "RUNNING")
    assert "Invalid trace state transition from 'COMPLETED' to 'RUNNING'" in str(exc_info.value)


# ============================================================================
# 2. Feature 20: HTTP 202 Async Submission & Dual-Mode Contract Tests
# ============================================================================

@pytest.mark.asyncio
async def test_async_trace_submission_202(async_client: AsyncClient):
    """POST /api/v1/traces?sync=false returns 202 Accepted with JobStatusResponse."""
    token = make_officer_token("IO-M4-01")
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Create parent case
    case_res = await async_client.post(
        "/api/v1/cases",
        json={"fir_number": "FIR-ASYNC-202", "victim_reference": "Victim 202"},
        headers=headers,
    )
    assert case_res.status_code == 201
    case_id = case_res.json()["id"]

    # 2. Submit async trace request
    res = await async_client.post(
        "/api/v1/traces?sync=false",
        json={
            "case_id": case_id,
            "chain": "TRON",
            "input": ADDR_SUSPECT_ROOT,
            "asset": "TRC20:USDT",
            "max_hops": 2,
            "execution_mode": "DEMO",
        },
        headers=headers,
    )
    assert res.status_code == 202
    data = res.json()
    assert data["status"] == "QUEUED"
    assert "job_id" in data
    assert "trace_id" in data
    assert data["case_id"] == case_id
    assert f"/api/v1/traces/{data['trace_id']}" in data["poll_url"]
    assert f"/ws/traces/{data['trace_id']}" in data["ws_url"]

    # 3. Verify status can be polled
    poll_res = await async_client.get(data["poll_url"], headers=headers)
    assert poll_res.status_code == 200
    assert poll_res.json()["status"] == "QUEUED"


@pytest.mark.asyncio
async def test_sync_trace_submission_201_default(async_client: AsyncClient):
    """POST /api/v1/traces without sync flag in dev/test environment executes synchronously (201 Created)."""
    token = make_officer_token("IO-M4-02")
    headers = {"Authorization": f"Bearer {token}"}

    case_res = await async_client.post(
        "/api/v1/cases",
        json={"fir_number": "FIR-SYNC-201", "victim_reference": "Victim 201"},
        headers=headers,
    )
    assert case_res.status_code == 201
    case_id = case_res.json()["id"]

    res = await async_client.post(
        "/api/v1/traces",
        json={
            "case_id": case_id,
            "chain": "TRON",
            "input": ADDR_SUSPECT_ROOT,
            "asset": "TRC20:USDT",
            "max_hops": 2,
            "execution_mode": "DEMO",
        },
        headers=headers,
    )
    assert res.status_code == 201
    data = res.json()
    assert data["status"] in ("COMPLETED", "PARTIAL")
    assert data["execution_mode"] == "DEMO"
    assert data["node_count"] > 0


@pytest.mark.asyncio
async def test_body_sync_false_overrides_to_202(async_client: AsyncClient):
    """Passing sync: false in JSON payload returns 202 Accepted."""
    token = make_officer_token("IO-M4-03")
    headers = {"Authorization": f"Bearer {token}"}

    case_res = await async_client.post(
        "/api/v1/cases",
        json={"fir_number": "FIR-BODY-SYNC", "victim_reference": "Victim Body"},
        headers=headers,
    )
    assert case_res.status_code == 201
    case_id = case_res.json()["id"]

    res = await async_client.post(
        "/api/v1/traces",
        json={
            "case_id": case_id,
            "chain": "TRON",
            "input": ADDR_SUSPECT_ROOT,
            "asset": "TRC20:USDT",
            "max_hops": 2,
            "execution_mode": "DEMO",
            "sync": False,
        },
        headers=headers,
    )
    assert res.status_code == 202
    assert res.json()["status"] == "QUEUED"


@pytest.mark.asyncio
async def test_trace_cancellation_endpoint(async_client: AsyncClient):
    """POST /api/v1/traces/{id}/cancel cancels an active or queued job."""
    token = make_officer_token("IO-M4-04")
    headers = {"Authorization": f"Bearer {token}"}

    case_res = await async_client.post(
        "/api/v1/cases",
        json={"fir_number": "FIR-CANCEL-01"},
        headers=headers,
    )
    case_id = case_res.json()["id"]

    # Submit async trace
    trace_res = await async_client.post(
        "/api/v1/traces?sync=false",
        json={
            "case_id": case_id,
            "chain": "TRON",
            "input": ADDR_SUSPECT_ROOT,
            "execution_mode": "DEMO",
        },
        headers=headers,
    )
    trace_id = trace_res.json()["trace_id"]

    # Cancel trace
    cancel_res = await async_client.post(
        f"/api/v1/traces/{trace_id}/cancel",
        json={"reason": "Investigator halted trace manually"},
        headers=headers,
    )
    assert cancel_res.status_code == 200
    data = cancel_res.json()
    assert data["status"] == "CANCEL"
    assert "Investigator halted" in data["message"]

    # Cancelling again from terminal state should fail with 400
    re_cancel = await async_client.post(
        f"/api/v1/traces/{trace_id}/cancel",
        json={"reason": "Repeat cancellation"},
        headers=headers,
    )
    assert re_cancel.status_code == 400


# ============================================================================
# 3. Feature 21: Worker Fleet & Queue Execution Tests
# ============================================================================

@pytest.mark.asyncio
async def test_worker_processes_queued_job(test_engine):
    """Worker pops a queued job, executes BFS, updates DB to COMPLETED, and publishes event."""
    session_factory = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    queue = InMemoryTraceQueue()

    # 1. Create a trace in DB
    async with session_factory() as session:
        from backend.app.persistence.case_repository import CaseRepository
        case = await CaseRepository.create(
            session=session,
            case_data=CaseCreate(fir_number="FIR-WORKER-TEST-1"),
            tenant_id="TN-STATE",
        )
        case_id = case.id

        trace = await TraceRepository.create(
            session=session,
            case_id=case_id,
            chain="TRON",
            input_value=ADDR_SUSPECT_ROOT,
            execution_mode="DEMO",
            status="QUEUED",
            max_hops=2,
            tenant_id="TN-STATE",
        )
        trace_id = trace.id

    # 2. Enqueue job
    payload = TraceJobPayload(
        trace_id=trace_id,
        job_id=trace_id,
        case_id=case_id,
        tenant_id="TN-STATE",
        district_id="TN-DISTRICT",
        police_station_id="TN-PS-1",
        officer_id="TEST-OFFICER-1",
        chain="TRON",
        input_value=ADDR_SUSPECT_ROOT,
        asset="TRC20:USDT",
        max_hops=2,
        min_relevant_usd="1.00",
        execution_mode="DEMO",
    )
    await queue.enqueue(payload)

    # 3. Process via TraceWorker
    worker = TraceWorker(
        worker_id="test-worker-alpha",
        queue=queue,
        db_session_factory=session_factory,
    )
    job = await queue.pop(timeout_seconds=0.5)
    assert job is not None
    await worker.process_job(job)

    # 4. Verify DB was updated to COMPLETED or PARTIAL
    async with session_factory() as session:
        updated = await TraceRepository.get_by_id(session, trace_id, tenant_id="TN-STATE")
        assert updated is not None
        assert updated.status in ("COMPLETED", "PARTIAL")
        assert updated.node_count > 0
        assert updated.edge_count > 0
        assert updated.progress_percent == Decimal("100.00")


# ============================================================================
# 4. Feature 23: Worker Heartbeats, Progress & Zombie Sweeper Tests
# ============================================================================

@pytest.mark.asyncio
async def test_heartbeat_manager_acquire_and_release():
    """Verify HeartbeatManager lock acquisition and release."""
    trace_id = "test-trace-lock-1"
    worker_1 = "worker-1"
    worker_2 = "worker-2"

    acq1 = await HeartbeatManager.acquire_lock(trace_id, worker_1, lock_ttl=10)
    assert acq1 is True

    # Same lock cannot be acquired by worker 2
    acq2 = await HeartbeatManager.acquire_lock(trace_id, worker_2, lock_ttl=10)
    assert acq2 is False

    # Release by worker 1
    await HeartbeatManager.release_lock(trace_id, worker_1)

    # Now worker 2 can acquire
    acq2_retry = await HeartbeatManager.acquire_lock(trace_id, worker_2, lock_ttl=10)
    assert acq2_retry is True
    await HeartbeatManager.release_lock(trace_id, worker_2)


@pytest.mark.asyncio
async def test_zombie_recovery_to_retry_and_exhaustion(test_engine):
    """ZombieDetector recovers stale RUNNING job to RETRY, then to FAILED when retries exhausted."""
    session_factory = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)
    queue = InMemoryTraceQueue()

    # 1. Create a stale trace in DB
    async with session_factory() as session:
        from backend.app.persistence.case_repository import CaseRepository
        case = await CaseRepository.create(
            session=session,
            case_data=CaseCreate(fir_number="FIR-ZOMBIE-TEST"),
            tenant_id="TN-STATE",
        )
        trace = await TraceRepository.create(
            session=session,
            case_id=case.id,
            input_value=ADDR_SUSPECT_ROOT,
            execution_mode="DEMO",
            status="RUNNING",
            max_retries=2,
            tenant_id="TN-STATE",
        )
        trace_id = trace.id
        # Manually backdate heartbeat_at to simulate worker crash
        trace.heartbeat_at = datetime.now(timezone.utc) - timedelta(seconds=60)
        trace.started_at = datetime.now(timezone.utc) - timedelta(seconds=60)
        await session.commit()

    # 2. Run zombie sweeper (Attempt 1 -> Transitions to RETRY)
    detector = ZombieDetector(
        db_session_factory=session_factory,
        queue=queue,
        zombie_threshold_seconds=10.0,
    )
    actions = await detector.sweep_zombies()
    assert any(a["trace_id"] == trace_id and a["action"] == "RETRY" for a in actions)

    # Verify state in DB
    async with session_factory() as session:
        t1 = await TraceRepository.get_by_id(session, trace_id, tenant_id="TN-STATE")
        assert t1.status == "RETRY"
        assert t1.retry_count == 1
        # Set retry count to max_retries and backdate heartbeat again
        t1.retry_count = 2
        t1.heartbeat_at = datetime.now(timezone.utc) - timedelta(seconds=60)
        await session.commit()

    # 3. Run zombie sweeper (Attempt 2 -> Retries exhausted -> FAILED)
    actions2 = await detector.sweep_zombies()
    assert any(a["trace_id"] == trace_id and a["action"] == "FAILED" for a in actions2)

    async with session_factory() as session:
        t2 = await TraceRepository.get_by_id(session, trace_id, tenant_id="TN-STATE")
        assert t2.status == "FAILED"
        assert t2.boundary_code == "WORKER_HEARTBEAT_EXPIRED"


@pytest.mark.asyncio
async def test_trace_progress_endpoint(async_client: AsyncClient):
    """GET /api/v1/traces/{id}/progress returns live progress and metrics."""
    token = make_officer_token("IO-M4-05")
    headers = {"Authorization": f"Bearer {token}"}

    case_res = await async_client.post("/api/v1/cases", json={"fir_number": "FIR-PROG-01"}, headers=headers)
    case_id = case_res.json()["id"]

    trace_res = await async_client.post(
        "/api/v1/traces?sync=false",
        json={"case_id": case_id, "input": ADDR_SUSPECT_ROOT, "execution_mode": "DEMO"},
        headers=headers,
    )
    trace_id = trace_res.json()["trace_id"]

    prog_res = await async_client.get(f"/api/v1/traces/{trace_id}/progress", headers=headers)
    assert prog_res.status_code == 200
    data = prog_res.json()
    assert data["trace_id"] == trace_id
    assert data["status"] == "QUEUED"
    assert data["current_hop"] == 0
    assert data["progress_percent"] == 0.0


# ============================================================================
# 5. Feature 24: WebSocket Real-Time Streaming & SSE Tests
# ============================================================================

def test_websocket_initial_state_streaming(test_engine):
    """Connect to /ws/traces/{trace_id} and verify INITIAL_STATE frame."""
    token = make_officer_token("IO-WS-01")
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
                json={"fir_number": "FIR-WS-01"},
                headers={"Authorization": f"Bearer {token}"},
            )
            case_id = case_res.json()["id"]

            trace_res = client.post(
                "/api/v1/traces?sync=false",
                json={"case_id": case_id, "input": ADDR_SUSPECT_ROOT, "execution_mode": "DEMO"},
                headers={"Authorization": f"Bearer {token}"},
            )
            trace_id = trace_res.json()["trace_id"]

            # Connect WebSocket with token
            with client.websocket_connect(f"/ws/traces/{trace_id}?token={token}") as ws:
                data = ws.receive_json()
                assert data["event"] == "INITIAL_STATE"
                assert data["trace_id"] == trace_id
                assert data["status"] == "QUEUED"
                assert "progress" in data
    finally:
        app.dependency_overrides.clear()


def test_websocket_cross_tenant_rejected(test_engine):
    """Cross-tenant WebSocket connection is rejected with policy violation."""
    token_tn = make_officer_token("IO-WS-TN", tenant_id="TN-STATE")
    token_mh = make_officer_token("IO-WS-MH", tenant_id="MH-STATE")
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
                json={"fir_number": "FIR-WS-TN-01"},
                headers={"Authorization": f"Bearer {token_tn}"},
            )
            case_id = case_res.json()["id"]

            trace_res = client.post(
                "/api/v1/traces?sync=false",
                json={"case_id": case_id, "input": ADDR_SUSPECT_ROOT, "execution_mode": "DEMO"},
                headers={"Authorization": f"Bearer {token_tn}"},
            )
            trace_id = trace_res.json()["trace_id"]

            # MH officer attempts to connect to TN trace -> rejected
            with pytest.raises(Exception):
                with client.websocket_connect(f"/ws/traces/{trace_id}?token={token_mh}") as ws:
                    ws.receive_json()
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_sse_stream_initial_state(async_client: AsyncClient):
    """GET /api/v1/traces/{id}/stream returns SSE event stream with initial state."""
    token = make_officer_token("IO-M4-06")
    headers = {"Authorization": f"Bearer {token}"}

    case_res = await async_client.post("/api/v1/cases", json={"fir_number": "FIR-SSE-01"}, headers=headers)
    case_id = case_res.json()["id"]

    trace_res = await async_client.post(
        "/api/v1/traces?sync=true",
        json={"case_id": case_id, "input": ADDR_SUSPECT_ROOT, "execution_mode": "DEMO"},
        headers=headers,
    )
    trace_id = trace_res.json()["trace_id"]

    stream_res = await async_client.get(f"/api/v1/traces/{trace_id}/stream", headers=headers)
    assert stream_res.status_code == 200
    assert "text/event-stream" in stream_res.headers.get("content-type", "")
    assert "INITIAL_STATE" in stream_res.text
