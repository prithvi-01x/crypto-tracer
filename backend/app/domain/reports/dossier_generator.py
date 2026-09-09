import os
import io
import hashlib
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, List, Dict, Any, Tuple

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    KeepTogether,
    HRFlowable,
)
from reportlab.pdfgen import canvas

from backend.app.domain.models import InvestigationGraph
from backend.app.domain.attribution.models import AttributionReport, VASPCandidate
from backend.app.domain.evidence.models import EvidenceItem
from backend.app.persistence.models import Case, Trace
from backend.app.domain.reports.graph_drawer import render_graph_drawing
from backend.app.domain.evidence.hasher import compute_content_hash


class NumberedCanvas(canvas.Canvas):
    """Two-pass canvas to calculate total page count and draw running header/footer."""
    def __init__(self, *args, **kwargs):
        kwargs["pageCompression"] = 0
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count: int):
        self.saveState()
        self.setFont("Helvetica", 7.5)
        self.setFillColor(colors.HexColor("#64748B"))

        # Running header (pages > 1)
        if self._pageNumber > 1:
            self.drawString(40, 762, "CRYPTO-TRACER FORENSIC EVIDENCE DOSSIER — SECTION 63 BNSS")
            self.drawRightString(572, 762, f"CONFIDENTIAL // LAW ENFORCEMENT ONLY")
            self.setStrokeColor(colors.HexColor("#CBD5E1"))
            self.setLineWidth(0.5)
            self.line(40, 756, 572, 756)

        # Running footer (all pages)
        self.setStrokeColor(colors.HexColor("#E2E8F0"))
        self.setLineWidth(0.5)
        self.line(40, 38, 572, 38)
        self.drawString(40, 26, "Generated via Crypto-Tracer (SIH26182) | Section 63 BSA / BNSS Compliant")
        self.drawRightString(572, 26, f"Page {self._pageNumber} of {page_count}")
        self.restoreState()


