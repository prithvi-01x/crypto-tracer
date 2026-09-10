from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class EvidenceItemResponse(BaseModel):
    id: str
    case_id: str
    trace_id: Optional[str] = None
    evidence_type: str
    classification: str = Field(..., description="OBSERVED, DERIVED, INFERRED, HUMAN_ACTION")
    title: str
    description: Optional[str] = None
    source: str
    source_reference: Optional[str] = None
    payload: Dict[str, Any] = Field(default_factory=dict)
    parent_evidence_ids: List[str] = Field(default_factory=list)
    content_hash: str
    engine_version: str = "0.1.0"
    configuration_snapshot: Optional[Dict[str, Any]] = None
    collected_at: datetime
    analysis_timestamp: datetime
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EvidenceChainResponse(BaseModel):
    trace_id: Optional[str] = None
    case_id: str
    total_evidence_count: int
    observed_count: int
    derived_count: int
    inferred_count: int
    human_action_count: int
    items: List[EvidenceItemResponse]

    model_config = ConfigDict(from_attributes=True)


class AuditEventCreateRequest(BaseModel):
    actor_id: str = Field("investigator", description="Officer ID or badge reference")
    event_type: str = Field(..., description="CASE_OPENED, TRACE_STARTED, EVIDENCE_REVIEWED, ATTRIBUTION_ACCEPTED, etc.")
    action_summary: str = Field(..., description="Description of the action taken")
    trace_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AuditEventResponse(BaseModel):
    id: str
    case_id: str
    trace_id: Optional[str] = None
    actor_id: str
    event_type: str
    action_summary: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    content_hash: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AttributionReviewRequest(BaseModel):
    actor_id: str = Field("investigator", description="Officer badge / investigator reference")
    decision: str = Field(..., description="ACCEPT or REJECT")
    notes: Optional[str] = Field(None, description="Investigative justification notes")
    trace_id: Optional[str] = Field(None, description="Associated trace ID if reviewing within a trace context")


class AttributionReviewResponse(BaseModel):
    status: str
    candidate_address: str
    decision: str
    evidence_id: str
    audit_event_id: str
    reviewed_at: datetime

    model_config = ConfigDict(from_attributes=True)
