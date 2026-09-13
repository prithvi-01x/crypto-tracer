import os
import io
import hashlib
from datetime import datetime, timezone
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

from backend.app.persistence.models import Case, Trace, EvidenceItemModel
from backend.app.domain.evidence.hasher import compute_genesis_hash, canonicalize_rfc8785


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
        self.setFont("Helvetica-Bold", 8)
        self.setFillColor(colors.HexColor("#1E3A8A"))

        # Top running header
        self.drawString(40, 762, "CERTIFICATE OF ELECTRONIC EVIDENCE — SECTION 63 BSA, 2023")
        self.setFont("Helvetica", 7.5)
        self.setFillColor(colors.HexColor("#64748B"))
        self.drawRightString(572, 762, "STATUTORY ADMISSIBILITY // COURT COPY")
        self.setStrokeColor(colors.HexColor("#CBD5E1"))
        self.setLineWidth(0.5)
        self.line(40, 756, 572, 756)

        # Bottom footer
        self.setStrokeColor(colors.HexColor("#E2E8F0"))
        self.setLineWidth(0.5)
        self.line(40, 38, 572, 38)
        self.drawString(40, 26, "Crypto-Tracer Forensics | Section 63 BSA Certificate (replacing Section 65B Indian Evidence Act)")
        self.drawRightString(572, 26, f"Page {self._pageNumber} of {page_count}")
        self.restoreState()


