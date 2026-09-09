from datetime import datetime, timezone
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict, Field


class EvidenceClassification(str, Enum):
    OBSERVED = "OBSERVED"
    DERIVED = "DERIVED"
    INFERRED = "INFERRED"
    HUMAN_ACTION = "HUMAN_ACTION"


class EvidenceType(str, Enum):
    # OBSERVED
    TRANSACTION_RECORD = "TRANSACTION_RECORD"
    WALLET_OBSERVATION = "WALLET_OBSERVATION"
    VASP_REGISTRY_RECORD = "VASP_REGISTRY_RECORD"

    # DERIVED
    HOP_TRAVERSAL = "HOP_TRAVERSAL"
    PATH_FORMATION = "PATH_FORMATION"
    PRUNING_DECISION = "PRUNING_DECISION"
    SWEEP_ANALYSIS = "SWEEP_ANALYSIS"
    FAN_IN_ANALYSIS = "FAN_IN_ANALYSIS"
    TEMPORAL_ANALYSIS = "TEMPORAL_ANALYSIS"

    # INFERRED
    VASP_ATTRIBUTION = "VASP_ATTRIBUTION"
    CONFIDENCE_CALCULATION = "CONFIDENCE_CALCULATION"
    DOWNSTREAM_CONSOLIDATION = "DOWNSTREAM_CONSOLIDATION"

    # HUMAN_ACTION
    CASE_INITIATION = "CASE_INITIATION"
    TRACE_EXECUTION = "TRACE_EXECUTION"
    EVIDENCE_REVIEW = "EVIDENCE_REVIEW"
    ATTRIBUTION_REVIEW = "ATTRIBUTION_REVIEW"
    INVESTIGATION_NOTE = "INVESTIGATION_NOTE"


class AuditEventType(str, Enum):
    CASE_OPENED = "CASE_OPENED"
    TRACE_STARTED = "TRACE_STARTED"
    TRANSACTION_VIEWED = "TRANSACTION_VIEWED"
    ATTRIBUTION_VIEWED = "ATTRIBUTION_VIEWED"
    EVIDENCE_REVIEWED = "EVIDENCE_REVIEWED"
    ATTRIBUTION_ACCEPTED = "ATTRIBUTION_ACCEPTED"
    ATTRIBUTION_REJECTED = "ATTRIBUTION_REJECTED"
    REPORT_GENERATED = "REPORT_GENERATED"


class EvidenceItem(BaseModel):
    id: str = Field(..., description="Unique evidence identifier (e.g. ev_tx_hash or UUID)")
    case_id: str = Field(..., description="Parent case identifier")
    trace_id: Optional[str] = Field(None, description="Parent trace identifier if trace-scoped")
    evidence_type: EvidenceType = Field(..., description="Fine-grained evidence category")
    classification: EvidenceClassification = Field(..., description="OBSERVED, DERIVED, INFERRED, HUMAN_ACTION")
    title: str = Field(..., description="Short human-readable title for UI & dossiers")
    description: Optional[str] = Field(None, description="Detailed explanatory text")
    source: str = Field(..., description="Data provider or engine subsystem (e.g. trongrid, bfs_engine, vasp_registry)")
    source_reference: Optional[str] = Field(None, description="External identifier (tx_hash, address, registry version, badge ID)")
    payload: Dict[str, Any] = Field(default_factory=dict, description="Structured factual/analytical payload")
    parent_evidence_ids: List[str] = Field(default_factory=list, description="IDs of precursor evidence items forming provenance DAG")
    content_hash: str = Field(..., description="Cryptographic SHA-256 hash of the canonicalized evidence payload")
    engine_version: str = Field("0.1.0", description="Crypto-Tracer engine version")
    configuration_snapshot: Optional[Dict[str, Any]] = Field(None, description="Configuration parameters at time of creation")
    collected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Timestamp when raw fact was collected")
    analysis_timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Timestamp when analysis occurred")

    model_config = ConfigDict(from_attributes=True)


class AuditEvent(BaseModel):
    id: str = Field(..., description="Unique audit event UUID")
    case_id: str = Field(..., description="Parent case identifier")
    trace_id: Optional[str] = Field(None, description="Trace identifier if event relates to a trace")
    actor_id: str = Field("investigator", description="Identity of investigator or system agent")
    event_type: AuditEventType = Field(..., description="Type of investigator action")
    action_summary: str = Field(..., description="Human-readable description of the action taken")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Contextual action metadata")
    content_hash: str = Field(..., description="Deterministic SHA-256 hash of event contents")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Action timestamp")

    model_config = ConfigDict(from_attributes=True)


class ProvenanceChain(BaseModel):
    trace_id: str
    case_id: str
    total_evidence_count: int
    observed_count: int
    derived_count: int
    inferred_count: int
    human_action_count: int
    items: List[EvidenceItem]

    model_config = ConfigDict(from_attributes=True)