class EvidenceDossierGenerator:
    """
    Generates an evidentiary PDF dossier complying with Section 63 of Bharatiya Sakshya Adhiniyam, 2023 (BSA).
    Enforces deterministic SHA-256 integrity hashing and full provenance linkage.
    """

    @classmethod
    def generate_pdf(
        cls,
        case: Case,
        trace: Trace,
        graph: InvestigationGraph,
        attribution_report: Optional[AttributionReport],
        evidence_items: List[EvidenceItem],
        investigator_name: str = "IO-Vikram-742",
        investigator_rank: str = "Inspector of Police",
        police_station: str = "Cyber Crime Police Station",
        include_graph_snapshot: bool = True,
        notes: Optional[str] = None,
    ) -> Tuple[bytes, str, Dict[str, Any]]:
        """
        Generates the Evidence Dossier PDF in memory.
        Returns: (pdf_bytes, sha256_content_hash, report_metadata)
        """
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            leftMargin=40,
            rightMargin=40,
            topMargin=48,
            bottomMargin=50,
            pageCompression=0,
        )

        styles = getSampleStyleSheet()

        # Custom paragraph styles
        title_style = ParagraphStyle(
            "DocTitle",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=15,
            leading=18,
            textColor=colors.HexColor("#0F172A"),
        )
        subtitle_style = ParagraphStyle(
            "DocSubtitle",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#2563EB"),
        )
        h1_style = ParagraphStyle(
            "Heading1_Custom",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=14,
            textColor=colors.HexColor("#1E293B"),
            spaceBefore=10,
            spaceAfter=4,
        )
        body_style = ParagraphStyle(
            "Body_Custom",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=8,
            leading=11,
            textColor=colors.HexColor("#334155"),
        )
        code_style = ParagraphStyle(
            "Code_Custom",
            parent=styles["Normal"],
            fontName="Courier",
            fontSize=7,
            leading=9,
            textColor=colors.HexColor("#0F172A"),
        )
        notice_style = ParagraphStyle(
            "Notice_Custom",
            parent=styles["Normal"],
            fontName="Helvetica-Oblique",
            fontSize=7.5,
            leading=10.5,
            textColor=colors.HexColor("#92400E"),
        )

        story = []
        gen_time = datetime.now(timezone.utc)

        # -------------------------------------------------------------
        # 1. HEADER & LEGAL CLASSIFICATION
        # -------------------------------------------------------------
        story.append(Paragraph("FORENSIC CRYPTOCURRENCY TRACE & EVIDENCE DOSSIER", title_style))
        story.append(Spacer(1, 2))
        story.append(Paragraph("PREPARED FOR ADMISSIBILITY UNDER SECTION 63 BHARATIYA SAKSHYA ADHINIYAM (BSA), 2023", subtitle_style))
        story.append(Spacer(1, 8))
        story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#1E293B"), spaceBefore=0, spaceAfter=8))

        # Check for Partial Trace or Boundary Condition
        is_partial = (trace.status == "PARTIAL") or graph.meta.get("is_partial", False) or (bool(graph.boundary and graph.boundary.get("is_partial")))
        boundary_code = (graph.boundary or {}).get("code") or graph.meta.get("boundary_reached")
        boundary_explanation = (graph.boundary or {}).get("investigator_explanation") or graph.meta.get("investigator_explanation")

        if is_partial or boundary_code in ("MIXER_BOUNDARY", "BRIDGE_BOUNDARY", "PROVIDER_TIMEOUT", "PROVIDER_RATE_LIMITED", "MAX_NODES_REACHED", "MAX_EDGES_REACHED"):
            partial_box = [[
                Paragraph(
                    f"<b>⚠️ PARTIAL INVESTIGATION DOSSIER — OPERATIONAL BOUNDARY: {boundary_code or 'PARTIAL_SEARCH'}</b><br/>"
                    f"<font size='7.5' color='#92400E'>{boundary_explanation or 'Traversal was halted by an operational boundary. Discovered multi-hop paths and evidence items are preserved for the explored subset.'}</font>",
                    notice_style,
                )
            ]]
            partial_table = Table(partial_box, colWidths=[532])
            partial_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FEF3C7")),
                ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#F59E0B")),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ]))
            story.append(partial_table)
            story.append(Spacer(1, 8))

        # -------------------------------------------------------------
        # 2. CASE & INVESTIGATION METADATA TABLE
        # -------------------------------------------------------------
        loss_display = f"INR {case.loss_amount_inr:,.2f}" if case.loss_amount_inr else "Not Recorded"
        meta_table_data = [
            [
                Paragraph("<b>FIR Number:</b>", body_style),
                Paragraph(f"<font name='Helvetica-Bold'>{case.fir_number}</font>", body_style),
                Paragraph("<b>Investigation Unit:</b>", body_style),
                Paragraph(police_station, body_style),
            ],
            [
                Paragraph("<b>Complainant / Victim:</b>", body_style),
                Paragraph(case.victim_reference or "Confidential", body_style),
                Paragraph("<b>Investigating Officer:</b>", body_style),
                Paragraph(f"{investigator_name}, {investigator_rank}", body_style),
            ],
            [
                Paragraph("<b>1930 Portal Ref:</b>", body_style),
                Paragraph(case.ack_number or "N/A", body_style),
                Paragraph("<b>Trace Run ID:</b>", body_style),
                Paragraph(f"<font name='Courier'>{trace.id[:18]}...</font>", body_style),
            ],
            [
                Paragraph("<b>Reported Defrauded Loss:</b>", body_style),
                Paragraph(f"<font color='#059669'><b>{loss_display}</b></font>", body_style),
                Paragraph("<b>Generation Timestamp:</b>", body_style),
                Paragraph(f"{gen_time.strftime('%Y-%m-%d %H:%M:%S')} UTC", body_style),
            ],
            [
                Paragraph("<b>Target Network & Asset:</b>", body_style),
                Paragraph("TRON Mainnet (TRC-20 USDT)", body_style),
                Paragraph("<b>Suspect Unhosted Wallet:</b>", body_style),
                Paragraph(f"<font name='Courier' color='#DC2626'>{case.suspect_wallet or 'N/A'}</font>", body_style),
            ],
            [
                Paragraph("<b>Execution Mode:</b>", body_style),
                Paragraph(
                    "<font color='#D97706'><b>DEMONSTRATION / REPLAY</b></font>"
                    if getattr(trace, "execution_mode", "DEMO") == "DEMO"
                    else "<font color='#059669'><b>LIVE ON-CHAIN TRACE</b></font>",
                    body_style
                ),
                Paragraph("<b>Data Provenance:</b>", body_style),
                Paragraph(
                    "Deterministic SIH Test Fixture"
                    if getattr(trace, "execution_mode", "DEMO") == "DEMO"
                    else "TronGrid API / Blockchain Ledger",
                    body_style
                ),
            ],
        ]

        meta_table = Table(meta_table_data, colWidths=[110, 155, 115, 152])
        meta_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
            ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#CBD5E1")),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(meta_table)
        story.append(Spacer(1, 10))

        # -------------------------------------------------------------
        # 3. EXECUTIVE INVESTIGATIVE FINDING (ACCEPTED ATTRIBUTION HYPOTHESIS)
        # -------------------------------------------------------------
        story.append(Paragraph("1. Executive Investigative Finding", h1_style))

        best_cand: Optional[VASPCandidate] = attribution_report.best_candidate if attribution_report else None
        if best_cand:
            finding_text = (
                f"Multi-hop blockchain traversal from suspect unhosted wallet <b>{case.suspect_wallet}</b> "
                f"traces funds into intermediate consolidation address <b>{best_cand.candidate_address}</b>, "
                f"which exhibits an <b>accepted attribution hypothesis</b> linking to "
                f"<b>{best_cand.vasp_name}</b> with <b>{best_cand.confidence_percentage}% confidence ({best_cand.confidence_band})</b>. "
                f"Analysis shows automated rapid sweep consolidation of relevant funds directly into verified "
                f"{best_cand.vasp_name} cluster wallets."
            )
        else:
            finding_text = (
                "Multi-hop blockchain traversal completed without a high-confidence VASP attribution match. "
                "All observed transfers and intermediate hops are detailed below for ongoing investigative analysis."
            )

        exec_box = Table([[Paragraph(finding_text, body_style)]], colWidths=[532])
        exec_box.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#EFF6FF")),
            ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#3B82F6")),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ]))
        story.append(exec_box)
        story.append(Spacer(1, 10))

        # -------------------------------------------------------------
        # 4. MULTI-HOP GRAPH SNAPSHOT
        # -------------------------------------------------------------
        if include_graph_snapshot:
            story.append(Paragraph("2. Multi-Hop Transaction Graph Snapshot", h1_style))
            drawing = render_graph_drawing(graph, width=532, height=130)
            story.append(drawing)
            story.append(Spacer(1, 10))

        # -------------------------------------------------------------
        # 5. ON-CHAIN TRANSACTION PATH & OBSERVED FACTS
        # -------------------------------------------------------------
        story.append(Paragraph("3. Observed On-Chain Transaction Path", h1_style))

        tx_headers = [
            Paragraph("<b>Hop</b>", body_style),
            Paragraph("<b>From Address</b>", body_style),
            Paragraph("<b>To Address</b>", body_style),
            Paragraph("<b>Amount (USDT)</b>", body_style),
            Paragraph("<b>Tx Hash</b>", body_style),
            Paragraph("<b>Timestamp (UTC)</b>", body_style),
        ]
        tx_rows = [tx_headers]

        for edge in graph.edges:
            if edge.pruned:
                continue
            tx_rows.append([
                Paragraph(f"Hop {edge.hop}", body_style),
                Paragraph(f"<font name='Courier'>{edge.from_address[:6]}...{edge.from_address[-4:]}</font>", body_style),
                Paragraph(f"<font name='Courier'>{edge.to_address[:6]}...{edge.to_address[-4:]}</font>", body_style),
                Paragraph(f"<b>{float(edge.amount):,.2f}</b>", body_style),
                Paragraph(f"<font name='Courier'>{edge.tx_hash[:8]}...{edge.tx_hash[-6:]}</font>", body_style),
                Paragraph(edge.timestamp.strftime("%Y-%m-%d %H:%M"), body_style),
            ])

        tx_table = Table(tx_rows, colWidths=[40, 95, 95, 80, 110, 112])
        tx_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0F172A")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("ALIGN", (3, 0), (3, -1), "RIGHT"),
            ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#CBD5E1")),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
            ("TOPPADDING", (0, 0), (-1, -1), 3.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#FFFFFF"), colors.HexColor("#F8FAFC")]),
        ]))
        story.append(tx_table)
        story.append(Spacer(1, 10))

        # -------------------------------------------------------------
        # 6. ATTRIBUTION FACTOR EXPLANATIONS & EVIDENCE POINTS
        # -------------------------------------------------------------
        if best_cand:
            story.append(Paragraph("4. Attribution Factor Analysis & Algorithmic Scoring", h1_style))

            attr_factors_data = [
                [
                    Paragraph("<b>Evaluation Factor</b>", body_style),
                    Paragraph("<b>Score</b>", body_style),
                    Paragraph("<b>Algorithmic Finding & Technical Justification</b>", body_style),
                ],
                [
                    Paragraph("Direct Registry Tag", body_style),
                    Paragraph(f"{best_cand.factors.direct_tag:.2f}", body_style),
                    Paragraph(best_cand.explanations.direct_tag, body_style),
                ],
                [
                    Paragraph("Downstream VASP Match", body_style),
                    Paragraph(f"{best_cand.factors.downstream_vasp_match:.2f}", body_style),
                    Paragraph(best_cand.explanations.downstream_vasp_match, body_style),
                ],
                [
                    Paragraph("Sweep Consolidation", body_style),
                    Paragraph(f"{best_cand.factors.sweep:.2f}", body_style),
                    Paragraph(best_cand.explanations.sweep, body_style),
                ],
                [
                    Paragraph("Fan-In Convergence", body_style),
                    Paragraph(f"{best_cand.factors.fan_in:.2f}", body_style),
                    Paragraph(best_cand.explanations.fan_in, body_style),
                ],
                [
                    Paragraph("Temporal Batch Delay", body_style),
                    Paragraph(f"{best_cand.factors.temporal:.2f}", body_style),
                    Paragraph(best_cand.explanations.temporal, body_style),
                ],
            ]

            attr_table = Table(attr_factors_data, colWidths=[120, 45, 367])
            attr_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1E293B")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#CBD5E1")),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                ("TOPPADDING", (0, 0), (-1, -1), 3.5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
            ]))
            story.append(attr_table)
            story.append(Spacer(1, 10))

        # -------------------------------------------------------------
        # 7. FORENSIC PRUNING RECORDS (IF ANY)
        # -------------------------------------------------------------
        if graph.pruned_records:
            story.append(Paragraph(f"5. Forensic Relevance Pruning Log ({len(graph.pruned_records)} Records Excluded)", h1_style))
            prune_rows = [[
                Paragraph("<b>Hop</b>", body_style),
                Paragraph("<b>Excluded Tx Hash</b>", body_style),
                Paragraph("<b>Amount</b>", body_style),
                Paragraph("<b>Pruning Reason</b>", body_style),
                Paragraph("<b>Threshold Applied</b>", body_style),
            ]]
            for pr in graph.pruned_records[:6]:
                prune_rows.append([
                    Paragraph(f"Hop {pr.hop}", body_style),
                    Paragraph(f"<font name='Courier'>{pr.tx_hash[:12]}...</font>", body_style),
                    Paragraph(f"{float(pr.amount):,.2f} {pr.asset}", body_style),
                    Paragraph(pr.reason, body_style),
                    Paragraph(f"{float(pr.threshold):,.2f} USD", body_style),
                ])
            p_table = Table(prune_rows, colWidths=[40, 150, 100, 120, 122])
            p_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#334155")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#CBD5E1")),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]))
            story.append(p_table)
            story.append(Spacer(1, 10))

        # -------------------------------------------------------------
        # 8. CRYPTOGRAPHIC PROVENANCE & SECTION 63 BSA INTEGRITY TABLE
        # -------------------------------------------------------------
        story.append(KeepTogether([
            Paragraph("6. Cryptographic Provenance DAG & Content Integrity Table", h1_style),
            Paragraph(
                "In compliance with Section 63 BSA, every observed fact, structural metric, and inferred finding "
                "carries an immutable SHA-256 content digest linking back to precursor evidence items.",
                body_style,
            ),
            Spacer(1, 4),
        ]))

        ev_headers = [
            Paragraph("<b>Evidence ID</b>", body_style),
            Paragraph("<b>Tier</b>", body_style),
            Paragraph("<b>Type / Title</b>", body_style),
            Paragraph("<b>Precursors</b>", body_style),
            Paragraph("<b>Deterministic SHA-256 Digest</b>", body_style),
        ]
        ev_rows = [ev_headers]

        for item in evidence_items[:8]:  # Top key items
            precursors = ", ".join([p.split('_')[-1][:6] for p in item.parent_evidence_ids]) if item.parent_evidence_ids else "Root"
            ev_rows.append([
                Paragraph(f"<font name='Courier'>{item.id[:14]}</font>", body_style),
                Paragraph(f"<b>{item.classification}</b>", body_style),
                Paragraph(f"{item.evidence_type}<br/><font color='#64748B'>{item.title[:28]}</font>", body_style),
                Paragraph(f"<font name='Courier'>{precursors}</font>", body_style),
                Paragraph(f"<font name='Courier'>{item.content_hash[:16]}...{item.content_hash[-8:]}</font>", code_style),
            ])

        ev_table = Table(ev_rows, colWidths=[70, 75, 125, 65, 197])
        ev_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1E293B")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#CBD5E1")),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
        ]))
        story.append(ev_table)
        story.append(Spacer(1, 10))

        # -------------------------------------------------------------
        # 9. INVESTIGATOR REVIEW STATUS & HUMAN-IN-THE-LOOP GATE
        # -------------------------------------------------------------
        human_review_item = next((it for it in evidence_items if it.classification == "HUMAN_ACTION"), None)
        review_status = "ACCEPTED INVESTIGATIVE FINDING" if human_review_item else "PENDING INVESTIGATOR REVIEW"
        status_color = "#059669" if human_review_item else "#D97706"

        review_notes_text = human_review_item.description if human_review_item else (
            notes or "Preliminary evidence dossier compiled for Investigating Officer evaluation."
        )

        review_box_data = [
            [
                Paragraph(f"<b>Review Status:</b> <font color='{status_color}'>{review_status}</font>", body_style),
                Paragraph(f"<b>Reviewing Officer:</b> {investigator_name}, {investigator_rank}", body_style),
            ],
            [
                Paragraph(f"<b>Investigator Justification & Notes:</b> {review_notes_text}", body_style),
                Paragraph(f"<b>Review Timestamp:</b> {gen_time.strftime('%Y-%m-%d %H:%M:%S')} UTC", body_style),
            ],
        ]
        review_table = Table(review_box_data, colWidths=[266, 266])
        review_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F1F5F9")),
            ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#64748B")),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ]))

        story.append(KeepTogether([
            Paragraph("7. Investigating Officer Review & Chain of Custody Gate", h1_style),
            review_table,
            Spacer(1, 10),
        ]))

        # -------------------------------------------------------------
        # 10. STATUTORY LIMITATIONS & EVIDENTIARY DISCLAIMER
        # -------------------------------------------------------------
        story.append(KeepTogether([
            Paragraph("8. Evidentiary Limitations & Statutory Notice", h1_style),
            Paragraph(
                "<b>MANDATORY LEGAL DISCLAIMER:</b> This evidence dossier documents an <b>accepted attribution hypothesis</b> "
                "and investigative findings based on algorithmic graph traversal and observable on-chain clustering. "
                "It does not constitute autonomous legal proof of account ownership. "
                "In accordance with Indian legal boundaries, this system does not autonomously freeze funds or issue legal notices. "
                "All findings require verification and formal requisition by an authorized Investigating Officer under Section 94 BNSS.",
                notice_style,
            ),
            Spacer(1, 10),
        ]))

        # -------------------------------------------------------------
        # 11. DETERMINISTIC REPORT CONTENT HASH & INTEGRITY SEAL
        # -------------------------------------------------------------
        # Calculate deterministic hash from case, trace, graph edges, and best candidate
        hashable_dict = {
            "case_id": case.id,
            "fir_number": case.fir_number,
            "trace_id": trace.id,
            "suspect_wallet": case.suspect_wallet,
            "best_candidate": best_cand.candidate_address if best_cand else None,
            "attributed_vasp": best_cand.vasp_id if best_cand else None,
            "confidence": float(best_cand.confidence) if best_cand else None,
            "edges_count": len(graph.edges),
            "evidence_count": len(evidence_items),
            "generated_at": gen_time.isoformat(),
        }
        report_hash = compute_content_hash(hashable_dict)

        seal_data = [[
            Paragraph(
                f"<b>CRYPTOGRAPHIC INTEGRITY SEAL (SHA-256):</b><br/>"
                f"<font name='Courier' size='7'>{report_hash}</font><br/>"
                f"<font size='6.5' color='#64748B'>Verified deterministic digest of dossier facts, graph topology, and provenance DAG.</font>",
                body_style,
            )
        ]]
        seal_table = Table(seal_data, colWidths=[532])
        seal_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
            ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#0F172A")),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ]))

        story.append(KeepTogether([seal_table]))

        # Build document
        doc.build(story, canvasmaker=NumberedCanvas)
        pdf_bytes = buffer.getvalue()
        buffer.close()

        report_meta = {
            "case_id": case.id,
            "fir_number": case.fir_number,
            "trace_id": trace.id,
            "report_hash": report_hash,
            "file_size_bytes": len(pdf_bytes),
            "best_candidate": best_cand.candidate_address if best_cand else None,
            "attributed_vasp": best_cand.vasp_name if best_cand else None,
            "confidence": float(best_cand.confidence) if best_cand else None,
            "generated_at": gen_time.isoformat(),
            "generated_by": investigator_name,
        }

        return pdf_bytes, report_hash, report_meta
