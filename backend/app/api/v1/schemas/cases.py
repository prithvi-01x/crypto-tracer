from datetime import datetime
from decimal import Decimal
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict


class CaseBase(BaseModel):
    fir_number: str = Field(..., description="FIR / Police Report Number", json_schema_extra={"example": "2026/812"})
    victim_reference: Optional[str] = Field(None, description="Victim identifier or name", json_schema_extra={"example": "RAMESH-001"})
    loss_amount_inr: Optional[Decimal] = Field(None, description="Reported financial loss in INR", json_schema_extra={"example": 500000.00})
    ack_number: Optional[str] = Field(None, description="1930 Cybercrime Portal Acknowledgement Number", json_schema_extra={"example": "1930-DL-2026-812"})
    suspect_wallet: Optional[str] = Field(None, description="Suspect wallet address or Transaction ID", json_schema_extra={"example": "TYDZSxdBzWnCuB4jF3K6j5X3qW7b9X1234"})
    chain: str = Field("TRON", description="Target blockchain", json_schema_extra={"example": "TRON"})
    asset: str = Field("TRC20:USDT", description="Target cryptocurrency asset", json_schema_extra={"example": "TRC20:USDT"})
    notes: Optional[str] = Field(None, description="Investigation notes or modus operandi summary", json_schema_extra={"example": "Telegram task-based fraudulent investment scheme"})


class CaseCreate(CaseBase):
    pass


class CaseUpdate(BaseModel):
    status: Optional[str] = Field(None, description="Updated case status")
    notes: Optional[str] = Field(None, description="Additional investigation notes")


class CaseResponse(CaseBase):
    id: str
    status: str
    created_at: datetime
    updated_at: datetime
    trace_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class CaseListResponse(BaseModel):
    total: int
    cases: List[CaseResponse]
