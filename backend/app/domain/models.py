from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict, Field


class Transfer(BaseModel):
    chain: str = Field("TRON", description="Blockchain network name")
    tx_hash: str = Field(..., description="Unique transaction hash / ID")
    block_number: Optional[int] = Field(None, description="Block height if available")
    timestamp: datetime = Field(..., description="Transaction timestamp in UTC")
    from_address: str = Field(..., description="Sender wallet address")
    to_address: str = Field(..., description="Recipient wallet address")
    asset_contract: str = Field(..., description="Smart contract address of the token")
    asset_symbol: str = Field("USDT", description="Token symbol")
    amount_raw: int = Field(..., description="Raw integer token amount in atomic units")
    amount_decimal: Decimal = Field(..., description="Normalized human-readable token amount")
    source: str = Field("trongrid", description="Data provenance / source name")
    raw: Optional[Dict[str, Any]] = Field(default=None, description="Original provider payload for evidence auditing")

    model_config = ConfigDict(from_attributes=True)


class TransferPage(BaseModel):
    transfers: List[Transfer]
    next_cursor: Optional[str] = None
    has_more: bool = False
    cached: bool = False
    total_fetched: int = 0
