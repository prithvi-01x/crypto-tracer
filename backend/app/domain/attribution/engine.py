from typing import Optional, List, Dict, Any
from backend.app.domain.models import InvestigationGraph
from backend.app.domain.attribution.models import (
    VASPCandidate,
    AttributionReport,
    FactorScores,
    FactorExplanations,
)
from backend.app.domain.attribution.registry import VASPRegistry, default_registry
from backend.app.domain.attribution.sweep import SweepAnalyzer
from backend.app.domain.attribution.fan_in import FanInAnalyzer
from backend.app.domain.attribution.temporal import TemporalAnalyzer


class AttributionEngine:
    """
    Explainable VASP Attribution Engine.
    Combines direct tags, sweep ratios, fan-in convergence, and temporal delay
    into a calibrated, transparent confidence score [0.0 - 1.0].
    
    Adheres strictly to the inferential evidence framework:
    confidence = 0.35 * direct_tag + 0.35 * sweep + 0.15 * fan_in + 0.15 * temporal
    """

    ENGINE_VERSION = "0.1.0"
    DISCLAIMER = (
        "Attribution is an investigative hypothesis based on observable on-chain transaction patterns, "
        "not legal proof of account ownership."
    )

    def __init__(
        self,
        registry: Optional[VASPRegistry] = None,
        tau_hours: float = 4.0,
    ):
        self.registry = registry or default_registry
        self.sweep_analyzer = SweepAnalyzer(self.registry)
        self.fan_in_analyzer = FanInAnalyzer()
        self.temporal_analyzer = TemporalAnalyzer(tau_hours=tau_hours)

    def evaluate_trace(
        self,
        trace_id: str,
        graph: InvestigationGraph,
    ) -> AttributionReport:
        """
        Evaluate all candidate nodes in an investigation graph and score VASP attribution.
        """
        candidates: List[VASPCandidate] = []

        # Find candidate nodes to evaluate:
        # 1. Non-suspect nodes that received funds (intermediates and endpoints)
        # 2. Any nodes that directly match a known VASP
        candidate_addresses = set()
        for node in graph.nodes:
            if node.node_type != "suspect" and node.total_received > 0:
                candidate_addresses.add(node.address)
            elif self.registry.is_known_vasp(node.address):
                candidate_addresses.add(node.address)

        for addr in candidate_addresses:
            candidate = self._score_candidate(addr, graph)
            if candidate:
                candidates.append(candidate)

        # Sort candidates by composite confidence score descending
        candidates.sort(key=lambda c: (c.confidence, c.factors.direct_tag, c.factors.sweep), reverse=True)

        best = candidates[0] if candidates else None

        meta = {
            "total_candidates_evaluated": len(candidate_addresses),
            "retained_candidates_count": len(candidates),
            "algorithm": "0.35*tag + 0.35*sweep + 0.15*fan_in + 0.15*temporal",
            "registry_version": self.registry.VERSION,
        }

        return AttributionReport(
            trace_id=trace_id,
            engine_version=self.ENGINE_VERSION,
            disclaimer=self.DISCLAIMER,
            candidates=candidates,
            best_candidate=best,
            meta=meta,
        )

    def _score_candidate(self, address: str, graph: InvestigationGraph) -> Optional[VASPCandidate]:
        normalized_addr = address.strip()

        # 1. Direct Tag Analysis
        direct_entry = self.registry.get(normalized_addr)

        # 2. Sweep Analysis
        sweep_res = self.sweep_analyzer.analyze(normalized_addr, graph)

        # 3. Destination Entity Tag (if this address swept into a known VASP hot wallet)
        dest_entry = self.registry.get(sweep_res.dominant_destination) if sweep_res.dominant_destination else None

        # Determine attributed entity and direct tag score
        if direct_entry:
            vasp_id = direct_entry.vasp_id
            vasp_name = direct_entry.entity_name
            verification_status = direct_entry.verification_status
            if verification_status == "VERIFIED":
                direct_tag_score = 1.0
                tag_explanation = f"Direct tag match: Wallet is a verified {direct_entry.address_type} belonging to {vasp_name} (Source: {direct_entry.source})."
            else:
                direct_tag_score = 0.60
                tag_explanation = f"Heuristic tag match: Wallet has an unverified/community tag associated with {vasp_name}."
        elif dest_entry and sweep_res.is_sweep:
            # Intermediate deposit address sweeping into verified exchange hot wallet
            vasp_id = dest_entry.vasp_id
            vasp_name = dest_entry.entity_name
            verification_status = dest_entry.verification_status
            if verification_status == "VERIFIED":
                direct_tag_score = 0.95
                tag_explanation = f"Downstream consolidation match: Wallet sweeps funds directly into verified {vasp_name} hot wallet ({dest_entry.address[:8]}...)."
            else:
                direct_tag_score = 0.50
                tag_explanation = f"Downstream heuristic match: Wallet sweeps into an unverified {vasp_name} candidate address."
        else:
            vasp_id = "unknown_entity"
            vasp_name = "Unknown Service / Unidentified VASP"
            verification_status = "UNVERIFIED"
            direct_tag_score = 0.0
            tag_explanation = "No direct registry tag or verified destination match found in current intelligence database."

        # 4. Fan-In Analysis (evaluate on the destination hot wallet if sweeping, else on the candidate itself)
        eval_fan_in_addr = sweep_res.dominant_destination if (dest_entry and sweep_res.is_sweep) else normalized_addr
        fan_in_res = self.fan_in_analyzer.analyze(eval_fan_in_addr, graph)

        # 5. Temporal Delay Analysis
        temporal_res = self.temporal_analyzer.analyze(normalized_addr, graph)

        # 6. Composite Confidence Calculation
        # CS = 0.35 * direct_tag + 0.35 * sweep + 0.15 * fan_in + 0.15 * temporal
        confidence_raw = (
            0.35 * direct_tag_score +
            0.35 * sweep_res.score +
            0.15 * fan_in_res.score +
            0.15 * temporal_res.score
        )
        confidence = min(max(confidence_raw, 0.0), 1.0)
        confidence_pct = round(confidence * 100.0, 1)

        # 7. Confidence Band Assignment
        if confidence >= 0.90:
            band = "VERY HIGH"
        elif confidence >= 0.75:
            band = "HIGH"
        elif confidence >= 0.50:
            band = "MODERATE"
        else:
            band = "LOW"

        # 8. Standardized Hypothesis Wording (Never claim "definitely")
        hypothesis_label = f"Likely VASP: {vasp_name} (Evidence-backed attribution hypothesis)"

        # 9. Evidence Bullet Points for UI/Dossier
        evidence_points: List[str] = []
        if direct_tag_score >= 0.50:
            evidence_points.append(f"✓ Direct tag evidence: {tag_explanation}")
        if sweep_res.score >= 0.70:
            evidence_points.append(f"✓ Sweep consolidation: {sweep_res.explanation}")
        if fan_in_res.score >= 0.60:
            evidence_points.append(f"✓ Multi-sender fan-in: {fan_in_res.explanation}")
        if temporal_res.score >= 0.60:
            evidence_points.append(f"✓ Programmatic temporal signal: {temporal_res.explanation}")

        if not evidence_points:
            evidence_points.append(f"• Weak attribution signals: Insufficient patterns to strongly attribute to a known VASP.")

        return VASPCandidate(
            candidate_address=normalized_addr,
            vasp_id=vasp_id,
            vasp_name=vasp_name,
            hypothesis_label=hypothesis_label,
            confidence=round(confidence, 4),
            confidence_percentage=confidence_pct,
            confidence_band=band,
            verification_status=verification_status,
            factors=FactorScores(
                direct_tag=round(direct_tag_score, 4),
                sweep=round(sweep_res.score, 4),
                fan_in=round(fan_in_res.score, 4),
                temporal=round(temporal_res.score, 4),
            ),
            explanations=FactorExplanations(
                direct_tag=tag_explanation,
                sweep=sweep_res.explanation,
                fan_in=fan_in_res.explanation,
                temporal=temporal_res.explanation,
            ),
            evidence_bullet_points=evidence_points,
            sweep_details=sweep_res,
            fan_in_details=fan_in_res,
            temporal_details=temporal_res,
        )
