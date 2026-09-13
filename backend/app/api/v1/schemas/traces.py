from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
from backend.app.domain.models import InvestigationGraph


class TraceCreateRequest(BaseModel):
    case_id: str = Field(..., min_length=1, max_length=64, description="Associated case UUID", json_schema_extra={"example": "d61da092-8a26-47dd-9bbb-471a508bf2a2"})
    chain: str = Field("TRON", min_length=2, max_length=20, description="Target blockchain", json_schema_extra={"example": "TRON"})
    input_type: str = Field("address", pattern="^(address|tx_hash)$", description="Input type ('address' or 'tx_hash')", json_schema_extra={"example": "address"})
    input: str = Field(..., min_length=1, max_length=128, description="Target wallet address or transaction ID", json_schema_extra={"example": "TYDZSxdBzWnCuB4jF3K6j5X3qW7b9X1234"})
    asset: str = Field("TRC20:USDT", min_length=2, max_length=32, description="Target asset identifier", json_schema_extra={"example": "TRC20:USDT"})
    max_hops: int = Field(4, ge=1, le=6, description="Maximum graph traversal depth (1 to 6)", json_schema_extra={"example": 4})
    min_relevant_usd: Decimal = Field(Decimal("1.00"), ge=0, le=1000000, description="Minimum relevant transfer value", json_schema_extra={"example": 1.00})
    execution_mode: str = Field("LIVE", pattern="^(DEMO|LIVE)$", description="Execution mode: 'LIVE' or 'DEMO'")
    sync: Optional[bool] = Field(None, description="Force sync (True -> 201) or async (False -> 202) execution")


class TraceStatusResponse(BaseModel):
    trace_id: str
    case_id: str
    status: str
    chain: str
    input_value: str
    asset: str
    max_hops: int
    execution_mode: str = "LIVE"
    duration_ms: Optional[int] = None
    node_count: int = 0
    edge_count: int = 0
    pruned_count: int = 0
    nodes: Optional[int] = None
    edges: Optional[int] = None
    pruned_nodes: Optional[int] = None
    raw_transfers_count: int = 0
    relevant_transfers_count: int = 0
    boundary_code: Optional[str] = None
    investigator_summary: Optional[str] = None
    is_partial: bool = False
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class JobStatusResponse(BaseModel):
    job_id: str
    trace_id: str
    case_id: str
    status: str = "QUEUED"
    chain: str = "TRON"
    input_value: str = ""
    asset: str = "TRC20:USDT"
    max_hops: int = 4
    execution_mode: str = "LIVE"
    poll_url: str
    ws_url: str
    created_at: datetime
    message: str = "Trace job queued for background execution."

    model_config = ConfigDict(from_attributes=True)


class TraceCancelRequest(BaseModel):
    reason: Optional[str] = Field("Cancelled by investigator", max_length=500)


class TraceCancelResponse(BaseModel):
    trace_id: str
    status: str = "CANCEL"
    message: str = "Trace execution cancelled by investigator."
    cancelled_at: datetime


class TraceProgressResponse(BaseModel):
    trace_id: str
    status: str
    current_hop: int = 0
    max_hops: int = 4
    progress_percent: float = 0.0
    node_count: int = 0
    edge_count: int = 0
    pruned_count: int = 0
    heartbeat_at: Optional[datetime] = None
    error_message: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class TraceListResponse(BaseModel):
    items: List[TraceStatusResponse] = Field(default_factory=list)
    total: int = 0
    next_cursor: Optional[str] = None
    has_more: bool = False

    model_config = ConfigDict(from_attributes=True)
