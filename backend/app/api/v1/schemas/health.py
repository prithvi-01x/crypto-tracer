from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel


class ServiceComponentHealth(BaseModel):
    status: str
    latency_ms: Optional[float] = None
    error: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    app: str
    environment: str
    version: str
    timestamp: datetime
    services: Dict[str, ServiceComponentHealth]
