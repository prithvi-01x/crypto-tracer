from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Dict, Any
from pydantic import BaseModel, ConfigDict, Field


class ReportType(str, Enum):
    EVIDENCE_DOSSIER = "EVIDENCE_DOSSIER"
    SECTION_94_BNSS = "SECTION_94_BNSS"
    SECTION_63_BSA = "SECTION_63_BSA"


class ReportStatus(str, Enum):
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ReportMetadata(BaseModel):
    id: str
    case_id: str
    trace_id: Optional[str] = None
    report_type: ReportType
    title: str
    file_path: str
    file_size_bytes: int = 0
    content_hash: str
    generated_by: str = "investigator"
    status: str = "COMPLETED"
    job_id: Optional[str] = None
    storage_backend: str = "LOCAL"
    storage_path: Optional[str] = None
    s3_key: Optional[str] = None
    file_hash: Optional[str] = None
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