class Section63BSAGenerator:
    """
    Generates an official Certificate of Electronic Evidence under Section 63(4) of
    the Bharatiya Sakshya Adhiniyam, 2023 (BSA) (formerly Section 65B of Indian Evidence Act, 1872).
    """

    @classmethod
    def generate_pdf(
        cls,
        case: Case,
        trace: Trace,
        evidence_items: Optional[List[Any]] = None,
        investigator_name: str = "IO-Vikram-742",
        investigator_rank: str = "Inspector of Police",
        police_station: str = "Cyber Crime Police Station",
        technical_examiner: Optional[str] = "Forensic Examiner (Cyber Cell)",
        notes: Optional[str] = None,
    ) -> Tuple[bytes, str, Dict[str, Any]]:
        """
        Generates the Section 63 BSA Certificate PDF in memory.
        Returns (pdf_bytes, sha256_hash, metadata_dict).
        """
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            leftMargin=40,
            rightMargin=40,
            topMargin=54,
            bottomMargin=54,
        )

        styles = getSampleStyleSheet()
        normal = styles["Normal"]

        title_style = ParagraphStyle(
            "BSATitle",
            parent=normal,
            fontName="Helvetica-Bold",
            fontSize=13,
            leading=16,
            textColor=colors.HexColor("#0F172A"),
            alignment=1,  # Center
        )
        subtitle_style = ParagraphStyle(
            "BSASubTitle",
            parent=normal,
            fontName="Helvetica",
            fontSize=8.5,
            leading=12,
            textColor=colors.HexColor("#475569"),
            alignment=1,
        )
        sec_header = ParagraphStyle(
            "BSASecHeader",
            parent=normal,
            fontName="Helvetica-Bold",
            fontSize=10,
            leading=13,
            textColor=colors.HexColor("#1E3A8A"),
        )
        body = ParagraphStyle(
            "BSABody",
            parent=normal,
            fontName="Helvetica",
            fontSize=8,
            leading=11,
            textColor=colors.HexColor("#1E293B"),
        )
        body_bold = ParagraphStyle(
            "BSABodyBold",
            parent=body,
            fontName="Helvetica-Bold",
        )
        legal_dec = ParagraphStyle(
            "BSALegalDec",
            parent=normal,
            fontName="Helvetica",
            fontSize=8,
            leading=12,
            textColor=colors.HexColor("#0F172A"),
            alignment=4,  # Justify
        )

        story = []

        # 1. Statutory Header
        story.append(Spacer(1, 4))
        story.append(Paragraph("IN THE COURT OF COMPETENT JURISDICTION", subtitle_style))
        story.append(Spacer(1, 2))
        story.append(Paragraph("CERTIFICATE OF ELECTRONIC EVIDENCE", title_style))
        story.append(Spacer(1, 2))
        story.append(Paragraph(
            "<b>[Issued under Section 63(4) of the Bharatiya Sakshya Adhiniyam, 2023 (Act No. 47 of 2023)]</b><br/>"
            "<i>(Corresponding to Section 65B of the Indian Evidence Act, 1872)</i>",
            subtitle_style,
        ))
        story.append(Spacer(1, 8))
        story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#1E3A8A"), spaceBefore=2, spaceAfter=8))

        # 2. Case Particulars Table
        now_utc = datetime.now(timezone.utc)
        case_rows = [
            [Paragraph("<b>Police Station:</b>", body), Paragraph(police_station, body),
             Paragraph("<b>Date of Certificate:</b>", body), Paragraph(now_utc.strftime("%d %B %Y, %H:%M UTC"), body)],
            [Paragraph("<b>FIR / Crime No:</b>", body), Paragraph(case.fir_number or "N/A", body),
             Paragraph("<b>Case ID (UUID):</b>", body), Paragraph(str(case.id), body)],
            [Paragraph("<b>Investigating Officer:</b>", body), Paragraph(f"{investigator_name} ({investigator_rank})", body),
             Paragraph("<b>Technical Examiner:</b>", body), Paragraph(technical_examiner or "Cyber Cell Examiner", body)],
            [Paragraph("<b>Suspect Address:</b>", body), Paragraph(trace.input_value or "N/A", body),
             Paragraph("<b>Trace ID:</b>", body), Paragraph(str(trace.id), body)],
        ]
        case_tbl = Table(case_rows, colWidths=[100, 166, 100, 166])
        case_tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(case_tbl)
        story.append(Spacer(1, 10))

        # 3. Preamble & Affirmation
        preamble = (
            f"I, <b>{investigator_name}</b>, holding the rank of <b>{investigator_rank}</b> at <b>{police_station}</b>, "
            f"do hereby solemnly affirm, certify and declare under Section 63 of the Bharatiya Sakshya Adhiniyam, 2023, "
            f"that the electronic records, blockchain transactions, multi-hop forensic graph representations, and analytical "
            f"findings described herein were produced by the automated computer systems under my lawful supervisory control, "
            f"and satisfy all conditions of admissibility prescribed under Section 63(2) and Section 63(4) of the BSA, 2023."
        )
        story.append(Paragraph(preamble, legal_dec))
        story.append(Spacer(1, 10))

        # 4. SCHEDULE — PART A: Identification of Electronic Records
        story.append(Paragraph("SCHEDULE — PART A", sec_header))
        story.append(Paragraph("<b>[Identification of Electronic Records & Technical Device Particulars — Sec. 63(4)(a) & (b) BSA]</b>", subtitle_style))
        story.append(Spacer(1, 4))

        genesis_hash = compute_genesis_hash(str(case.id))
        ev_items = evidence_items or []
        ev_count = len(ev_items)

        records_info = [
            [Paragraph("<b>Category</b>", body_bold), Paragraph("<b>Specification / Forensic Value</b>", body_bold)],
            [Paragraph("Primary Electronic Record", body), Paragraph(f"Blockchain Forensic Ledger & Multi-Hop Trace (Trace ID: {trace.id})", body)],
            [Paragraph("Cryptographic Genesis Anchor", body), Paragraph(f"<code>{genesis_hash}</code>", body)],
            [Paragraph("Blockchain Network / Protocol", body), Paragraph(f"{trace.chain} Mainnet / TRC20:USDT Token Ledger", body)],
            [Paragraph("Evidence Chain Length", body), Paragraph(f"{ev_count} itemized immutable evidence records", body)],
            [Paragraph("Computer System / OS", body), Paragraph("Linux x86_64 Forensics Node (Ubuntu/Alpine Container)", body)],
            [Paragraph("Analysis Application", body), Paragraph("Crypto-Tracer Enterprise Forensics Suite (v0.1.0)", body)],
            [Paragraph("Cryptographic Algorithms", body), Paragraph("SHA-256 (FIPS 180-4) with RFC 8785 Canonical JSON Serialization", body)],
            [Paragraph("Network Interface", body), Paragraph("TLS 1.3 Encrypted TRON Blockchain REST/gRPC Interface", body)],
            [Paragraph("Storage & Vault Security", body), Paragraph("PostgreSQL 16 Relational Ledger & AES-256-GCM Storage Vault", body)],
        ]
        rec_tbl = Table(records_info, colWidths=[160, 372])
        rec_tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E2E8F0")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(rec_tbl)
        story.append(Spacer(1, 8))

        # 5. Itemized Evidence Entries Table (if any items present)
        if ev_items:
            story.append(Paragraph("<b>Itemized Evidence Items & Content Digests:</b>", body_bold))
            story.append(Spacer(1, 2))
            ev_rows = [[Paragraph("<b>Seq</b>", body_bold), Paragraph("<b>Evidence ID</b>", body_bold), Paragraph("<b>Classification</b>", body_bold), Paragraph("<b>SHA-256 Content Digest</b>", body_bold)]]
            for idx, item in enumerate(ev_items[:12], 1):  # Show up to 12 items
                ev_id = getattr(item, "id", f"ev_{idx}")
                classification = getattr(item, "classification", "OBSERVED")
                c_hash = getattr(item, "content_hash", "") or getattr(item, "current_hash", "")
                ev_rows.append([
                    Paragraph(str(idx), body),
                    Paragraph(str(ev_id)[:24], body),
                    Paragraph(str(classification), body),
                    Paragraph(f"<code>{str(c_hash)[:32]}...</code>", body),
                ])
            if len(ev_items) > 12:
                ev_rows.append([Paragraph("...", body), Paragraph(f"... and {len(ev_items) - 12} more items", body), Paragraph("-", body), Paragraph("-", body)])

            ev_tbl = Table(ev_rows, colWidths=[30, 150, 100, 252])
            ev_tbl.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F1F5F9")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ]))
            story.append(ev_tbl)
            story.append(Spacer(1, 10))

        # 6. SCHEDULE — PART B: Statutory Declarations
        story.append(KeepTogether([
            Paragraph("SCHEDULE — PART B", sec_header),
            Paragraph("<b>[Certificate by Person in Charge / Lawful Control Declaration — Sec. 63(4)(c) BSA]</b>", subtitle_style),
            Spacer(1, 4),
            Paragraph(
                "In compliance with the mandatory requirements of Section 63(2) and Section 63(4) of the "
                "Bharatiya Sakshya Adhiniyam, 2023, I hereby certify the following factual conditions:<br/><br/>"
                "<b>1. Lawful Production & Regular Use [Sec. 63(2)(a)]:</b> The electronic records referred to in Part A "
                "were produced by the computer system during the period over which the computer was used regularly to store "
                "or process information for the purposes of cyber forensic investigation and criminal law enforcement regularly "
                "carried on by this Police Station.<br/><br/>"
                "<b>2. Regular Feed of Information [Sec. 63(2)(b)]:</b> Throughout the material period, electronic transaction "
                "data from public cryptographic distributed ledgers was regularly and systematically ingested into the computer "
                "in the ordinary course of investigative operations.<br/><br/>"
                "<b>3. Uninterrupted & Proper Operation [Sec. 63(2)(c)]:</b> Throughout the material period, the computer system "
                "was operating properly and without error, malfunction, or unauthorized modification. If at any time there was an "
                "operational pause, it did not affect the electronic record or the accuracy of its contents.<br/><br/>"
                "<b>4. Reproducible Fidelity & Cryptographic Anchor [Sec. 63(2)(d)]:</b> The electronic evidence faithfully "
                "reproduces information retrieved from the blockchain ledger. Each record is chained via SHA-256 cryptographic hashes "
                "anchored to the genesis block of the case, ensuring tamper-evident provenance.<br/><br/>"
                "<b>5. Knowledge & Belief [Sec. 63(4)]:</b> To the best of my knowledge and belief, all matters stated in this "
                "certificate are true and correct, and I make this statement in my official capacity as the person responsible "
                "for the management and supervision of the relevant electronic devices and investigation.",
                legal_dec,
            ),
            Spacer(1, 14),
        ]))

        if notes:
            story.append(KeepTogether([
                Paragraph("<b>Investigator Additional Notes:</b>", body_bold),
                Paragraph(notes, body),
                Spacer(1, 10),
            ]))

        # 7. Signature & Attestation Block
        sig_rows = [
            [
                Paragraph("<b>CERTIFYING OFFICER (IN CHARGE)</b>", body_bold),
                Paragraph("<b>CYBER FORENSIC EXAMINER</b>", body_bold),
            ],
            [
                Paragraph(
                    f"Signature: ___________________________<br/>"
                    f"Name: <b>{investigator_name}</b><br/>"
                    f"Rank: {investigator_rank}<br/>"
                    f"Police Station: {police_station}<br/>"
                    f"Date: {now_utc.strftime('%d-%m-%Y')} // Time: {now_utc.strftime('%H:%M:%S UTC')}",
                    body,
                ),
                Paragraph(
                    f"Signature: ___________________________<br/>"
                    f"Name: <b>{technical_examiner or 'Cyber Forensic Specialist'}</b><br/>"
                    f"Designation: Technical Examiner<br/>"
                    f"Division: Cyber Crime Operations Center<br/>"
                    f"Seal: [ OFFICIAL POLICE CYBER CELL SEAL ]",
                    body,
                ),
            ],
        ]
        sig_tbl = Table(sig_rows, colWidths=[266, 266])
        sig_tbl.setStyle(TableStyle([
            ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#1E3A8A")),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F1F5F9")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ]))
        story.append(KeepTogether([sig_tbl]))

        doc.build(story, canvasmaker=NumberedCanvas)
        pdf_bytes = buffer.getvalue()
        buffer.close()

        report_hash = hashlib.sha256(pdf_bytes).hexdigest()
        meta = {
            "statutory_act": "Bharatiya Sakshya Adhiniyam, 2023",
            "statutory_section": "Section 63(4)",
            "superseded_act": "Indian Evidence Act, 1872 (Section 65B)",
            "genesis_hash": genesis_hash,
            "evidence_count": ev_count,
            "investigator": investigator_name,
            "rank": investigator_rank,
            "police_station": police_station,
            "generated_at": now_utc.isoformat(),
        }
        return pdf_bytes, report_hash, meta
