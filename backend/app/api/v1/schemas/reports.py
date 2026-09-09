from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from backend.app.domain.reports.models import ReportType


class EvidenceDossierCreateRequest(BaseModel):
    trace_id: str = Field(..., description="ID of the completed multi-hop trace")
    investigator_name: str = Field("IO-Vikram-742", description="Investigating Officer Name / Badge")
    investigator_rank: str = Field("Inspector of Police", description="Officer Designation / Rank")
    police_station: str = Field("Cyber Crime Police Station", description="Originating police station / Cyber Cell")
    include_graph_snapshot: bool = Field(True, description="Whether to embed rendered multi-hop graph snapshot")
    notes: Optional[str] = Field(None, description="Additional case observations to embed in the dossier")


class BNSS94DraftCreateRequest(BaseModel):
    trace_id: str = Field(..., description="ID of the completed multi-hop trace")
    target_vasp: Optional[str] = Field(None, description="Attributed VASP entity name (auto-detected if None)")
    candidate_address: Optional[str] = Field(None, description="Attributed wallet address (auto-detected if None)")
    investigator_name: str = Field("IO-Vikram-742", description="Investigating Officer Name / Badge")
    investigator_rank: str = Field("Inspector of Police", description="Officer Designation / Rank")
    police_station: str = Field("Cyber Crime Police Station", description="Originating Police Station")
    court_jurisdiction: str = Field("Chief Judicial Magistrate / Cyber Special Court", description="Designated court jurisdiction")
    compliance_email: Optional[str] = Field(None, description="Official law enforcement desk contact for the VASP")
    urgency_hours: int = Field(48, description="Requested response turnaround in hours")
    notes: Optional[str] = Field(None, description="Specific context or supplementary FIR details")


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
