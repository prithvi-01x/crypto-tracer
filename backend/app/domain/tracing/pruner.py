from decimal import Decimal
from typing import List, Tuple
from backend.app.domain.models import Transfer, PrunedRecord


class RelevancePruner:
    """
    Forensic relevance-aware branch pruner.
    Suppresses low-value noise and unranked fan-out branches while recording
    pruning decisions with exact reasons and thresholds for forensic transparency.
    """

    def __init__(
        self,
        min_relevant_usd: Decimal = Decimal("1.00"),
        max_branches_per_node: int = 20,
        target_asset: str = "USDT",
    ):
        self.min_relevant_usd = Decimal(str(min_relevant_usd))
        self.max_branches_per_node = max_branches_per_node
        self.target_asset = target_asset

    def partition_transfers(
        self,
        transfers: List[Transfer],
        current_hop: int,
    ) -> Tuple[List[Transfer], List[PrunedRecord]]:
        """
        Rank and partition outgoing transfers from a wallet into:
        1. relevant_transfers (to be evaluated for graph expansion)
        2. pruned_records (forensically retained with reason & threshold)
        """
        relevant: List[Transfer] = []
        pruned: List[PrunedRecord] = []

        # Branch ranking: Sort transfers deterministically by value descending, then timestamp, then hash
        sorted_transfers = sorted(
            transfers,
            key=lambda t: (t.amount_decimal, t.timestamp.isoformat(), t.tx_hash),
            reverse=True,
        )

        branch_count = 0
        for tx in sorted_transfers:
            hop_level = current_hop + 1

            # 1. Asset relevance gate
            if tx.asset_symbol.upper() != self.target_asset.upper():
                pruned.append(
                    PrunedRecord(
                        tx_hash=tx.tx_hash,
                        from_address=tx.from_address,
                        to_address=tx.to_address,
                        amount=tx.amount_decimal,
                        asset=f"{tx.chain}:{tx.asset_symbol}",
                        hop=hop_level,
                        reason="ASSET_MISMATCH",
                        threshold=Decimal("0"),
                        timestamp=tx.timestamp,
                        source=tx.source,
                    )
                )
                continue

            # 2. Minimum relevant value gate (Dust filtering: default < $1.00)
            if tx.amount_decimal < self.min_relevant_usd:
                pruned.append(
                    PrunedRecord(
                        tx_hash=tx.tx_hash,
                        from_address=tx.from_address,
                        to_address=tx.to_address,
                        amount=tx.amount_decimal,
                        asset=f"{tx.chain}:{tx.asset_symbol}",
                        hop=hop_level,
                        reason="DUST",
                        threshold=self.min_relevant_usd,
                        timestamp=tx.timestamp,
                        source=tx.source,
                    )
                )
                continue

            # 3. Maximum branch width gate (Noise suppression for high fan-out omnibus addresses)
            if branch_count >= self.max_branches_per_node:
                pruned.append(
                    PrunedRecord(
                        tx_hash=tx.tx_hash,
                        from_address=tx.from_address,
                        to_address=tx.to_address,
                        amount=tx.amount_decimal,
                        asset=f"{tx.chain}:{tx.asset_symbol}",
                        hop=hop_level,
                        reason="BRANCH_LIMIT_EXCEEDED",
                        threshold=Decimal(self.max_branches_per_node),
                        timestamp=tx.timestamp,
                        source=tx.source,
                    )
                )
                continue

            branch_count += 1
            relevant.append(tx)

        return relevant, pruned
