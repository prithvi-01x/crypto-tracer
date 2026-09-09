import io
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

from backend.app.domain.attribution.models import AttributionReport, VASPCandidate
from backend.app.persistence.models import Case, Trace
from backend.app.domain.evidence.hasher import compute_content_hash


class BNSSCanvas(canvas.Canvas):
    """Running header and footer for legal draft notice."""
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
        self.setFillColor(colors.HexColor("#DC2626"))

        # Top banner warning
        self.drawString(40, 762, "DRAFT REQUISITION — FOR OFFICER REVIEW ONLY // NOT FOR AUTONOMOUS DISPATCH")
        self.setFont("Helvetica", 7.5)
        self.setFillColor(colors.HexColor("#64748B"))
        self.drawRightString(572, 762, "CONFIDENTIAL // SECTION 94 BNSS")
        self.setStrokeColor(colors.HexColor("#CBD5E1"))
        self.setLineWidth(0.5)
        self.line(40, 756, 572, 756)

        # Bottom footer
        self.setStrokeColor(colors.HexColor("#E2E8F0"))
        self.setLineWidth(0.5)
        self.line(40, 38, 572, 38)
        self.drawString(40, 26, "Draft Prepared via Crypto-Tracer (SIH26182) | Section 94 BNSS, 2023 (formerly Section 91 CrPC)")
        self.drawRightString(572, 26, f"Page {self._pageNumber} of {page_count}")
        self.restoreState()


