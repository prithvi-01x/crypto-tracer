from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
from backend.app.domain.models import InvestigationGraph


class TraceCreateRequest(BaseModel):
    case_id: str = Field(..., description="Associated case UUID", json_schema_extra={"example": "d61da092-8a26-47dd-9bbb-471a508bf2a2"})
    chain: str = Field("TRON", description="Target blockchain", json_schema_extra={"example": "TRON"})
    input_type: str = Field("address", description="Input type ('address' or 'tx_hash')", json_schema_extra={"example": "address"})
    input: str = Field(..., description="Target wallet address or transaction ID", json_schema_extra={"example": "TYDZSxdBzWnCuB4jF3K6j5X3qW7b9X1234"})
    asset: str = Field("TRC20:USDT", description="Target asset identifier", json_schema_extra={"example": "TRC20:USDT"})
    max_hops: int = Field(4, ge=1, le=10, description="Maximum graph traversal depth", json_schema_extra={"example": 4})
    min_relevant_usd: Decimal = Field(Decimal("1.00"), ge=0, description="Minimum relevant transfer value", json_schema_extra={"example": 1.00})
    execution_mode: str = Field("DEMO", description="Execution mode: 'DEMO' (deterministic fixture replay) or 'LIVE' (real-time blockchain query)")


class TraceStatusResponse(BaseModel):
    trace_id: str
    case_id: str
    status: str
    chain: str
    input_value: str
    asset: str
    max_hops: int
    execution_mode: str = "DEMO"
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
