from enum import Enum
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class TraceExecutionStatus(str, Enum):
    """
    Lifecycle status of a multi-hop blockchain trace.
    Explicitly separates fully traversed graphs from partial graphs truncated by boundaries,
    and unrecoverable failures.
    """
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


class BoundaryCode(str, Enum):
    """
    Taxonomy of failure conditions and operational boundaries in forensic blockchain tracing.
    """
    # Input Validation Boundaries
    INVALID_ADDRESS = "INVALID_ADDRESS"
    UNSUPPORTED_CHAIN = "UNSUPPORTED_CHAIN"
    UNSUPPORTED_ASSET = "UNSUPPORTED_ASSET"

    # Ingestion / Provider Boundaries
    PROVIDER_TIMEOUT = "PROVIDER_TIMEOUT"
    PROVIDER_RATE_LIMITED = "PROVIDER_RATE_LIMITED"

    # Traversal Graph Boundaries
    NO_TRANSFERS_FOUND = "NO_TRANSFERS_FOUND"
    NO_RELEVANT_PATH = "NO_RELEVANT_PATH"
    MAX_HOPS_REACHED = "MAX_HOPS_REACHED"
    MAX_NODES_REACHED = "MAX_NODES_REACHED"
    MAX_EDGES_REACHED = "MAX_EDGES_REACHED"

    # Obfuscation & Cross-Chain Boundaries
    MIXER_BOUNDARY = "MIXER_BOUNDARY"
    BRIDGE_BOUNDARY = "BRIDGE_BOUNDARY"

    # Attribution Boundaries
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    NO_VASP_FOUND = "NO_VASP_FOUND"

    # Export & Reporting Boundaries
    REPORT_GENERATION_FAILED = "REPORT_GENERATION_FAILED"


class TraceBoundaryInfo(BaseModel):
    """
    Structured forensic explanation of an operational boundary or failure encountered during tracing.
    Provides technical context and human-interpretable rationale for law enforcement investigators.
    """
    code: BoundaryCode = Field(..., description="Canonical boundary code")
    category: str = Field(..., description="Boundary category (INPUT_ERROR, PROVIDER_ERROR, TRAVERSAL_LIMIT, OBFUSCATION, etc.)")
    is_partial: bool = Field(False, description="Whether the trace result represents a valid partial graph")
    terminal: bool = Field(True, description="Whether further traversal expansion was halted")
    address: Optional[str] = Field(None, description="Wallet address associated with the boundary")
    hop: Optional[int] = Field(None, description="Hop depth where boundary was reached")
    entity_name: Optional[str] = Field(None, description="Entity or service name if applicable (e.g. Mixer or Bridge name)")
    technical_details: Optional[str] = Field(None, description="Low-level error or configuration constraint details")
    investigator_explanation: str = Field(..., description="Plain-English explanation designed for police investigation notes")


def get_default_investigator_explanation(code: BoundaryCode, **kwargs) -> str:
    """
    Generate standard investigator explanations for each boundary code.
    """
    addr = kwargs.get("address", "target wallet")
    hop = kwargs.get("hop", 0)
    entity = kwargs.get("entity_name", "Unknown Service")
    limit = kwargs.get("limit", "")

    explanations: Dict[BoundaryCode, str] = {
        BoundaryCode.INVALID_ADDRESS: (
            f"Address '{addr}' does not conform to valid blockchain format. "
            "Please verify the wallet address provided in the FIR / complaint."
        ),
        BoundaryCode.UNSUPPORTED_CHAIN: (
            "Requested blockchain is not supported by the current tracer version. "
            "Supported blockchain: TRON."
        ),
        BoundaryCode.UNSUPPORTED_ASSET: (
            "Requested asset is not supported by the current tracer version. "
            "Supported asset: TRC-20 USDT."
        ),
        BoundaryCode.PROVIDER_TIMEOUT: (
            f"Blockchain provider timed out while querying address {addr} at hop {hop}. "
            "Upstream network service was unresponsive after bounded retries. "
            "Partial transaction graph and collected evidence have been preserved."
        ),
        BoundaryCode.PROVIDER_RATE_LIMITED: (
            f"Blockchain provider rate limit (HTTP 429) encountered at hop {hop}. "
            "Traversal paused to prevent data corruption. Partial graph preserved."
        ),
        BoundaryCode.NO_TRANSFERS_FOUND: (
            f"No outgoing transactions found for wallet {addr}. "
            "The wallet appears inactive or has no recorded on-chain activity for the target asset."
        ),
        BoundaryCode.NO_RELEVANT_PATH: (
            f"All observed outgoing transfers from {addr} were pruned due to relevance filtering "
            "(below minimum threshold or asset mismatch). No significant downstream paths remain."
        ),
        BoundaryCode.MAX_HOPS_REACHED: (
            f"Traversal completed up to the configured maximum depth limit ({limit or hop} hops). "
            "Further downstream transactions were not expanded to maintain investigation scope."
        ),
        BoundaryCode.MAX_NODES_REACHED: (
            f"Graph safety limit reached ({limit or 'node threshold'}). Traversal halted to prevent "
            "combinatorial explosion. Partial multi-hop path preserved."
        ),
        BoundaryCode.MAX_EDGES_REACHED: (
            f"Edge safety bound reached ({limit or 'edge threshold'}). Traversal halted. "
            "Partial multi-hop path preserved."
        ),
        BoundaryCode.MIXER_BOUNDARY: (
            f"Funds entered a High-Risk Obfuscation Service ({entity} at {addr}). "
            "Traversal halted at mixer boundary per forensic anti-de-anonymization policy. "
            "Cryptographic multi-party mixing prevents deterministic on-chain linkability."
        ),
        BoundaryCode.BRIDGE_BOUNDARY: (
            f"Funds deposited into Cross-Chain Bridge Gateway ({entity} at {addr}). "
            "Single-chain TRON traversal terminated. Outbound transfers continue on an external "
            "blockchain (requires dedicated cross-chain correlation adapter)."
        ),
        BoundaryCode.LOW_CONFIDENCE: (
            "Attribution confidence is below the evidentiary threshold. "
            "Destination remains an unhosted or unidentified wallet cluster. No VASP identified."
        ),
        BoundaryCode.REPORT_GENERATION_FAILED: (
            "Failed to compile forensic report PDF due to invalid trace data or formatting failure. "
            "Original investigation graph and evidence items remain intact."
        ),
    }

    return explanations.get(code, f"Operational boundary reached: {code.value}.")
