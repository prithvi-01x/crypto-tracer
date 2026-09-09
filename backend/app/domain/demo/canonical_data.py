from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Any

from backend.app.adapters.base import BlockchainProvider
from backend.app.domain.models import Transfer, TransferPage


# ============================================================================
# CANONICAL SIH 2026 DEMO SPECIFICATION
# FIR: FIR-2026-DEL-CY-0812
# Scenario: 4-Hop TRC-20 USDT Layering into Verified Binance Deposit Node
# ============================================================================

CANONICAL_CASE_ID = "00000000-0000-0000-0000-000000000812"
CANONICAL_FIR = "FIR-2026-DEL-CY-0812"
CANONICAL_VICTIM = "Ramesh Kumar (Telegram Task-Based Investment Scam)"
CANONICAL_LOSS_INR = Decimal("5000000.00")
CANONICAL_ACK = "1930-DEL-2026-0812"
CANONICAL_CHAIN = "TRON"
CANONICAL_ASSET = "TRC20:USDT"
CANONICAL_NOTES = (
    "Victim defrauded via task-based cryptocurrency investment group. "
    "Primary suspect unhosted wallet funneled funds through multi-tier mule accounts, "
    "consolidated into an omnibus deposit node, and swept into a verified Binance hot wallet."
)

# 34-Character Deterministic Addresses
ADDR_SUSPECT_ROOT = "TSuspectScamRootWallet111111111111"
ADDR_HOP1_LAYERING = "TLayeringIntermediaryHop1111111111"
ADDR_HOP1_MULE_ALT = "TMuleAlternateAccountHop1111111111"
ADDR_HOP1_DUST = "TDustSpamAccountHop10000000000000"

ADDR_HOP2_CONSOLIDATION = "TMuleConsolidationHop2222222222222"
ADDR_HOP2_EXPENSES = "TOperationalExpensesHop22222222222"
ADDR_HOP2_DUST = "TDustMicroRefundHop22222222222222"
ADDR_HOP2_CASHOUT_P2P = "TCashoutP2PTraderHop22222222222222"

ADDR_HOP3_CANDIDATE = "TBinanceUserDepositCandidate333333"
ADDR_HOP3_BROKER_FEE = "TOtcBrokerCommissionHop33333333333"

# Verified Binance Hot Wallet 4 from VASP Registry
ADDR_HOP4_BINANCE_HOT = "TMuA6YqfCeX8EhbfYEg5y7S4Dqz9Dw92eP"

USDT_CONTRACT = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"


def _create_transfer(
    tx_hash: str,
    from_addr: str,
    to_addr: str,
    amount_usdt: float,
    ts: datetime,
    block_num: int = 59124010,
) -> Transfer:
    amount_dec = Decimal(str(amount_usdt))
    amount_raw = int(amount_dec * 1_000_000)
    return Transfer(
        chain=CANONICAL_CHAIN,
        tx_hash=tx_hash,
        block_number=block_num,
        timestamp=ts,
        from_address=from_addr,
        to_address=to_addr,
        asset_contract=USDT_CONTRACT,
        asset_symbol="USDT",
        amount_raw=amount_raw,
        amount_decimal=amount_dec,
        source="demo_fixture",
    )


