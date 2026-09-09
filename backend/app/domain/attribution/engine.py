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
    
    Enforces strict forensic boundaries:
    - Never claims mixer de-anonymization.
    - Never fabricates a VASP when confidence is insufficient.
    - Accurately halts at cross-chain bridge gateways.
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
        # Boundary Check: Graph has 0 edges (No transfers found or all pruned)
        if len(graph.edges) == 0:
            boundary_code = graph.meta.get("boundary_reached") or "NO_TRANSFERS_FOUND"
            return AttributionReport(
                trace_id=trace_id,
                engine_version=self.ENGINE_VERSION,
                disclaimer=self.DISCLAIMER,
                candidates=[],
                best_candidate=None,
                meta={
                    "total_candidates_evaluated": 0,
                    "retained_candidates_count": 0,
                    "attribution_status": boundary_code,
                    "explanation": "No on-chain transaction edges available to evaluate VASP attribution.",
                    "registry_version": self.registry.VERSION,
                },
            )

        candidates: List[VASPCandidate] = []

        # Find candidate nodes to evaluate:
        # 1. Non-suspect nodes that received funds (intermediates and endpoints)
        # 2. Any nodes that directly match a known VASP, mixer, or bridge in the registry
        candidate_addresses = set()
        for node in graph.nodes:
            if node.node_type != "suspect" and node.total_received > 0:
                candidate_addresses.add(node.address)
            elif self.registry.get(node.address) is not None:
                candidate_addresses.add(node.address)

        for addr in candidate_addresses:
            candidate = self._score_candidate(addr, graph)
            if candidate:
                candidates.append(candidate)

        # Sort candidates by composite confidence score descending
        candidates.sort(key=lambda c: (c.confidence, c.factors.direct_tag, c.factors.sweep), reverse=True)

        best = candidates[0] if candidates else None

        # Attribution status classification
        if not best or (best.confidence < 0.40 and best.vasp_id == "unidentified"):
            attribution_status = "LOW_CONFIDENCE"
            explanation = "Attribution confidence is insufficient to identify a responsible VASP entity."
        elif best.entity_category == "mixer":
            attribution_status = "MIXER_BOUNDARY"
            explanation = (
                "Funds routed into a high-risk obfuscation service (Mixer). "
                "Cryptographic mixing prevents deterministic on-chain linkability. De-anonymization cannot be claimed."
            )
        elif best.entity_category == "bridge":
            attribution_status = "BRIDGE_BOUNDARY"
            explanation = "Funds deposited into a Cross-Chain Bridge gateway. Outbound transfers continue on an external blockchain."
        else:
            attribution_status = "IDENTIFIED"
            explanation = f"Forensic analysis established accepted attribution hypothesis for {best.vasp_name}."

        meta = {
            "total_candidates_evaluated": len(candidate_addresses),
            "retained_candidates_count": len(candidates),
            "algorithm": "0.35*effective_tag(direct|0.80*downstream) + 0.35*sweep + 0.15*fan_in + 0.15*temporal",
            "registry_version": self.registry.VERSION,
            "attribution_status": attribution_status,
            "explanation": explanation,
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

        # 1. Direct Tag Analysis (strictly for candidate address itself)
        direct_entry = self.registry.get(normalized_addr)
        is_directly_tagged = direct_entry is not None

        # 2. Pure Behavioral Sweep Analysis (consolidation mechanics)
        sweep_res = self.sweep_analyzer.analyze(normalized_addr, graph)

        # 3. Downstream VASP Match Analysis (separate from direct tag)
        dest_entry = self.registry.get(sweep_res.dominant_destination) if sweep_res.dominant_destination else None

        entity_category = "vasp"
        is_low_confidence = False

        if is_directly_tagged:
            if direct_entry.address_type == "mixer":
                vasp_id = "mixer"
                vasp_name = direct_entry.entity_name
                entity_category = "mixer"
                verification_status = direct_entry.verification_status
                direct_tag_score = 1.0
                tag_explanation = (
                    f"Mixer Boundary: Address is identified as {direct_entry.entity_name}. "
                    "Cryptographic multi-party mixing prevents deterministic on-chain linkability. "
                    "De-anonymization cannot be claimed from public on-chain ledgers."
                )
                hypothesis_label = f"High-Risk Obfuscation: {vasp_name} (Mixer Boundary)"
            elif direct_entry.address_type == "bridge":
                vasp_id = "bridge"
                vasp_name = direct_entry.entity_name
                entity_category = "bridge"
                verification_status = direct_entry.verification_status
                direct_tag_score = 1.0
                tag_explanation = (
                    f"Cross-Chain Bridge: Address is identified as {direct_entry.entity_name}. "
                    "Single-chain TRON traversal terminates at cross-chain bridge gateway."
                )
                hypothesis_label = f"Cross-Chain Bridge: {vasp_name} (Cross-Chain Boundary)"
            else:
                vasp_id = direct_entry.vasp_id
                vasp_name = direct_entry.entity_name
                verification_status = direct_entry.verification_status
                if verification_status == "VERIFIED":
                    direct_tag_score = 1.0
                    tag_explanation = f"Direct tag match: Wallet is a verified {direct_entry.address_type} belonging to {vasp_name} (Source: {direct_entry.source})."
                else:
                    direct_tag_score = 0.60
                    tag_explanation = f"Heuristic tag match: Wallet has an unverified/community tag associated with {vasp_name}."
                hypothesis_label = f"Likely VASP: {vasp_name} (Evidence-backed attribution hypothesis)"
            downstream_vasp_match = 0.0
            downstream_explanation = "N/A: Candidate address is directly tagged."
        elif dest_entry:
            if dest_entry.address_type == "mixer":
                vasp_id = "mixer"
                vasp_name = dest_entry.entity_name
                entity_category = "mixer"
                verification_status = dest_entry.verification_status
                direct_tag_score = 0.0
                tag_explanation = "This candidate is not directly tagged in the VASP registry."
                downstream_vasp_match = 1.0
                downstream_explanation = f"Candidate sweeps funds into High-Risk Obfuscation Service ({dest_entry.entity_name}). Traversal terminates at mixer boundary."
                hypothesis_label = f"High-Risk Obfuscation: {vasp_name} (Mixer Boundary)"
            elif dest_entry.address_type == "bridge":
                vasp_id = "bridge"
                vasp_name = dest_entry.entity_name
                entity_category = "bridge"
                verification_status = dest_entry.verification_status
                direct_tag_score = 0.0
                tag_explanation = "This candidate is not directly tagged in the VASP registry."
                downstream_vasp_match = 1.0
                downstream_explanation = f"Candidate routes funds into Cross-Chain Bridge Gateway ({dest_entry.entity_name})."
                hypothesis_label = f"Cross-Chain Bridge: {vasp_name} (Cross-Chain Boundary)"
            else:
                vasp_id = dest_entry.vasp_id
                vasp_name = dest_entry.entity_name
                verification_status = dest_entry.verification_status
                direct_tag_score = 0.0
                tag_explanation = "This candidate is not directly tagged in the VASP registry."
                if verification_status == "VERIFIED":
                    downstream_vasp_match = 1.0
                    downstream_explanation = f"This candidate is not directly tagged; its funds sweep into a verified {vasp_name} wallet."
                else:
                    downstream_vasp_match = 0.50
                    downstream_explanation = f"This candidate is not directly tagged; its funds flow toward a candidate {vasp_name} address with heuristic status."
                hypothesis_label = f"Likely VASP: {vasp_name} (Evidence-backed attribution hypothesis)"
        else:
            vasp_id = "unknown_entity"
            vasp_name = "Unidentified / Unhosted Wallet"
            entity_category = "unidentified"
            verification_status = "UNVERIFIED"
            direct_tag_score = 0.0
            tag_explanation = "This candidate is not directly tagged in the VASP registry."
            downstream_vasp_match = 0.0
            downstream_explanation = "No downstream consolidation into a known VASP identified."
            hypothesis_label = "Unidentified Unhosted Wallet (Insufficient attribution evidence)"

        # 4. Fan-In Analysis (evaluate on destination hot wallet if sweeping, else candidate itself)
        eval_fan_in_addr = sweep_res.dominant_destination if (dest_entry and sweep_res.is_sweep) else normalized_addr
        fan_in_res = self.fan_in_analyzer.analyze(eval_fan_in_addr, graph)

        # 5. Temporal Delay Analysis
        temporal_res = self.temporal_analyzer.analyze(normalized_addr, graph)

        # 6. Composite Confidence Calculation
        if is_directly_tagged:
            effective_entity_tag = direct_tag_score
        else:
            effective_entity_tag = 0.80 * downstream_vasp_match

        confidence_raw = (
            0.35 * effective_entity_tag +
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

        # 8. Anti-Fabrication Rule for Low Confidence / Unidentified Wallets
        if band == "LOW" and entity_category not in ("mixer", "bridge") and not (is_directly_tagged and direct_tag_score >= 0.50):
            vasp_id = "unknown_entity"
            vasp_name = "Unidentified / Unhosted Wallet"
            entity_category = "unidentified"
            hypothesis_label = "Unidentified Unhosted Wallet (Insufficient attribution evidence)"
            is_low_confidence = True

        # 9. Evidence Bullet Points for UI/Dossier
        evidence_points: List[str] = []
        if entity_category == "mixer":
            evidence_points.append("⚠️ Mixer Boundary: High-risk obfuscation service encountered. Cryptographic mixing halts deterministic tracing. Never claim mixer de-anonymization.")
        elif entity_category == "bridge":
            evidence_points.append(f"✓ Cross-Chain Gateway: Funds deposited into {vasp_name}. External cross-chain correlation adapter required.")
        else:
            if is_directly_tagged and direct_tag_score >= 0.50:
                evidence_points.append(f"✓ Direct tag evidence: {tag_explanation}")
            elif downstream_vasp_match >= 0.50:
                evidence_points.append(f"✓ Downstream VASP match: {downstream_explanation}")

            if sweep_res.score >= 0.70:
                evidence_points.append(f"✓ Sweep consolidation: {sweep_res.explanation}")
            if fan_in_res.score >= 0.60:
                evidence_points.append(f"✓ Multi-sender fan-in: {fan_in_res.explanation}")
            if temporal_res.score >= 0.60:
                evidence_points.append(f"✓ Programmatic temporal signal: {temporal_res.explanation}")

            if not evidence_points or is_low_confidence:
                evidence_points = ["• Weak attribution signals: Insufficient patterns to attribute to a known VASP. Destination remains an unhosted wallet."]

        return VASPCandidate(
            candidate_address=normalized_addr,
            vasp_id=vasp_id,
            vasp_name=vasp_name,
            hypothesis_label=hypothesis_label,
            confidence=round(confidence, 4),
            confidence_percentage=confidence_pct,
            confidence_band=band,
            verification_status=verification_status,
            entity_category=entity_category,
            is_low_confidence=is_low_confidence,
            factors=FactorScores(
                direct_tag=round(direct_tag_score, 4),
                downstream_vasp_match=round(downstream_vasp_match, 4),
                sweep=round(sweep_res.score, 4),
                fan_in=round(fan_in_res.score, 4),
                temporal=round(temporal_res.score, 4),
            ),
            explanations=FactorExplanations(
                direct_tag=tag_explanation,
                downstream_vasp_match=downstream_explanation,
                sweep=sweep_res.explanation,
                fan_in=fan_in_res.explanation,
                temporal=temporal_res.explanation,
            ),
            evidence_bullet_points=evidence_points,
            sweep_details=sweep_res,
            fan_in_details=fan_in_res,
            temporal_details=temporal_res,
        )