class BNSS94DraftGenerator:
    """
    Generates a draft legal record-production request under Section 94 of
    the Bharatiya Nagarik Suraksha Sanhita, 2023 (BNSS) (formerly Section 91 CrPC).
    """

    @classmethod
    def generate_pdf(
        cls,
        case: Case,
        trace: Trace,
        attribution_report: Optional[AttributionReport],
        target_vasp_override: Optional[str] = None,
        candidate_address_override: Optional[str] = None,
        investigator_name: str = "IO-Vikram-742",
        investigator_rank: str = "Inspector of Police",
        police_station: str = "Cyber Crime Police Station",
        court_jurisdiction: str = "Chief Judicial Magistrate / Cyber Special Court",
        compliance_email: Optional[str] = None,
        urgency_hours: int = 48,
        notes: Optional[str] = None,
    ) -> Tuple[bytes, str, Dict[str, Any]]:
        """
        Generates the Section 94 BNSS Draft PDF in memory.
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

        title_style = ParagraphStyle(
            "LegalTitle",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=13,
            leading=16,
            alignment=1,  # Center
            textColor=colors.HexColor("#0F172A"),
        )
        banner_style = ParagraphStyle(
            "DraftBanner",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=12,
            alignment=1,
            textColor=colors.HexColor("#B91C1C"),
        )
        h1_style = ParagraphStyle(
            "LegalH1",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=10,
            leading=13,
            textColor=colors.HexColor("#0F172A"),
            spaceBefore=8,
            spaceAfter=3,
        )
        body_style = ParagraphStyle(
            "LegalBody",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=8.5,
            leading=12,
            textColor=colors.HexColor("#1E293B"),
        )
        list_style = ParagraphStyle(
            "LegalList",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=8,
            leading=11.5,
            textColor=colors.HexColor("#334155"),
            leftIndent=15,
        )

        story = []
        gen_time = datetime.now(timezone.utc)

        # Detect target candidate
        best_cand: Optional[VASPCandidate] = attribution_report.best_candidate if attribution_report else None
        target_vasp = target_vasp_override or (best_cand.vasp_name if best_cand else "Virtual Asset Service Provider")
        target_wallet = candidate_address_override or (best_cand.candidate_address if best_cand else (case.suspect_wallet or "N/A"))

        # -------------------------------------------------------------
        # 1. PROMINENT OFFICER REVIEW WARNING BANNER
        # -------------------------------------------------------------
        banner_data = [[
            Paragraph(
                "<b>*** DRAFT NOTICE — FOR INVESTIGATING OFFICER (IO) REVIEW ONLY ***</b><br/>"
                "<font size='7.5' color='#7F1D1D'>This is a computer-generated draft legal requisition prepared under Section 94 BNSS, 2023. "
                "It requires formal review, verification of case facts, and signature by the authorized officer before dispatch. "
                "Crypto-Tracer does not autonomously dispatch legal process or freeze accounts.</font>",
                banner_style,
            )
        ]]
        banner_table = Table(banner_data, colWidths=[532])
        banner_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FEF2F2")),
            ("BOX", (0, 0), (-1, -1), 1.5, colors.HexColor("#EF4444")),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ]))
        story.append(banner_table)
        story.append(Spacer(1, 10))

        # -------------------------------------------------------------
        # 2. POLICE DEPARTMENT LETTERHEAD & NOTICE HEADING
        # -------------------------------------------------------------
        story.append(Paragraph(f"<b>OFFICE OF THE INVESTIGATING OFFICER</b><br/>{police_station.upper()}", title_style))
        story.append(Spacer(1, 4))
        story.append(Paragraph(
            "<b>NOTICE UNDER SECTION 94 OF BHARATIYA NAGARIK SURAKSHA SANHITA, 2023 (BNSS)</b><br/>"
            "<font size='8' color='#475569'><i>(Corresponding to Section 91 of the Code of Criminal Procedure, 1973)</i></font>",
            title_style,
        ))
        story.append(Spacer(1, 6))
        story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#0F172A"), spaceBefore=0, spaceAfter=8))

        # -------------------------------------------------------------
        # 3. NOTICE PARTICULARS TABLE
        # -------------------------------------------------------------
        loss_display = f"INR {case.loss_amount_inr:,.2f}" if case.loss_amount_inr else "Substantial Pecuniary Loss"
        particulars_data = [
            [
                Paragraph("<b>Notice Ref / Dispatch No.:</b>", body_style),
                Paragraph(f"CYBER/{case.fir_number.replace('/', '-')}/BNSS-94", body_style),
                Paragraph("<b>Date of Issuance:</b>", body_style),
                Paragraph(f"{gen_time.strftime('%d %B %Y')}", body_style),
            ],
            [
                Paragraph("<b>Police Station / FIR No.:</b>", body_style),
                Paragraph(f"<b>{case.fir_number}</b>", body_style),
                Paragraph("<b>Designated Court:</b>", body_style),
                Paragraph(court_jurisdiction, body_style),
            ],
            [
                Paragraph("<b>Target Entity (VASP):</b>", body_style),
                Paragraph(f"<b>{target_vasp}</b> (Compliance / Law Enforcement Desk)", body_style),
                Paragraph("<b>Compliance Contact:</b>", body_style),
                Paragraph(compliance_email or f"law-enforcement@{target_vasp.lower().replace(' ', '')}.com", body_style),
            ],
            [
                Paragraph("<b>Statutory Offences:</b>", body_style),
                Paragraph("Sections 316 / 318 BNS, 2023 r/w Section 66D Information Technology Act", body_style),
                Paragraph("<b>Mandatory Turnaround:</b>", body_style),
                Paragraph(f"<b>Within {urgency_hours} Hours of Receipt</b>", body_style),
            ],
        ]

        p_table = Table(particulars_data, colWidths=[130, 145, 115, 142])
        p_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
            ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#CBD5E1")),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(p_table)
        story.append(Spacer(1, 10))

        # -------------------------------------------------------------
        # 4. FORMAL REQUISITION NARRATIVE
        # -------------------------------------------------------------
        to_text = (
            f"<b>To:</b><br/>"
            f"The Nodal / Compliance Officer (Law Enforcement Inquiries),<br/>"
            f"<b>{target_vasp}</b>.<br/>"
        )
        story.append(Paragraph(to_text, body_style))
        story.append(Spacer(1, 6))

        subject_text = (
            f"<b>SUBJECT: REQUISITION UNDER SECTION 94 BNSS, 2023 FOR PRODUCTION OF SUBSCRIBER KYC, "
            f"TRANSACTION LEDGERS, AND DIGITAL AUDIT TRAILS IN RESPECT OF WALLET: {target_wallet}</b>"
        )
        story.append(Paragraph(subject_text, ParagraphStyle("Subj", parent=body_style, fontName="Helvetica-Bold", backColor=colors.HexColor("#F1F5F9"))))
        story.append(Spacer(1, 8))

        body_p1 = (
            f"1. WHEREAS an investigation into the commission of cyber financial fraud in connection with "
            f"<b>{case.fir_number}</b> registered at {police_station} is currently in progress, "
            f"wherein the complainant ({case.victim_reference or 'victim'}) was induced by deceptive means into transferring funds "
            f"amounting to <b>{loss_display}</b>, which were subsequently converted into TRC-20 USDT on the TRON blockchain."
        )
        story.append(Paragraph(body_p1, body_style))
        story.append(Spacer(1, 6))

        body_p2 = (
            f"2. AND WHEREAS forensic multi-hop transaction tracing conducted on-chain establishes an <b>accepted attribution hypothesis</b> "
            f"indicating that stolen proceeds were systematically routed and deposited into <b>{target_vasp}</b> "
            f"associated deposit / consolidation wallet address: <b><font name='Courier'>{target_wallet}</font></b>."
        )
        story.append(Paragraph(body_p2, body_style))
        story.append(Spacer(1, 6))

        body_p3 = (
            f"3. AND WHEREAS the production of complete electronic records, subscriber identity details, "
            f"and ledger entries maintained by your organization in respect of the said wallet address is necessary and desirable "
            f"for the purposes of the ongoing criminal investigation under the provisions of Section 94 BNSS, 2023."
        )
        story.append(Paragraph(body_p3, body_style))
        story.append(Spacer(1, 8))

        # -------------------------------------------------------------
        # 5. SPECIFIC PRODUCTION DEMANDS (KYC, LEDGER, LOGS, PRESERVATION)
        # -------------------------------------------------------------
        story.append(Paragraph("<b>THEREFORE, YOU ARE HEREBY REQUISITIONED TO PRODUCE THE FOLLOWING RECORDS:</b>", h1_style))
        story.append(Spacer(1, 4))

        demands = [
            "<b>1. Full Subscriber KYC / Account Identification:</b> Full legal name, date of birth, registered mobile number, email address, physical residential address, submitted national identity documents (PAN, Aadhaar, Passport, or foreign government ID), and biometric / selfie verification records.",
            "<b>2. Account Registration Metadata:</b> Registration date and time, signup IP address, timestamp, device identifier, and operating system / user-agent details.",
            "<b>3. Complete Transaction Ledger & Flow of Funds:</b> Complete deposit and withdrawal history for the subject account from registration to date, including transaction hashes, internal UID / account transfers, fiat currency deposits and withdrawals, and linked payment methods.",
            "<b>4. P2P Counterparties & Off-Ramping Bank Details:</b> If the funds were liquidated via Peer-to-Peer (P2P) trading or bank settlement, furnish counterparty UIDs, beneficiary bank account numbers, IFSC codes, UPI IDs, and proof of payment receipts.",
            "<b>5. Digital Access & Login Audit Trails:</b> Session login/logout logs, IP address access history with port numbers and UTC timestamps, and two-factor authentication (2FA) telephone / authenticator records.",
            "<b>6. Urgent Preservation Request:</b> Under Section 94 BNSS read with Section 106 BNSS, immediately preserve all current account balances, linked accounts, and electronic log data to prevent dissipation of criminal proceeds pending formal attachment / freezing orders.",
        ]

        for demand in demands:
            story.append(Paragraph(demand, list_style))
            story.append(Spacer(1, 4))

        story.append(Spacer(1, 8))

        # -------------------------------------------------------------
        # 6. STATUTORY COMPLIANCE TIMEFRAME & PENAL NOTICE
        # -------------------------------------------------------------
        penal_text = (
            f"<b>NOTICE OF STATUTORY COMPLIANCE:</b><br/>"
            f"Please furnish the requisitioned records electronically in password-protected format within <b>{urgency_hours} hours</b> "
            f"of receipt of this notice to the official police email address: <b>cybercell@{police_station.lower().replace(' ', '')}.gov.in</b>. "
            f"Failure to comply with this lawful requisition without reasonable cause may attract legal proceedings under "
            f"Section 223 / 228 of Bharatiya Nyaya Sanhita, 2023 (BNS)."
        )
        penal_box = Table([[Paragraph(penal_text, body_style)]], colWidths=[532])
        penal_box.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FEF3C7")),
            ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#D97706")),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ]))
        story.append(penal_box)
        story.append(Spacer(1, 14))

        # -------------------------------------------------------------
        # 7. INVESTIGATING OFFICER SIGNATURE & SEAL BLOCK
        # -------------------------------------------------------------
        sig_data = [
            [
                Paragraph("<b>Issued under the Hand and Seal of:</b>", body_style),
                Paragraph("<b>Official Police Station Seal:</b>", body_style),
            ],
            [
                Paragraph(
                    f"<br/><br/>______________________________________<br/>"
                    f"<b>{investigator_name}</b><br/>"
                    f"{investigator_rank}<br/>"
                    f"{police_station}<br/>"
                    f"Badge / Reg No.: POL-{investigator_name[-6:]}",
                    body_style,
                ),
                Paragraph(
                    f"<br/><br/>[ SEAL OF THE INVESTIGATING OFFICER ]<br/>"
                    f"Date of Signing: ____ / ____ / 2026<br/>"
                    f"Location: {police_station}",
                    body_style,
                ),
            ],
        ]
        sig_table = Table(sig_data, colWidths=[300, 232])
        sig_table.setStyle(TableStyle([
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ]))

        story.append(KeepTogether([sig_table, Spacer(1, 10)]))

        # -------------------------------------------------------------
        # 8. DETERMINISTIC REPORT INTEGRITY HASH
        # -------------------------------------------------------------
        hashable_dict = {
            "case_id": case.id,
            "fir_number": case.fir_number,
            "trace_id": trace.id,
            "target_vasp": target_vasp,
            "target_wallet": target_wallet,
            "investigator": investigator_name,
            "urgency_hours": urgency_hours,
            "timestamp": gen_time.isoformat(),
        }
        report_hash = compute_content_hash(hashable_dict)

        hash_footer_data = [[
            Paragraph(
                f"<b>DRAFT NOTICE CONTENT HASH (SHA-256):</b> <font name='Courier' size='7'>{report_hash}</font><br/>"
                f"<font size='6.5' color='#64748B'>Verifiable electronic integrity digest. Notice valid only upon formal execution and officer signature.</font>",
                body_style,
            )
        ]]
        hash_table = Table(hash_footer_data, colWidths=[532])
        hash_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
            ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#CBD5E1")),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(KeepTogether([hash_table]))

        # Build document
        doc.build(story, canvasmaker=BNSSCanvas)
        pdf_bytes = buffer.getvalue()
        buffer.close()

        report_meta = {
            "case_id": case.id,
            "fir_number": case.fir_number,
            "trace_id": trace.id,
            "target_vasp": target_vasp,
            "target_wallet": target_wallet,
            "report_hash": report_hash,
            "file_size_bytes": len(pdf_bytes),
            "generated_at": gen_time.isoformat(),
            "generated_by": investigator_name,
        }

        return pdf_bytes, report_hash, report_meta
