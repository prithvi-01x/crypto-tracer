from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, ConfigDict, Field


class ReportType(str, Enum):
    EVIDENCE_DOSSIER = "EVIDENCE_DOSSIER"
    SECTION_94_BNSS = "SECTION_94_BNSS"


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
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(from_attributes=True)