def build_canonical_demo_fixtures(base_time: Optional[datetime] = None) -> Dict[str, List[Transfer]]:
    """
    Build the complete, deterministic 4-hop transaction graph fixture for the SIH demo.
    All timestamps are chronologically sequenced with realistic inter-hop delays.
    Includes dust noise (< $1.00) to demonstrate forensic relevance pruning.
    Includes a strong 99.78% sweep with a 14-minute delay to produce explainable Binance attribution.
    """
    t0 = base_time or datetime(2026, 3, 9, 14, 0, 0, tzinfo=timezone.utc)

    # 1. Hop 0 (Suspect Root Wallet) Outgoing
    suspect_txs = [
        # Main theft branch: 50,000 USDT -> Hop 1 Layering
        _create_transfer(
            tx_hash="0a1b2c3d4e5f60718293a4b5c6d7e8f90123456789abcdef0123456789abcdef",
            from_addr=ADDR_SUSPECT_ROOT,
            to_addr=ADDR_HOP1_LAYERING,
            amount_usdt=50000.00,
            ts=t0 + timedelta(minutes=2, seconds=15),
            block_num=59124010,
        ),
        # Secondary mule split: 9,998 USDT -> Hop 1 Alt
        _create_transfer(
            tx_hash="1b2c3d4e5f60718293a4b5c6d7e8f90123456789abcdef0123456789abcdef01",
            from_addr=ADDR_SUSPECT_ROOT,
            to_addr=ADDR_HOP1_MULE_ALT,
            amount_usdt=9998.00,
            ts=t0 + timedelta(minutes=5, seconds=40),
            block_num=59124018,
        ),
        # Dust transaction: 0.50 USDT (Noise Pruned by Relevance Filter)
        _create_transfer(
            tx_hash="2c3d4e5f60718293a4b5c6d7e8f90123456789abcdef0123456789abcdef012a",
            from_addr=ADDR_SUSPECT_ROOT,
            to_addr=ADDR_HOP1_DUST,
            amount_usdt=0.50,
            ts=t0 + timedelta(minutes=1, seconds=10),
            block_num=59124005,
        ),
    ]

    # 2. Hop 1 (Layering Intermediary) Outgoing
    hop1_layering_txs = [
        # Forward to Hop 2 Consolidation: 49,850 USDT
        _create_transfer(
            tx_hash="3d4e5f60718293a4b5c6d7e8f90123456789abcdef0123456789abcdef01234b",
            from_addr=ADDR_HOP1_LAYERING,
            to_addr=ADDR_HOP2_CONSOLIDATION,
            amount_usdt=49850.00,
            ts=t0 + timedelta(minutes=18, seconds=22),
            block_num=59124050,
        ),
        # Operational / fee leak: 150 USDT
        _create_transfer(
            tx_hash="4e5f60718293a4b5c6d7e8f90123456789abcdef0123456789abcdef0123456c",
            from_addr=ADDR_HOP1_LAYERING,
            to_addr=ADDR_HOP2_EXPENSES,
            amount_usdt=150.00,
            ts=t0 + timedelta(minutes=20, seconds=10),
            block_num=59124055,
        ),
        # Dust transaction: 0.85 USDT (Noise Pruned by Relevance Filter)
        _create_transfer(
            tx_hash="5f60718293a4b5c6d7e8f90123456789abcdef0123456789abcdef012345678d",
            from_addr=ADDR_HOP1_LAYERING,
            to_addr=ADDR_HOP2_DUST,
            amount_usdt=0.85,
            ts=t0 + timedelta(minutes=19, seconds=0),
            block_num=59124052,
        ),
    ]

    # 3. Hop 1 Alternate Mule Outgoing
    hop1_alt_txs = [
        _create_transfer(
            tx_hash="60718293a4b5c6d7e8f90123456789abcdef0123456789abcdef01234567890e",
            from_addr=ADDR_HOP1_MULE_ALT,
            to_addr=ADDR_HOP2_CASHOUT_P2P,
            amount_usdt=9950.00,
            ts=t0 + timedelta(minutes=25, seconds=0),
            block_num=59124070,
        ),
    ]

    # 4. Hop 2 (Mule Consolidation) Outgoing
    hop2_consolidation_txs = [
        # Consolidation to Deposit Candidate: 62,100 USDT
        _create_transfer(
            tx_hash="718293a4b5c6d7e8f90123456789abcdef0123456789abcdef0123456789012f",
            from_addr=ADDR_HOP2_CONSOLIDATION,
            to_addr=ADDR_HOP3_CANDIDATE,
            amount_usdt=62100.00,
            ts=t0 + timedelta(minutes=45, seconds=10),
            block_num=59124120,
        ),
        # OTC commission: 250 USDT
        _create_transfer(
            tx_hash="8293a4b5c6d7e8f90123456789abcdef0123456789abcdef012345678901234a",
            from_addr=ADDR_HOP2_CONSOLIDATION,
            to_addr=ADDR_HOP3_BROKER_FEE,
            amount_usdt=250.00,
            ts=t0 + timedelta(minutes=46, seconds=0),
            block_num=59124125,
        ),
    ]

    # 5. Hop 3 (Deposit Candidate) Outgoing
    # Note: received 62,100 USDT at t0 + 45m10s
    # Sweeps 61,980 USDT to Binance Hot Wallet 4 at t0 + 59m12s (14m 02s delay, 99.8% sweep!)
    hop3_candidate_txs = [
        _create_transfer(
            tx_hash="93a4b5c6d7e8f90123456789abcdef0123456789abcdef01234567890123456b",
            from_addr=ADDR_HOP3_CANDIDATE,
            to_addr=ADDR_HOP4_BINANCE_HOT,
            amount_usdt=61980.00,
            ts=t0 + timedelta(minutes=59, seconds=12),
            block_num=59124160,
        ),
    ]

    return {
        ADDR_SUSPECT_ROOT: suspect_txs,
        ADDR_HOP1_LAYERING: hop1_layering_txs,
        ADDR_HOP1_MULE_ALT: hop1_alt_txs,
        ADDR_HOP1_DUST: [],
        ADDR_HOP2_CONSOLIDATION: hop2_consolidation_txs,
        ADDR_HOP2_EXPENSES: [],
        ADDR_HOP2_DUST: [],
        ADDR_HOP2_CASHOUT_P2P: [],
        ADDR_HOP3_CANDIDATE: hop3_candidate_txs,
        ADDR_HOP3_BROKER_FEE: [],
        ADDR_HOP4_BINANCE_HOT: [],
    }


