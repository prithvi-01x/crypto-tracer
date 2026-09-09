from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict

from backend.app.domain.attribution.models import VASPCandidate, AttributionReport


class AttributionFactorsSchema(BaseModel):
    direct_tag: float = Field(..., description="Weight: 0.35")
    sweep: float = Field(..., description="Weight: 0.35")
    fan_in: float = Field(..., description="Weight: 0.15")
    temporal: float = Field(..., description="Weight: 0.15")


class AttributionExplanationsSchema(BaseModel):
    direct_tag: str
    sweep: str
    fan_in: str
    temporal: str


class CandidateResponse(BaseModel):
    candidate_address: str
    vasp: str = Field(..., description="Attributed entity name")
    vasp_name: str = Field(..., description="Attributed entity name")
    vasp_id: str
    hypothesis_label: str
    confidence: float = Field(..., description="Normalized confidence score [0.0 - 1.0]")
    confidence_percentage: float = Field(..., description="Confidence percentage e.g. 94.2")
    confidence_band: str = Field(..., description="LOW, MODERATE, HIGH, VERY HIGH")
    verification_status: str = Field("VERIFIED", description="VERIFIED, UNVERIFIED, HEURISTIC")
    factors: AttributionFactorsSchema
    explanations: AttributionExplanationsSchema
    evidence_bullet_points: List[str] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_domain(cls, c: VASPCandidate) -> "CandidateResponse":
        return cls(
            candidate_address=c.candidate_address,
            vasp=c.vasp_name,
            vasp_name=c.vasp_name,
            vasp_id=c.vasp_id,
            hypothesis_label=c.hypothesis_label,
            confidence=c.confidence,
            confidence_percentage=c.confidence_percentage,
            confidence_band=c.confidence_band,
            verification_status=c.verification_status,
            factors=AttributionFactorsSchema(**c.factors.model_dump()),
            explanations=AttributionExplanationsSchema(**c.explanations.model_dump()),
            evidence_bullet_points=c.evidence_bullet_points,
        )


class AttributionResponse(BaseModel):
    trace_id: str
    engine_version: str = "0.1.0"
    disclaimer: str
    evaluated_at: datetime
    candidates: List[CandidateResponse]
    best_candidate: Optional[CandidateResponse] = None
    meta: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_domain(cls, report: AttributionReport) -> "AttributionResponse":
        return cls(
            trace_id=report.trace_id,
            engine_version=report.engine_version,
            disclaimer=report.disclaimer,
            evaluated_at=report.evaluated_at,
            candidates=[CandidateResponse.from_domain(c) for c in report.candidates],
            best_candidate=CandidateResponse.from_domain(report.best_candidate) if report.best_candidate else None,
            meta=report.meta,
        )
