import json
import asyncio
import logging
from typing import Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, status, Depends

import redis.asyncio as aioredis
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.persistence.db import get_db, async_session_factory
from backend.app.persistence.redis import redis_pool
from backend.app.persistence.trace_repository import TraceRepository
from backend.app.domain.tracing.fsm import TraceStateMachine
from backend.app.core.auth import decode_access_token, OfficerSession, Role
from backend.app.worker.queue import get_trace_queue, InMemoryTraceQueue
from backend.app.config import settings

logger = logging.getLogger("crypto_tracer.ws")
router = APIRouter(tags=["WebSockets"])


def authenticate_ws_connection(token: Optional[str], websocket: WebSocket) -> Optional[OfficerSession]:
    """Extract and validate JWT officer session from token param or Authorization header."""
    raw_token = token
    if not raw_token:
        auth_header = websocket.headers.get("authorization") or websocket.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            raw_token = auth_header[7:].strip()

    if raw_token:
        try:
            claims = decode_access_token(raw_token)
            return OfficerSession(
                officer_id=claims.sub,
                name=claims.name or "Officer",
                badge_number=claims.badge_number or "BADGE-1",
                unit=claims.unit or "Cyber Crime Cell",
                role=claims.role,
                is_authenticated=True,
                tenant_id=claims.tenant_id,
                district_id=claims.district_id,
                police_station_id=claims.police_station_id,
                station_id=claims.police_station_id,
            )
        except Exception:
            return None

    # In development/test mode, fallback to default officer session for ease of testing
    if settings.APP_ENV.lower() != "production":
        return OfficerSession(
            officer_id="default-officer",
            name="Inspector P. Sharma",
            badge_number="CYBER-DELHI-4029",
            unit="District Cyber Crime Cell",
            role=Role.INVESTIGATING_OFFICER.value,
            is_authenticated=True,
            tenant_id=settings.DEFAULT_TENANT_ID,
            district_id=settings.DEFAULT_DISTRICT_ID,
            police_station_id=settings.DEFAULT_POLICE_STATION_ID,
            station_id=settings.DEFAULT_POLICE_STATION_ID,
        )

    return None


@router.websocket("/ws/traces/{trace_id}")
async def trace_websocket_endpoint(
    websocket: WebSocket,
    trace_id: str,
    token: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """
    Real-time WebSocket streaming endpoint for trace execution progress and graphs.
    Enforces authentication and tenant isolation (IDOR protection).
    """
    # 1. Authenticate connection
    officer = authenticate_ws_connection(token, websocket)
    if not officer:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Unauthorized")
        return

    # 2. Check tenant scoping and trace existence
    trace = await TraceRepository.get_by_id(db, trace_id, tenant_id=officer.tenant_id)
    if not trace:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Trace not found or access denied")
        return

    initial_status = trace.status
    initial_progress = {
        "current_hop": trace.current_hop or 0,
        "max_hops": trace.max_hops,
        "progress_percent": float(trace.progress_percent or 0.0),
        "node_count": trace.node_count or 0,
        "edge_count": trace.edge_count or 0,
    }
    graph_data = trace.graph_data if TraceStateMachine.is_terminal(trace.status) else None

    # 3. Accept handshake
    await websocket.accept()

    # 4. Stream INITIAL_STATE frame
    await websocket.send_json({
        "event": "INITIAL_STATE",
        "trace_id": trace_id,
        "status": initial_status,
        "progress": initial_progress,
        "graph": graph_data,
    })

    # If trace is already terminal, close cleanly
    if TraceStateMachine.is_terminal(initial_status):
        await websocket.close(code=status.WS_1000_NORMAL_CLOSURE, reason="Trace already completed")
        return

    # 5. Subscribe to event queue / pubsub
    in_mem_queue = get_trace_queue(None)
    sub_queue = in_mem_queue.subscribe(trace_id)
    try:
        while True:
            data = await sub_queue.get()
            await websocket.send_json(data)
            if data.get("event") in ("JOB_COMPLETED", "JOB_FAILED", "JOB_CANCELLED"):
                await websocket.close(code=status.WS_1000_NORMAL_CLOSURE)
                break
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.warning(f"WebSocket client error: {e}")
    finally:
        in_mem_queue.unsubscribe(trace_id, sub_queue)