class DemoFixtureProvider(BlockchainProvider):
    """
    Deterministic, zero-network BlockchainProvider for the canonical SIH 2026 demo.
    Guarantees sub-millisecond execution, complete resilience against internet/API failures,
    and absolute reproducibility for judge presentations.
    """

    def __init__(self, fixtures: Optional[Dict[str, List[Transfer]]] = None):
        self.fixtures = fixtures or build_canonical_demo_fixtures()

    async def get_transfers(
        self,
        address: str,
        asset_contract: Optional[str] = None,
        cursor: Optional[str] = None,
        limit: int = 20,
        direction: Optional[str] = None,
    ) -> TransferPage:
        clean_addr = address.strip()
        txs = self.fixtures.get(clean_addr, [])

        # Filter by direction if requested
        if direction == "outgoing":
            filtered = [t for t in txs if t.from_address == clean_addr]
        elif direction == "incoming":
            filtered = [t for t in txs if t.to_address == clean_addr]
        else:
            filtered = txs

        # Pagination simulation
        start_idx = int(cursor) if cursor and cursor.isdigit() else 0
        end_idx = start_idx + limit
        page_items = filtered[start_idx:end_idx]
        next_cursor = str(end_idx) if end_idx < len(filtered) else None

        return TransferPage(
            transfers=page_items,
            next_cursor=next_cursor,
            has_more=next_cursor is not None,
            cached=True,
            total_fetched=len(page_items),
        )


def is_canonical_demo_address(address: str) -> bool:
    """Check if address belongs to the canonical SIH demo dataset."""
    canonical_addresses = {
        ADDR_SUSPECT_ROOT,
        ADDR_HOP1_LAYERING,
        ADDR_HOP1_MULE_ALT,
        ADDR_HOP2_CONSOLIDATION,
        ADDR_HOP3_CANDIDATE,
        ADDR_HOP4_BINANCE_HOT,
    }
    return address.strip() in canonical_addresses
