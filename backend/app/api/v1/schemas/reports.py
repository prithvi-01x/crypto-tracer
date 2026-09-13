from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
from backend.app.domain.reports.models import ReportType


class EvidenceDossierCreateRequest(BaseModel):
    trace_id: str = Field(..., min_length=1, max_length=64, description="ID of the completed multi-hop trace")
    investigator_name: str = Field("IO-Vikram-742", min_length=2, max_length=128, description="Investigating Officer Name / Badge")
    investigator_rank: str = Field("Inspector of Police", min_length=2, max_length=128, description="Officer Designation / Rank")
    police_station: str = Field("Cyber Crime Police Station", min_length=2, max_length=256, description="Originating police station / Cyber Cell")
    include_graph_snapshot: bool = Field(True, description="Whether to embed rendered multi-hop graph snapshot")
    notes: Optional[str] = Field(None, max_length=4096, description="Additional case observations to embed in the dossier")


class BNSS94DraftCreateRequest(BaseModel):
    trace_id: str = Field(..., min_length=1, max_length=64, description="ID of the completed multi-hop trace")
    target_vasp: Optional[str] = Field(None, max_length=128, description="Attributed VASP entity name (auto-detected if None)")
    candidate_address: Optional[str] = Field(None, max_length=128, description="Attributed wallet address (auto-detected if None)")
    investigator_name: str = Field("IO-Vikram-742", min_length=2, max_length=128, description="Investigating Officer Name / Badge")
    investigator_rank: str = Field("Inspector of Police", min_length=2, max_length=128, description="Officer Designation / Rank")
    police_station: str = Field("Cyber Crime Police Station", min_length=2, max_length=256, description="Originating Police Station")
    court_jurisdiction: str = Field("Chief Judicial Magistrate / Cyber Special Court", min_length=2, max_length=256, description="Designated court jurisdiction")
    compliance_email: Optional[str] = Field(None, max_length=256, description="Official law enforcement desk contact for the VASP")
    urgency_hours: int = Field(48, ge=1, le=720, description="Requested response turnaround in hours (1-720)")
    notes: Optional[str] = Field(None, max_length=4096, description="Specific context or supplementary FIR details")


class Section63BSACreateRequest(BaseModel):
    trace_id: str = Field(..., min_length=1, max_length=64, description="ID of the completed multi-hop trace")
    investigator_name: str = Field("IO-Vikram-742", min_length=2, max_length=128, description="Investigating Officer Name / Badge")
    investigator_rank: str = Field("Inspector of Police", min_length=2, max_length=128, description="Officer Designation / Rank")
    police_station: str = Field("Cyber Crime Police Station", min_length=2, max_length=256, description="Originating police station / Cyber Cell")
    technical_examiner: Optional[str] = Field("Forensic Examiner (Cyber Cell)", max_length=128, description="Technical Cyber Examiner Name/Designation")
    notes: Optional[str] = Field(None, max_length=4096, description="Additional case observations or FIR particulars")


class ReportResponse(BaseModel):
    id: str
    case_id: str
    trace_id: Optional[str] = None
    report_type: ReportType
    title: str
    file_name: str
    file_size_bytes: int
    content_hash: str
    generated_by: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    download_url: str

    model_config = ConfigDict(from_attributes=True)


class ReportJobStatusResponse(BaseModel):
    job_id: str
    report_id: str
    case_id: str
    report_type: ReportType
    status: str  # QUEUED, PROCESSING, COMPLETED, FAILED
    poll_url: str
    created_at: datetime
    completed_at: Optional[datetime] = None
    download_url: Optional[str] = None
    presigned_url: Optional[str] = None
    content_hash: Optional[str] = None
    file_size_bytes: Optional[int] = None
    error_message: Optional[str] = None
    message: str

    model_config = ConfigDict(from_attributes=True)


class PresignedUrlRequest(BaseModel):
    expires_in_seconds: int = Field(900, ge=60, le=86400, description="Expiration in seconds (1 min to 24 hrs, default 15 min / 900s)")


class PresignedUrlResponse(BaseModel):
    report_id: str
    download_url: str
    expires_in_seconds: int
    expires_at: datetime

    model_config = ConfigDict(from_attributes=True)
