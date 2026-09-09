from typing import Set, List
from backend.app.domain.models import InvestigationGraph
from backend.app.domain.attribution.models import FanInResult


class FanInAnalyzer:
    """
    Fan-In Analysis Engine.
    Quantifies multi-source consolidation into an omnibus address by counting
    distinct sender addresses converging on a target candidate wallet.
    """

    def __init__(self, high_fan_in_threshold: int = 3):
        self.high_fan_in_threshold = high_fan_in_threshold

    def analyze(self, address: str, graph: InvestigationGraph) -> FanInResult:
        normalized_addr = address.strip()

        # Find all distinct upstream senders that directed funds to this address
        senders: Set[str] = {
            e.from_address
            for e in graph.edges
            if e.to_address == normalized_addr and e.from_address != normalized_addr
        }

        distinct_count = len(senders)
        is_high_fan_in = (distinct_count >= self.high_fan_in_threshold)

        # Normalized scoring
        if distinct_count >= 5:
            score = 1.0
            explanation = f"High fan-in consolidation ({distinct_count} distinct deposit senders) converging into this omnibus wallet."
        elif distinct_count >= 3:
            score = 0.85
            explanation = f"Moderate-high fan-in ({distinct_count} distinct senders) consistent with multi-user deposit aggregation."
        elif distinct_count == 2:
            score = 0.60
            explanation = f"Dual-source consolidation (2 distinct senders) observed."
        elif distinct_count == 1:
            score = 0.30
            explanation = f"Single-source transfer (1 sender) observed in current traversal slice."
        else:
            score = 0.0
            explanation = f"No incoming senders observed for this node."

        return FanInResult(
            distinct_senders_count=distinct_count,
            senders=sorted(list(senders)),
            is_high_fan_in=is_high_fan_in,
            score=round(score, 4),
            explanation=explanation,
        )
