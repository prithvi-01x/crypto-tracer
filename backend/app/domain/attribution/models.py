from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict, Field


class VASPEntry(BaseModel):
    vasp_id: str = Field(..., description="Unique entity slug, e.g. binance, okx, bybit")
    entity_name: str = Field(..., description="Official VASP display name")
    chain: str = Field("TRON", description="Target blockchain")
    address: str = Field(..., description="Known wallet address on-chain")
    address_type: str = Field("hot_wallet", description="hot_wallet, cold_wallet, deposit_sweeper, settlement")
    source: str = Field(..., description="Provenance source of tag (e.g. proof_of_reserves, court_order, public_disclosure)")
    verification_status: str = Field("VERIFIED", description="VERIFIED, UNVERIFIED, HEURISTIC")
    version: str = Field("2026.1.0", description="VASP registry schema version")
    description: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class SweepResult(BaseModel):
    sweep_ratio: float = Field(..., description="Ratio of swept funds to relevant received funds [0.0 - 1.0]")
    received_usdt: Decimal = Field(..., description="Total relevant USDT received")
    swept_usdt: Decimal = Field(..., description="Total USDT swept out")
    dominant_destination: Optional[str] = Field(None, description="Dominant outgoing recipient wallet")
    destination_entity: Optional[str] = Field(None, description="Entity name if dominant destination is known VASP")
    destination_verified: bool = Field(False, description="Whether destination entity is verified")
    is_sweep: bool = Field(False, description="Whether sweep ratio exceeds minimum heuristic threshold (>= 0.70)")
    is_strong_sweep: bool = Field(False, description="Whether sweep ratio is strong consolidation (>= 0.90)")
    score: float = Field(..., description="Normalized sweep factor score [0.0 - 1.0]")
    explanation: str = Field(..., description="Explainable description of the sweep behavior")


class FanInResult(BaseModel):
    distinct_senders_count: int = Field(..., description="Count of distinct upstream addresses sending to this wallet")
    senders: List[str] = Field(default_factory=list, description="Observed sender addresses in the trace")
    is_high_fan_in: bool = Field(False, description="Whether distinct senders count indicates omnibus aggregation (>= 3)")
    score: float = Field(..., description="Normalized fan-in factor score [0.0 - 1.0]")
    explanation: str = Field(..., description="Explainable description of fan-in concentration")


class TemporalResult(BaseModel):
    deposit_time: Optional[datetime] = Field(None, description="Earliest relevant incoming deposit timestamp")
    sweep_time: Optional[datetime] = Field(None, description="Earliest subsequent outgoing sweep timestamp")
    delay_seconds: Optional[float] = Field(None, description="Observed deposit-to-sweep delay in seconds")
    delay_hours: Optional[float] = Field(None, description="Observed delay in hours")
    delay_formatted: str = Field("N/A", description="Human-readable delay, e.g. '14 minutes, 20 seconds'")
    score: float = Field(..., description="Normalized temporal score based on exponential decay [0.0 - 1.0]")
    explanation: str = Field(..., description="Explainable description of temporal clustering")


class FactorScores(BaseModel):
    direct_tag: float = Field(..., ge=0.0, le=1.0, description="Weight: 0.35")
    sweep: float = Field(..., ge=0.0, le=1.0, description="Weight: 0.35")
    fan_in: float = Field(..., ge=0.0, le=1.0, description="Weight: 0.15")
    temporal: float = Field(..., ge=0.0, le=1.0, description="Weight: 0.15")


class FactorExplanations(BaseModel):
    direct_tag: str
    sweep: str
    fan_in: str
    temporal: str


class VASPCandidate(BaseModel):
    candidate_address: str = Field(..., description="Wallet address evaluated for VASP attribution")
    vasp_id: str = Field(..., description="Attributed VASP slug")
    vasp_name: str = Field(..., description="Attributed VASP entity display name")
    hypothesis_label: str = Field(..., description="Standardized inference wording, e.g. 'Likely VASP: Binance'")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Composite confidence score [0.0 - 1.0]")
    confidence_percentage: float = Field(..., description="Confidence formatted as percentage, e.g. 94.2")
    confidence_band: str = Field(..., description="LOW, MODERATE, HIGH, VERY HIGH")
    verification_status: str = Field("VERIFIED", description="VERIFIED, UNVERIFIED, HEURISTIC")
    factors: FactorScores
    explanations: FactorExplanations
    evidence_bullet_points: List[str] = Field(default_factory=list, description="Checkmark evidence points for UI display")
    sweep_details: Optional[SweepResult] = None
    fan_in_details: Optional[FanInResult] = None
    temporal_details: Optional[TemporalResult] = None

    model_config = ConfigDict(from_attributes=True)


class AttributionReport(BaseModel):
    trace_id: str
    engine_version: str = "0.1.0"
    evaluated_at: datetime = Field(default_factory=datetime.utcnow)
    disclaimer: str = Field(
        "Attribution is an investigative hypothesis based on observable on-chain transaction patterns, "
        "not legal proof of account ownership.",
        description="Mandatory legal disclaimer from PRD.md"
    )
    candidates: List[VASPCandidate] = Field(default_factory=list)
    best_candidate: Optional[VASPCandidate] = None
    meta: Dict[str, Any] = Field(default_factory=dict)
