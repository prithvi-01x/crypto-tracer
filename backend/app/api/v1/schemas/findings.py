from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict

from backend.app.domain.findings.models import FindingSeverity, FindingType, FindingStatus, ForensicFinding


class EvidenceReferenceSchema(BaseModel):
    id: str
    title: str
    classification: str
    content_hash: str
    evidence_type: str

    model_config = ConfigDict(from_attributes=True)


class FindingResponse(BaseModel):
    finding_id: str
    case_id: str
    trace_id: str
    severity: str
    finding_type: str
    title: str
    description: str
    timestamp: datetime
    source_signal: str
    confidence: Optional[float] = None
    related_address: Optional[str] = None
    related_tx_hash: Optional[str] = None
    related_vasp: Optional[str] = None
    evidence_refs: List[EvidenceReferenceSchema] = Field(default_factory=list)
    status: str
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    review_notes: Optional[str] = None
    graph_node_id: Optional[str] = None
    graph_edge_id: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_domain(cls, f: ForensicFinding) -> "FindingResponse":
        return cls(
            finding_id=f.finding_id,
            case_id=f.case_id,
            trace_id=f.trace_id,
            severity=f.severity.value if hasattr(f.severity, "value") else str(f.severity),
            finding_type=f.finding_type.value if hasattr(f.finding_type, "value") else str(f.finding_type),
            title=f.title,
            description=f.description,
            timestamp=f.timestamp,
            source_signal=f.source_signal,
            confidence=f.confidence,
            related_address=f.related_address,
            related_tx_hash=f.related_tx_hash,
            related_vasp=f.related_vasp,
            evidence_refs=[EvidenceReferenceSchema(**ref.model_dump()) for ref in f.evidence_refs],
            status=f.status.value if hasattr(f.status, "value") else str(f.status),
            reviewed_by=f.reviewed_by,
            reviewed_at=f.reviewed_at,
            review_notes=f.review_notes,
            graph_node_id=f.graph_node_id,
            graph_edge_id=f.graph_edge_id,
        )


class FindingReviewRequest(BaseModel):
    status: FindingStatus = Field(..., description="Target status: OPEN, REVIEWED, or DISMISSED")
    notes: Optional[str] = Field(None, description="Investigator notes explaining decision")
    reviewed_by: Optional[str] = Field("investigator", description="Officer identity or identifier")


class FindingListResponse(BaseModel):
    case_id: str
    trace_id: Optional[str] = None
    total: int
    open_count: int
    reviewed_count: int
    dismissed_count: int
    critical_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0
    info_count: int = 0
    findings: List[FindingResponse] = Field(default_factory=list)
