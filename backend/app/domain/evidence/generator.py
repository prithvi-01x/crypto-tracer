import uuid
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

from backend.app.domain.models import InvestigationGraph, GraphNode, GraphEdge, PrunedRecord
from backend.app.domain.attribution.models import AttributionReport, VASPCandidate
from backend.app.domain.evidence.models import (
    EvidenceItem,
    EvidenceClassification,
    EvidenceType,
    AuditEvent,
    AuditEventType,
)
from backend.app.domain.evidence.hasher import compute_content_hash


class EvidenceGenerator:
    """
    Automated Evidence & Provenance Generator.
    Transforms raw blockchain observations, traversal graph algorithms, and
    attribution inferences into immutable, verifiable evidence records forming
    a cryptographic provenance DAG.
    """

    ENGINE_VERSION = "0.1.0"

    @classmethod
    def generate_trace_evidence(
        cls,
        case_id: str,
        trace_id: str,
        graph: InvestigationGraph,
        attribution_report: Optional[AttributionReport] = None,
        config_snapshot: Optional[Dict[str, Any]] = None,
    ) -> List[EvidenceItem]:
        """
        Generate complete tiered evidence items for a trace graph and its attribution inferences.
        """
        evidence_items: List[EvidenceItem] = []
        now = datetime.now(timezone.utc)
        config = config_snapshot or graph.meta.get("config", {})

        # Map to track edge tx_hash -> evidence_id for provenance linking
        tx_evidence_map: Dict[str, str] = {}
        # Map to track address -> incoming/outgoing tx evidence IDs
        addr_incoming_evs: Dict[str, List[str]] = {}
        addr_outgoing_evs: Dict[str, List[str]] = {}

        # ---------------------------------------------------------
        # TIER 1: OBSERVED On-Chain Transaction Records
        # ---------------------------------------------------------
        for edge in graph.edges:
            ev_id = f"ev_tx_{edge.tx_hash[:16]}_{edge.hop}"
            tx_evidence_map[edge.tx_hash] = ev_id

            addr_incoming_evs.setdefault(edge.to_address, []).append(ev_id)
            addr_outgoing_evs.setdefault(edge.from_address, []).append(ev_id)

            payload = {
                "tx_hash": edge.tx_hash,
                "from_address": edge.from_address,
                "to_address": edge.to_address,
                "amount": str(edge.amount),
                "amount_raw": edge.amount_raw,
                "asset": edge.asset,
                "timestamp": edge.timestamp.isoformat(),
                "hop": edge.hop,
                "block_number": edge.block_number,
                "relevance_score": str(edge.relevance_score),
            }
            content_hash = compute_content_hash(payload)

            item = EvidenceItem(
                id=ev_id,
                case_id=case_id,
                trace_id=trace_id,
                evidence_type=EvidenceType.TRANSACTION_RECORD,
                classification=EvidenceClassification.OBSERVED,
                title=f"Transaction: {edge.amount} {edge.asset} ({edge.tx_hash[:10]}...)",
                description=(
                    f"Observed on-chain transfer of {edge.amount} {edge.asset} "
                    f"from {edge.from_address[:10]}... to {edge.to_address[:10]}... at hop {edge.hop}."
                ),
                source=edge.source or "trongrid",
                source_reference=edge.tx_hash,
                payload=payload,
                parent_evidence_ids=[],
                content_hash=content_hash,
                engine_version=cls.ENGINE_VERSION,
                configuration_snapshot=config,
                collected_at=edge.timestamp,
                analysis_timestamp=now,
            )
            evidence_items.append(item)

        # ---------------------------------------------------------
        # TIER 2: DERIVED Hop Traversals & Wallet Paths
        # ---------------------------------------------------------
        for node in graph.nodes:
            ev_id = f"ev_node_{node.address[:16]}_hop{node.hop}"
            parent_ids = addr_incoming_evs.get(node.address, [])

            payload = {
                "address": node.address,
                "node_type": node.node_type,
                "hop": node.hop,
                "total_received": str(node.total_received),
                "total_sent": str(node.total_sent),
                "chain": node.chain,
            }
            content_hash = compute_content_hash(payload)

            item = EvidenceItem(
                id=ev_id,
                case_id=case_id,
                trace_id=trace_id,
                evidence_type=EvidenceType.HOP_TRAVERSAL,
                classification=EvidenceClassification.DERIVED,
                title=f"Wallet Traversal: {node.address[:10]}... (Hop {node.hop}, {node.node_type.upper()})",
                description=(
                    f"BFS graph traversal reached wallet {node.address} at hop distance {node.hop}. "
                    f"Observed volume: {node.total_received} USDT received, {node.total_sent} USDT sent."
                ),
                source="networkx_graph_engine",
                source_reference=node.address,
                payload=payload,
                parent_evidence_ids=parent_ids,
                content_hash=content_hash,
                engine_version=cls.ENGINE_VERSION,
                configuration_snapshot=config,
                collected_at=now,
                analysis_timestamp=now,
            )
            evidence_items.append(item)

        # ---------------------------------------------------------
        # TIER 2: DERIVED Forensic Pruning Decisions
        # ---------------------------------------------------------
        for pr in graph.pruned_records:
            ev_id = f"ev_pruned_{pr.tx_hash[:16]}_{pr.hop}"
            payload = {
                "tx_hash": pr.tx_hash,
                "from_address": pr.from_address,
                "to_address": pr.to_address,
                "amount": str(pr.amount),
                "asset": pr.asset,
                "hop": pr.hop,
                "reason": pr.reason,
                "threshold": str(pr.threshold),
                "timestamp": pr.timestamp.isoformat(),
            }
            content_hash = compute_content_hash(payload)

            item = EvidenceItem(
                id=ev_id,
                case_id=case_id,
                trace_id=trace_id,
                evidence_type=EvidenceType.PRUNING_DECISION,
                classification=EvidenceClassification.DERIVED,
                title=f"Pruned Transfer: {pr.amount} {pr.asset} ({pr.reason})",
                description=(
                    f"Forensic pruning decision applied at hop {pr.hop}: Transfer excluded from graph expansion "
                    f"due to {pr.reason} (Applied threshold: {pr.threshold})."
                ),
                source="relevance_pruning_filter",
                source_reference=pr.tx_hash,
                payload=payload,
                parent_evidence_ids=[],
                content_hash=content_hash,
                engine_version=cls.ENGINE_VERSION,
                configuration_snapshot=config,
                collected_at=pr.timestamp,
                analysis_timestamp=now,
            )
            evidence_items.append(item)

        # ---------------------------------------------------------
        # TIER 2 & 3: Attribution Behavioral Analyses & Inferences
        # ---------------------------------------------------------
        if attribution_report:
            for candidate in attribution_report.candidates:
                cand_addr = candidate.candidate_address
                parent_txs = addr_incoming_evs.get(cand_addr, []) + addr_outgoing_evs.get(cand_addr, [])

                # A. Sweep Analysis Evidence (DERIVED)
                sweep_ev_id = f"ev_sweep_{cand_addr[:16]}"
                sweep_payload = candidate.sweep_details.model_dump(mode="json") if candidate.sweep_details else {}
                sweep_hash = compute_content_hash(sweep_payload)

                sweep_item = EvidenceItem(
                    id=sweep_ev_id,
                    case_id=case_id,
                    trace_id=trace_id,
                    evidence_type=EvidenceType.SWEEP_ANALYSIS,
                    classification=EvidenceClassification.DERIVED,
                    title=f"Sweep Consolidation Analysis: {cand_addr[:10]}...",
                    description=candidate.explanations.sweep,
                    source="sweep_analyzer",
                    source_reference=cand_addr,
                    payload=sweep_payload,
                    parent_evidence_ids=parent_txs,
                    content_hash=sweep_hash,
                    engine_version=cls.ENGINE_VERSION,
                    configuration_snapshot=config,
                    collected_at=now,
                    analysis_timestamp=now,
                )
                evidence_items.append(sweep_item)

                # B. Fan-In Analysis Evidence (DERIVED)
                fan_in_ev_id = f"ev_fan_in_{cand_addr[:16]}"
                fan_in_payload = candidate.fan_in_details.model_dump(mode="json") if candidate.fan_in_details else {}
                fan_in_hash = compute_content_hash(fan_in_payload)

                fan_in_item = EvidenceItem(
                    id=fan_in_ev_id,
                    case_id=case_id,
                    trace_id=trace_id,
                    evidence_type=EvidenceType.FAN_IN_ANALYSIS,
                    classification=EvidenceClassification.DERIVED,
                    title=f"Fan-In Convergence Analysis: {cand_addr[:10]}...",
                    description=candidate.explanations.fan_in,
                    source="fan_in_analyzer",
                    source_reference=cand_addr,
                    payload=fan_in_payload,
                    parent_evidence_ids=addr_incoming_evs.get(cand_addr, []),
                    content_hash=fan_in_hash,
                    engine_version=cls.ENGINE_VERSION,
                    configuration_snapshot=config,
                    collected_at=now,
                    analysis_timestamp=now,
                )
                evidence_items.append(fan_in_item)

                # C. Temporal Analysis Evidence (DERIVED)
                temp_ev_id = f"ev_temporal_{cand_addr[:16]}"
                temp_payload = candidate.temporal_details.model_dump(mode="json") if candidate.temporal_details else {}
                temp_hash = compute_content_hash(temp_payload)

                temp_item = EvidenceItem(
                    id=temp_ev_id,
                    case_id=case_id,
                    trace_id=trace_id,
                    evidence_type=EvidenceType.TEMPORAL_ANALYSIS,
                    classification=EvidenceClassification.DERIVED,
                    title=f"Temporal Delay Analysis: {cand_addr[:10]}...",
                    description=candidate.explanations.temporal,
                    source="temporal_analyzer",
                    source_reference=cand_addr,
                    payload=temp_payload,
                    parent_evidence_ids=parent_txs,
                    content_hash=temp_hash,
                    engine_version=cls.ENGINE_VERSION,
                    configuration_snapshot=config,
                    collected_at=now,
                    analysis_timestamp=now,
                )
                evidence_items.append(temp_item)

                # D. VASP Registry Match Evidence (OBSERVED if direct / DERIVED if downstream)
                vasp_ev_id = f"ev_vasp_match_{cand_addr[:16]}"
                is_direct = candidate.factors.direct_tag > 0
                vasp_classification = EvidenceClassification.OBSERVED if is_direct else EvidenceClassification.DERIVED
                vasp_payload = {
                    "vasp_id": candidate.vasp_id,
                    "vasp_name": candidate.vasp_name,
                    "verification_status": candidate.verification_status,
                    "direct_tag_score": candidate.factors.direct_tag,
                    "downstream_vasp_match": candidate.factors.downstream_vasp_match,
                    "direct_tag_explanation": candidate.explanations.direct_tag,
                    "downstream_explanation": candidate.explanations.downstream_vasp_match,
                }
                vasp_hash = compute_content_hash(vasp_payload)

                vasp_item = EvidenceItem(
                    id=vasp_ev_id,
                    case_id=case_id,
                    trace_id=trace_id,
                    evidence_type=EvidenceType.VASP_REGISTRY_RECORD,
                    classification=vasp_classification,
                    title=f"VASP Registry Match: {candidate.vasp_name} ({candidate.verification_status})",
                    description=(
                        candidate.explanations.direct_tag
                        if is_direct
                        else candidate.explanations.downstream_vasp_match
                    ),
                    source="vasp_registry",
                    source_reference=candidate.vasp_id,
                    payload=vasp_payload,
                    parent_evidence_ids=[],
                    content_hash=vasp_hash,
                    engine_version=cls.ENGINE_VERSION,
                    configuration_snapshot=config,
                    collected_at=now,
                    analysis_timestamp=now,
                )
                evidence_items.append(vasp_item)

                # E. Attribution Hypothesis & Confidence Calculation (INFERRED)
                # Forms the apex of the provenance chain, linking to all supporting evidence items
                attr_ev_id = f"ev_attr_{cand_addr[:16]}_{candidate.vasp_id}"
                attr_parents = [sweep_ev_id, fan_in_ev_id, temp_ev_id, vasp_ev_id]

                attr_payload = {
                    "candidate_address": candidate.candidate_address,
                    "vasp_id": candidate.vasp_id,
                    "vasp_name": candidate.vasp_name,
                    "hypothesis_label": candidate.hypothesis_label,
                    "confidence": candidate.confidence,
                    "confidence_percentage": candidate.confidence_percentage,
                    "confidence_band": candidate.confidence_band,
                    "verification_status": candidate.verification_status,
                    "factors": candidate.factors.model_dump(mode="json"),
                    "explanations": candidate.explanations.model_dump(mode="json"),
                    "evidence_bullet_points": candidate.evidence_bullet_points,
                    "scoring_formula": "0.35*effective_tag(direct|0.80*downstream) + 0.35*sweep + 0.15*fan_in + 0.15*temporal",
                    "disclaimer": attribution_report.disclaimer,
                }
                attr_hash = compute_content_hash(attr_payload)

                attr_item = EvidenceItem(
                    id=attr_ev_id,
                    case_id=case_id,
                    trace_id=trace_id,
                    evidence_type=EvidenceType.VASP_ATTRIBUTION,
                    classification=EvidenceClassification.INFERRED,
                    title=f"{candidate.hypothesis_label} ({candidate.confidence_percentage}% Confidence)",
                    description=(
                        f"Inferred attribution hypothesis linking {candidate.candidate_address} to {candidate.vasp_name} "
                        f"with {candidate.confidence_band} confidence ({candidate.confidence_percentage}%). "
                        f"Disclaimer: {attribution_report.disclaimer}"
                    ),
                    source="attribution_engine",
                    source_reference=candidate.candidate_address,
                    payload=attr_payload,
                    parent_evidence_ids=attr_parents,
                    content_hash=attr_hash,
                    engine_version=cls.ENGINE_VERSION,
                    configuration_snapshot=config,
                    collected_at=now,
                    analysis_timestamp=now,
                )
                evidence_items.append(attr_item)

        return evidence_items

    @classmethod
    def generate_human_action_evidence(
        cls,
        audit_event: AuditEvent,
        parent_evidence_id: Optional[str] = None,
    ) -> EvidenceItem:
        """
        Generate a HUMAN_ACTION tier evidence item from an investigator audit event.
        """
        ev_id = f"ev_human_{audit_event.id[:16]}"
        payload = {
            "actor_id": audit_event.actor_id,
            "event_type": audit_event.event_type,
            "action_summary": audit_event.action_summary,
            "metadata": audit_event.metadata,
        }
        content_hash = compute_content_hash(payload)

        return EvidenceItem(
            id=ev_id,
            case_id=audit_event.case_id,
            trace_id=audit_event.trace_id,
            evidence_type=EvidenceType.ATTRIBUTION_REVIEW
            if audit_event.event_type in (AuditEventType.ATTRIBUTION_ACCEPTED, AuditEventType.ATTRIBUTION_REJECTED)
            else EvidenceType.EVIDENCE_REVIEW,
            classification=EvidenceClassification.HUMAN_ACTION,
            title=f"Investigator Action: {audit_event.event_type.replace('_', ' ').title()}",
            description=audit_event.action_summary,
            source="human_investigator",
            source_reference=audit_event.actor_id,
            payload=payload,
            parent_evidence_ids=[parent_evidence_id] if parent_evidence_id else [],
            content_hash=content_hash,
            engine_version=cls.ENGINE_VERSION,
            collected_at=audit_event.created_at,
            analysis_timestamp=audit_event.created_at,
        )
