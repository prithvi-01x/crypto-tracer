import math
from datetime import datetime
from typing import Optional
from backend.app.domain.models import InvestigationGraph
from backend.app.domain.attribution.models import TemporalResult


class TemporalAnalyzer:
    """
    Temporal Delay Analysis Engine.
    Quantifies the automated exchange sweeping pattern: rapid automated consolidation
    following victim deposit vs manual delayed transfers.
    Uses configurable exponential decay: score = exp(-delay_hours / tau).
    """

    def __init__(self, tau_hours: float = 4.0):
        self.tau_hours = max(tau_hours, 0.1)

    def analyze(self, address: str, graph: InvestigationGraph) -> TemporalResult:
        normalized_addr = address.strip()

        # Find earliest incoming deposit timestamp
        incoming_edges = [e for e in graph.edges if e.to_address == normalized_addr]
        outgoing_edges = [e for e in graph.edges if e.from_address == normalized_addr]

        if not incoming_edges:
            return TemporalResult(
                score=0.0,
                explanation="No incoming transfers observed for temporal baseline.",
            )

        earliest_deposit = min(e.timestamp for e in incoming_edges)

        # If no outgoing edges, this is a stationary deposit endpoint
        if not outgoing_edges:
            return TemporalResult(
                deposit_time=earliest_deposit,
                score=0.20,
                explanation=f"Stationary endpoint: Deposit received at {earliest_deposit.strftime('%H:%M:%S UTC')} with no subsequent outgoing sweep.",
            )

        # Earliest outgoing sweep after or at deposit
        sweeps_after_deposit = [e.timestamp for e in outgoing_edges if e.timestamp >= earliest_deposit]
        if sweeps_after_deposit:
            earliest_sweep = min(sweeps_after_deposit)
        else:
            earliest_sweep = min(e.timestamp for e in outgoing_edges)

        delay_seconds = max((earliest_sweep - earliest_deposit).total_seconds(), 0.0)
        delay_hours = delay_seconds / 3600.0

        # Exponential decay scoring
        score = math.exp(-delay_hours / self.tau_hours)
        score = min(max(score, 0.0), 1.0)

        # Format delay for forensic readability
        if delay_seconds < 60:
            formatted = f"{int(delay_seconds)} seconds"
        elif delay_seconds < 3600:
            mins = int(delay_seconds // 60)
            secs = int(delay_seconds % 60)
            formatted = f"{mins}m {secs}s"
        else:
            hours = int(delay_seconds // 3600)
            mins = int((delay_seconds % 3600) // 60)
            formatted = f"{hours}h {mins}m"

        if delay_seconds <= 900:  # <= 15 minutes
            explanation = f"Rapid automated sweep ({formatted} delay, score: {score:.2f}) strongly indicates programmatic exchange deposit forwarding."
        elif delay_seconds <= 3600:  # <= 1 hour
            explanation = f"Automated consolidation delay ({formatted}, score: {score:.2f}) consistent with scheduled exchange batch sweeping."
        elif delay_seconds <= 14400:  # <= 4 hours
            explanation = f"Moderate transfer interval ({formatted}, score: {score:.2f}) between deposit and onward movement."
        else:
            explanation = f"Delayed onward transfer ({formatted}, score: {score:.2f}) suggests manual or high-latency dormancy rather than immediate automated sweeping."

        return TemporalResult(
            deposit_time=earliest_deposit,
            sweep_time=earliest_sweep,
            delay_seconds=round(delay_seconds, 1),
            delay_hours=round(delay_hours, 3),
            delay_formatted=formatted,
            score=round(score, 4),
            explanation=explanation,
        )
