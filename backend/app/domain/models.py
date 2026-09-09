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


class GraphNode(BaseModel):
    id: str = Field(..., description="Unique node identifier (wallet address)")
    address: str = Field(..., description="Wallet address")
    chain: str = Field("TRON", description="Blockchain network")
    node_type: str = Field("unknown", description="suspect, intermediate, endpoint, etc.")
    hop: int = Field(0, description="Minimum hop distance from root suspect wallet")
    total_received: Decimal = Field(Decimal(0), description="Total volume received in USDT")
    total_sent: Decimal = Field(Decimal(0), description="Total volume sent in USDT")
    transaction_count: int = Field(0, description="Observed transaction count")
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class GraphEdge(BaseModel):
    id: str = Field(..., description="Unique edge identifier")
    tx_hash: str = Field(..., description="Transaction hash / ID")
    from_address: str = Field(..., description="Source address")
    to_address: str = Field(..., description="Destination address")
    amount: Decimal = Field(..., description="Normalized transfer amount in token units")
    amount_raw: int = Field(..., description="Raw atomic integer token amount")
    asset: str = Field("TRC20:USDT", description="Asset identifier")
    timestamp: datetime = Field(..., description="Transaction timestamp")
    block_number: Optional[int] = None
    hop: int = Field(1, description="Hop level of this transaction traversal")

    model_config = ConfigDict(from_attributes=True)


class InvestigationGraph(BaseModel):
    nodes: List[GraphNode]
    edges: List[GraphEdge]
    meta: Dict[str, Any] = Field(default_factory=dict)
