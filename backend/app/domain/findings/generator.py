import hashlib
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any, Set

from backend.app.domain.models import InvestigationGraph, GraphNode, GraphEdge
from backend.app.domain.attribution.models import AttributionReport, VASPCandidate
from backend.app.domain.evidence.models import EvidenceItem, EvidenceType
from backend.app.domain.boundaries import BoundaryCode
from backend.app.domain.findings.models import (
    FindingSeverity,
    FindingType,
    FindingStatus,
    EvidenceReference,
    ForensicFinding,
)


class FindingsGenerator:
    """
    Forensic Findings & Investigative Alerts Engine.
    Deterministically transforms observable transaction graph topologies,
    behavioral heuristics (sweep, fan-in, temporal delay), VASP attribution models,
    and operational boundaries into structured, evidence-linked investigative findings.
    """

    @classmethod
    def generate_findings(
        cls,
        case_id: str,
        trace_id: str,
        graph: InvestigationGraph,
        attribution_report: Optional[AttributionReport] = None,
        evidence_items: Optional[List[EvidenceItem]] = None,
        persisted_reviews: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> List[ForensicFinding]:
        """
        Generate prioritized forensic findings for a trace execution.
        """
        findings: List[ForensicFinding] = []
        seen_finding_keys: Set[str] = set()
        evidence_list = evidence_items or []
        reviews = persisted_reviews or {}
        now = datetime.now(timezone.utc)

        # Helper to find matching evidence items
        def find_evidence_refs(
            address: Optional[str] = None,
            tx_hash: Optional[str] = None,
            types: Optional[List[EvidenceType]] = None,
        ) -> List[EvidenceReference]:
            matched: List[EvidenceReference] = []
            seen_ev_ids: Set[str] = set()

            for ev in evidence_list:
                if ev.id in seen_ev_ids:
                    continue

                type_match = True
                if types is not None:
                    type_match = ev.evidence_type in types

                addr_match = True
                if address is not None:
                    addr_match = (
                        ev.source_reference == address or
                        address[:16] in ev.id or
                        (isinstance(ev.payload, dict) and (
                            ev.payload.get("from_address") == address or
                            ev.payload.get("to_address") == address or
                            ev.payload.get("address") == address or
                            ev.payload.get("candidate_address") == address
                        ))
                    )

                tx_match = True
                if tx_hash is not None:
                    tx_match = (
                        ev.source_reference == tx_hash or
                        (isinstance(ev.payload, dict) and ev.payload.get("tx_hash") == tx_hash)
                    )

                if type_match and (addr_match or tx_match):
                    matched.append(
                        EvidenceReference(
                            id=ev.id,
                            title=ev.title,
                            classification=ev.classification.value if hasattr(ev.classification, "value") else str(ev.classification),
                            content_hash=ev.content_hash,
                            evidence_type=ev.evidence_type.value if hasattr(ev.evidence_type, "value") else str(ev.evidence_type),
                        )
                    )
                    seen_ev_ids.add(ev.id)

            return matched

        # -----------------------------------------------------------------
        # 1. BOUNDARY FINDINGS (Mixers, Bridges, Timeouts, Limits)
        # -----------------------------------------------------------------
        boundary_code = graph.meta.get("boundary_reached")
        boundary_info = graph.boundary or {}

        # 1A. Mixer Encountered
        mixer_nodes = [n for n in graph.nodes if n.node_type == "mixer"]
        if boundary_code == BoundaryCode.MIXER_BOUNDARY.value or mixer_nodes:
            target_addr = mixer_nodes[0].address if mixer_nodes else boundary_info.get("address")
            f_key = f"mixer_{target_addr or 'boundary'}"
            if f_key not in seen_finding_keys:
                seen_finding_keys.add(f_key)
                addr_display = f" at {target_addr}" if target_addr else ""
                desc = (
                    f"Tracing reached an obfuscation service (Mixer){addr_display}. "
                    "Cryptographic mixing prevents deterministic on-chain linkability; "
                    "automated attribution is halted for this branch."
                )
                f_id = cls._make_id(trace_id, FindingType.MIXER_ENCOUNTERED, target_addr)
                findings.append(
                    ForensicFinding(
                        finding_id=f_id,
                        case_id=case_id,
                        trace_id=trace_id,
                        severity=FindingSeverity.HIGH,
                        finding_type=FindingType.MIXER_ENCOUNTERED,
                        title="Mixer Obfuscation Boundary Encountered",
                        description=desc,
                        timestamp=now,
                        source_signal="mixer_boundary_detector",
                        confidence=1.0,
                        related_address=target_addr,
                        evidence_refs=find_evidence_refs(address=target_addr),
                        graph_node_id=target_addr,
                    )
                )

        # 1B. Bridge Encountered
        bridge_nodes = [n for n in graph.nodes if n.node_type == "bridge"]
        if boundary_code == BoundaryCode.BRIDGE_BOUNDARY.value or bridge_nodes:
            target_addr = bridge_nodes[0].address if bridge_nodes else boundary_info.get("address")
            f_key = f"bridge_{target_addr or 'boundary'}"
            if f_key not in seen_finding_keys:
                seen_finding_keys.add(f_key)
                addr_display = f" at {target_addr}" if target_addr else ""
                desc = (
                    f"Cross-chain bridge gateway detected{addr_display}. "
                    "Outbound transfers transition across external blockchain networks; "
                    "automated attribution cannot continue automatically across this boundary."
                )
                f_id = cls._make_id(trace_id, FindingType.BRIDGE_ENCOUNTERED, target_addr)
                findings.append(
                    ForensicFinding(
                        finding_id=f_id,
                        case_id=case_id,
                        trace_id=trace_id,
                        severity=FindingSeverity.HIGH,
                        finding_type=FindingType.BRIDGE_ENCOUNTERED,
                        title="Cross-Chain Bridge Boundary Encountered",
                        description=desc,
                        timestamp=now,
                        source_signal="bridge_boundary_detector",
                        confidence=1.0,
                        related_address=target_addr,
                        evidence_refs=find_evidence_refs(address=target_addr),
                        graph_node_id=target_addr,
                    )
                )

        # 1C. Operational Ingestion Boundary (Timeouts / Rate Limits)
        if boundary_code in (BoundaryCode.PROVIDER_TIMEOUT.value, BoundaryCode.PROVIDER_RATE_LIMITED.value):
            f_key = f"operational_{boundary_code}"
            if f_key not in seen_finding_keys:
                seen_finding_keys.add(f_key)
                target_addr = boundary_info.get("address")
                tech = boundary_info.get("technical_details") or "Upstream RPC unresponsive"
                desc = f"Blockchain ingestion halted due to {boundary_code}: {tech}. Graph represents partial observed activity."
                f_id = cls._make_id(trace_id, FindingType.OPERATIONAL_BOUNDARY, boundary_code)
                findings.append(
                    ForensicFinding(
                        finding_id=f_id,
                        case_id=case_id,
                        trace_id=trace_id,
                        severity=FindingSeverity.MEDIUM,
                        finding_type=FindingType.OPERATIONAL_BOUNDARY,
                        title=f"Ingestion Boundary: {boundary_code}",
                        description=desc,
                        timestamp=now,
                        source_signal="provider_error_monitor",
                        related_address=target_addr,
                        graph_node_id=target_addr,
                    )
                )

        # -----------------------------------------------------------------
        # 2. ATTRIBUTION SIGNALS (Consolidation, Rapid Sweep, Fan-in, Low Conf)
        # -----------------------------------------------------------------
        if attribution_report and attribution_report.candidates:
            for candidate in attribution_report.candidates:
                cand_addr = candidate.candidate_address
                factors = candidate.factors
                vasp_name = candidate.vasp_name

                # 2A. HIGH — VASP Consolidation Detected
                # Condition: Sweep score >= 0.70 with strong downstream or direct VASP link
                if factors.sweep >= 0.70 and (factors.downstream_vasp_match >= 0.50 or factors.direct_tag >= 0.50):
                    f_key = f"consolidation_{cand_addr}_{vasp_name}"
                    if f_key not in seen_finding_keys:
                        seen_finding_keys.add(f_key)
                        
                        sweep_ratio_pct = 95.0
                        dominant_dest = ""
                        if candidate.sweep_details:
                            sweep_ratio_pct = round(candidate.sweep_details.sweep_ratio * 100, 1)
                            dominant_dest = candidate.sweep_details.dominant_destination

                        dest_snippet = f" destination ({dominant_dest[:10]}...)" if dominant_dest else " destination"
                        desc = (
                            f"Deposit candidate {cand_addr} consolidated {sweep_ratio_pct}% of incoming USDT "
                            f"into a downstream {vasp_name}-associated{dest_snippet}."
                        )
                        f_id = cls._make_id(trace_id, FindingType.VASP_CONSOLIDATION, cand_addr)
                        ev_refs = find_evidence_refs(
                            address=cand_addr,
                            types=[EvidenceType.SWEEP_ANALYSIS, EvidenceType.VASP_REGISTRY_RECORD, EvidenceType.VASP_ATTRIBUTION],
                        )
                        findings.append(
                            ForensicFinding(
                                finding_id=f_id,
                                case_id=case_id,
                                trace_id=trace_id,
                                severity=FindingSeverity.HIGH,
                                finding_type=FindingType.VASP_CONSOLIDATION,
                                title="VASP Consolidation Detected",
                                description=desc,
                                timestamp=now,
                                source_signal="sweep_analyzer",
                                confidence=candidate.confidence,
                                related_address=cand_addr,
                                related_vasp=vasp_name,
                                evidence_refs=ev_refs,
                                graph_node_id=cand_addr,
                            )
                        )

                # 2B. HIGH — Rapid Sweep Detected
                # Condition: Sweep score >= 0.40 and temporal score >= 0.65 (rapid movement within hours/minutes)
                if factors.sweep >= 0.40 and factors.temporal >= 0.65:
                    f_key = f"rapid_sweep_{cand_addr}"
                    if f_key not in seen_finding_keys:
                        seen_finding_keys.add(f_key)

                        time_desc = "rapid succession"
                        if candidate.temporal_details:
                            delay_hrs = candidate.temporal_details.delay_hours
                            delay_mins = int(delay_hrs * 60)
                            delay_sec = int(candidate.temporal_details.delay_seconds) % 60
                            if delay_mins > 60:
                                time_desc = f"{round(delay_hrs, 1)} hours"
                            elif delay_mins > 0:
                                time_desc = f"{delay_mins}m {delay_sec}s"
                            else:
                                time_desc = f"{delay_sec}s"

                        desc = (
                            f"Funds were swept to the downstream destination within {time_desc} of deposit, "
                            "consistent with automated custodial liquidation."
                        )
                        f_id = cls._make_id(trace_id, FindingType.RAPID_SWEEP, cand_addr)
                        ev_refs = find_evidence_refs(
                            address=cand_addr,
                            types=[EvidenceType.TEMPORAL_ANALYSIS, EvidenceType.SWEEP_ANALYSIS],
                        )
                        findings.append(
                            ForensicFinding(
                                finding_id=f_id,
                                case_id=case_id,
                                trace_id=trace_id,
                                severity=FindingSeverity.HIGH,
                                finding_type=FindingType.RAPID_SWEEP,
                                title="Rapid Sweep Detected",
                                description=desc,
                                timestamp=now,
                                source_signal="temporal_analyzer",
                                confidence=round(factors.temporal, 4),
                                related_address=cand_addr,
                                related_vasp=vasp_name,
                                evidence_refs=ev_refs,
                                graph_node_id=cand_addr,
                            )
                        )

                # 2C. MEDIUM — Fan-In Concentration
                # Condition: Fan-in score >= 0.60
                if factors.fan_in >= 0.60:
                    f_key = f"fan_in_{cand_addr}"
                    if f_key not in seen_finding_keys:
                        seen_finding_keys.add(f_key)
                        
                        senders_desc = "Multiple"
                        if candidate.fan_in_details:
                            senders_desc = str(candidate.fan_in_details.distinct_senders_count)

                        desc = f"{senders_desc} feeder addresses consolidated funds into candidate wallet {cand_addr}."
                        f_id = cls._make_id(trace_id, FindingType.FAN_IN_CONCENTRATION, cand_addr)
                        ev_refs = find_evidence_refs(
                            address=cand_addr,
                            types=[EvidenceType.FAN_IN_ANALYSIS],
                        )
                        findings.append(
                            ForensicFinding(
                                finding_id=f_id,
                                case_id=case_id,
                                trace_id=trace_id,
                                severity=FindingSeverity.MEDIUM,
                                finding_type=FindingType.FAN_IN_CONCENTRATION,
                                title="Fan-In Concentration",
                                description=desc,
                                timestamp=now,
                                source_signal="fan_in_analyzer",
                                confidence=round(factors.fan_in, 4),
                                related_address=cand_addr,
                                related_vasp=vasp_name,
                                evidence_refs=ev_refs,
                                graph_node_id=cand_addr,
                            )
                        )

            # 2D. LOW — Low-Confidence Attribution Review
            best_cand = attribution_report.best_candidate
            if best_cand and best_cand.confidence < 0.50 and (
                best_cand.vasp_id in ("unidentified", "unknown_entity") or
                best_cand.confidence_band == "LOW"
            ) and len(graph.edges) > 0:
                f_key = f"low_conf_{best_cand.candidate_address}"
                if f_key not in seen_finding_keys:
                    seen_finding_keys.add(f_key)
                    desc = (
                        f"Candidate VASP attribution remains below the configured confidence threshold "
                        f"({best_cand.confidence_percentage}%) and requires investigator review."
                    )
                    f_id = cls._make_id(trace_id, FindingType.LOW_CONFIDENCE_ATTRIBUTION, best_cand.candidate_address)
                    ev_refs = find_evidence_refs(
                        address=best_cand.candidate_address,
                        types=[EvidenceType.VASP_ATTRIBUTION],
                    )
                    findings.append(
                        ForensicFinding(
                            finding_id=f_id,
                            case_id=case_id,
                            trace_id=trace_id,
                            severity=FindingSeverity.LOW,
                            finding_type=FindingType.LOW_CONFIDENCE_ATTRIBUTION,
                            title="Low-Confidence Attribution Review",
                            description=desc,
                            timestamp=now,
                            source_signal="attribution_engine",
                            confidence=best_cand.confidence,
                            related_address=best_cand.candidate_address,
                            related_vasp=best_cand.vasp_name,
                            evidence_refs=ev_refs,
                            graph_node_id=best_cand.candidate_address,
                        )
                    )

        # -----------------------------------------------------------------
        # 3. GRAPH STRUCTURE FINDINGS (Layering, Trace Completed)
        # -----------------------------------------------------------------
        hops_reached = graph.meta.get("hops_reached", 0)

        # 3A. MEDIUM — Multi-Hop Layering
        if hops_reached >= 3 and len(graph.nodes) >= 4:
            f_key = f"layering_{hops_reached}"
            if f_key not in seen_finding_keys:
                seen_finding_keys.add(f_key)
                root_addr = graph.nodes[0].address if graph.nodes else None
                desc = (
                    f"Funds traversed {hops_reached} intermediate hops across {len(graph.nodes)} addresses, "
                    "exhibiting structured fund layering prior to reaching a terminal candidate."
                )
                f_id = cls._make_id(trace_id, FindingType.MULTI_HOP_LAYERING, str(hops_reached))
                ev_refs = find_evidence_refs(types=[EvidenceType.HOP_TRAVERSAL, EvidenceType.PATH_FORMATION])
                findings.append(
                    ForensicFinding(
                        finding_id=f_id,
                        case_id=case_id,
                        trace_id=trace_id,
                        severity=FindingSeverity.MEDIUM,
                        finding_type=FindingType.MULTI_HOP_LAYERING,
                        title="Multi-Hop Fund Layering",
                        description=desc,
                        timestamp=now,
                        source_signal="graph_engine_topology",
                        confidence=0.85,
                        related_address=root_addr,
                        evidence_refs=ev_refs,
                        graph_node_id=root_addr,
                    )
                )

        # 3B. INFO — Trace Completed
        if len(graph.nodes) > 0 and len(graph.edges) > 0:
            f_key = "trace_completed"
            if f_key not in seen_finding_keys:
                seen_finding_keys.add(f_key)
                pruned_count = len(graph.pruned_records)
                pruned_suffix = f" · {pruned_count} dust pruned" if pruned_count > 0 else ""
                desc = f"{hops_reached} hops · {len(graph.nodes)} nodes · {len(graph.edges)} relevant edges{pruned_suffix}."
                f_id = cls._make_id(trace_id, FindingType.TRACE_COMPLETED, "summary")
                findings.append(
                    ForensicFinding(
                        finding_id=f_id,
                        case_id=case_id,
                        trace_id=trace_id,
                        severity=FindingSeverity.INFO,
                        finding_type=FindingType.TRACE_COMPLETED,
                        title="Multi-Hop Trace Completed",
                        description=desc,
                        timestamp=now,
                        source_signal="graph_engine_summary",
                        confidence=1.0,
                    )
                )

        # -----------------------------------------------------------------
        # 4. OVERLAY PERSISTED REVIEW STATES
        # -----------------------------------------------------------------
        for finding in findings:
            if finding.finding_id in reviews:
                r = reviews[finding.finding_id]
                finding.status = FindingStatus(r.get("status", FindingStatus.OPEN.value))
                finding.reviewed_by = r.get("reviewed_by")
                finding.reviewed_at = r.get("reviewed_at")
                finding.review_notes = r.get("review_notes")

        # -----------------------------------------------------------------
        # 5. SORT BY SEVERITY & TIMESTAMP
        # -----------------------------------------------------------------
        severity_order = {
            FindingSeverity.CRITICAL: 0,
            FindingSeverity.HIGH: 1,
            FindingSeverity.MEDIUM: 2,
            FindingSeverity.LOW: 3,
            FindingSeverity.INFO: 4,
        }
        findings.sort(key=lambda f: (severity_order.get(f.severity, 99), f.timestamp.isoformat()), reverse=False)

        return findings

    @classmethod
    def _make_id(cls, trace_id: str, finding_type: FindingType, qualifier: Optional[str] = None) -> str:
        base = f"{trace_id}:{finding_type.value}:{qualifier or 'default'}"
        hash_digest = hashlib.sha256(base.encode()).hexdigest()[:12]
        return f"fnd_{finding_type.value.lower()}_{hash_digest}"
