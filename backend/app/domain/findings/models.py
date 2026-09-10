from datetime import datetime, timezone
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class FindingSeverity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


class FindingType(str, Enum):
    VASP_CONSOLIDATION = "VASP_CONSOLIDATION"
    RAPID_SWEEP = "RAPID_SWEEP"
    FAN_IN_CONCENTRATION = "FAN_IN_CONCENTRATION"
    MULTI_HOP_LAYERING = "MULTI_HOP_LAYERING"
    MIXER_ENCOUNTERED = "MIXER_ENCOUNTERED"
    BRIDGE_ENCOUNTERED = "BRIDGE_ENCOUNTERED"
    LOW_CONFIDENCE_ATTRIBUTION = "LOW_CONFIDENCE_ATTRIBUTION"
    OPERATIONAL_BOUNDARY = "OPERATIONAL_BOUNDARY"
    TRACE_COMPLETED = "TRACE_COMPLETED"


class FindingStatus(str, Enum):
    OPEN = "OPEN"
    REVIEWED = "REVIEWED"
    DISMISSED = "DISMISSED"


class EvidenceReference(BaseModel):
    id: str = Field(..., description="Evidence item unique identifier")
    title: str = Field(..., description="Short human-readable title of evidence")
    classification: str = Field(..., description="OBSERVED, DERIVED, INFERRED, HUMAN_ACTION")
    content_hash: str = Field(..., description="SHA-256 cryptographic hash of evidence content")
    evidence_type: str = Field(..., description="Fine-grained category of evidence")

    model_config = ConfigDict(from_attributes=True)


class ForensicFinding(BaseModel):
    finding_id: str = Field(..., description="Unique deterministic identifier for finding")
    case_id: str = Field(..., description="Parent case identifier")
    trace_id: str = Field(..., description="Parent trace identifier")
    severity: FindingSeverity = Field(..., description="Severity level (CRITICAL, HIGH, MEDIUM, LOW, INFO)")
    finding_type: FindingType = Field(..., description="Canonical categorization of forensic finding")
    title: str = Field(..., description="Clear, professional headline summarizing finding")
    description: str = Field(..., description="Detailed, legally objective explanation of the signal")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Evaluation timestamp")
    source_signal: str = Field(..., description="Underlying pipeline signal (e.g. sweep_analyzer, temporal_decay, boundary_engine)")
    confidence: Optional[float] = Field(None, description="Quantitative confidence score [0.0 - 1.0] when applicable")
    related_address: Optional[str] = Field(None, description="Primary wallet address associated with finding")
    related_tx_hash: Optional[str] = Field(None, description="Transaction hash associated with finding")
    related_vasp: Optional[str] = Field(None, description="Attributed or downstream VASP entity name when applicable")
    evidence_refs: List[EvidenceReference] = Field(default_factory=list, description="Cryptographic evidence items supporting this finding")
    status: FindingStatus = Field(default=FindingStatus.OPEN, description="Investigator workflow status")
    reviewed_by: Optional[str] = Field(None, description="Investigating officer who reviewed finding")
    reviewed_at: Optional[datetime] = Field(None, description="Timestamp of review")
    review_notes: Optional[str] = Field(None, description="Investigative notes entered during review")
    graph_node_id: Optional[str] = Field(None, description="Node address in Cytoscape canvas for focus/highlighting")
    graph_edge_id: Optional[str] = Field(None, description="Edge ID in Cytoscape canvas for focus/highlighting")

    model_config = ConfigDict(from_attributes=True)
