from decimal import Decimal
from typing import Optional, Dict
from collections import defaultdict

from backend.app.domain.models import InvestigationGraph, GraphEdge
from backend.app.domain.attribution.models import SweepResult
from backend.app.domain.attribution.registry import VASPRegistry


class SweepAnalyzer:
    """
    Forensic Sweep Analyzer.
    Detects high-ratio fund consolidation from intermediate deposit addresses
    into centralized omnibus exchange hot wallets.
    """

    def __init__(
        self,
        registry: VASPRegistry,
        strong_sweep_threshold: float = 0.90,
        moderate_sweep_threshold: float = 0.70,
    ):
        self.registry = registry
        self.strong_sweep_threshold = strong_sweep_threshold
        self.moderate_sweep_threshold = moderate_sweep_threshold

    def analyze(self, address: str, graph: InvestigationGraph) -> SweepResult:
        normalized_addr = address.strip()

        # 1. Sum incoming relevant funds
        incoming_edges = [e for e in graph.edges if e.to_address == normalized_addr]
        received_usdt = sum((e.amount for e in incoming_edges), Decimal("0"))

        # 2. Sum outgoing transfers and group by destination
        outgoing_edges = [e for e in graph.edges if e.from_address == normalized_addr]
        swept_usdt = sum((e.amount for e in outgoing_edges), Decimal("0"))

        dest_aggregates: Dict[str, Decimal] = defaultdict(Decimal)
        for e in outgoing_edges:
            dest_aggregates[e.to_address] += e.amount

        # 3. Compute sweep ratio
        if received_usdt > Decimal("0"):
            sweep_ratio_raw = float(swept_usdt / received_usdt)
            sweep_ratio = min(max(sweep_ratio_raw, 0.0), 1.0)
        else:
            # If no incoming edges in current graph slice (e.g. root suspect itself or direct endpoint)
            sweep_ratio = 0.0

        # 4. Identify dominant destination
        dominant_dest: Optional[str] = None
        dominant_ratio: float = 1.0
        destination_entity: Optional[str] = None
        destination_verified = False

        if dest_aggregates:
            dominant_dest = max(dest_aggregates.keys(), key=lambda k: dest_aggregates[k])
            if swept_usdt > Decimal("0"):
                dominant_ratio = float(dest_aggregates[dominant_dest] / swept_usdt)
            vasp = self.registry.get(dominant_dest)
            if vasp:
                destination_entity = vasp.entity_name
                destination_verified = (vasp.verification_status == "VERIFIED")

        is_sweep = (sweep_ratio >= self.moderate_sweep_threshold)
        is_strong_sweep = (sweep_ratio >= self.strong_sweep_threshold)

        # 5. Pure behavioral sweep mechanics scoring (independent of destination entity to prevent double counting)
        if is_strong_sweep and dominant_ratio >= 0.85:
            score = 1.0
            explanation = (
                f"Strong sweep consolidation ({sweep_ratio * 100:.1f}%): Swept {swept_usdt:.2f} of "
                f"{received_usdt:.2f} USDT into dominant destination ({dominant_ratio * 100:.1f}% concentration)."
            )
        elif is_strong_sweep:
            score = 0.88 * dominant_ratio
            explanation = (
                f"Strong sweep behavior ({sweep_ratio * 100:.1f}%): Swept {swept_usdt:.2f} of "
                f"{received_usdt:.2f} USDT across destinations ({dominant_ratio * 100:.1f}% to dominant)."
            )
        elif is_sweep:
            score = (0.70 + (sweep_ratio - self.moderate_sweep_threshold) * 0.75) * dominant_ratio
            score = min(max(score, 0.0), 0.85)
            explanation = (
                f"Moderate sweep behavior ({sweep_ratio * 100:.1f}%): Partial consolidation of "
                f"{swept_usdt:.2f} USDT observed ({dominant_ratio * 100:.1f}% to dominant destination)."
            )
        elif sweep_ratio > 0.10:
            score = sweep_ratio * 0.50 * dominant_ratio
            explanation = (
                f"Weak sweep behavior ({sweep_ratio * 100:.1f}%): Majority of funds retained or disbursed elsewhere."
            )
        else:
            score = 0.0
            explanation = (
                f"No sweep observed ({sweep_ratio * 100:.1f}%): Wallet retains received funds or has no outgoing edges."
            )

        return SweepResult(
            sweep_ratio=round(sweep_ratio, 4),
            dominant_ratio=round(dominant_ratio, 4),
            received_usdt=received_usdt,
            swept_usdt=swept_usdt,
            dominant_destination=dominant_dest,
            destination_entity=destination_entity,
            destination_verified=destination_verified,
            is_sweep=is_sweep,
            is_strong_sweep=is_strong_sweep,
            score=round(score, 4),
            explanation=explanation,
        )
