import uuid
from decimal import Decimal
from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    String,
    Numeric,
    Text,
    DateTime,
    Integer,
    JSON,
    ForeignKey,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


def generate_uuid() -> str:
    return str(uuid.uuid4())


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Case(Base):
    __tablename__ = "cases"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    fir_number = Column(String(100), nullable=False, index=True)
    victim_reference = Column(String(100), nullable=True)
    loss_amount_inr = Column(Numeric(precision=15, scale=2), nullable=True)
    ack_number = Column(String(100), nullable=True)
    suspect_wallet = Column(String(255), nullable=True)
    chain = Column(String(50), nullable=False, default="TRON")
    asset = Column(String(50), nullable=False, default="TRC20:USDT")
    status = Column(String(50), nullable=False, default="OPEN", index=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    traces = relationship("Trace", back_populates="case", cascade="all, delete-orphan", lazy="selectin")
    evidence_items = relationship("EvidenceItemModel", back_populates="case", cascade="all, delete-orphan", lazy="selectin")
    audit_events = relationship("AuditEventModel", back_populates="case", cascade="all, delete-orphan", lazy="selectin")
    reports = relationship("ReportModel", back_populates="case", cascade="all, delete-orphan", lazy="selectin")


class Trace(Base):
    __tablename__ = "traces"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    case_id = Column(String(36), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True)
    chain = Column(String(50), nullable=False, default="TRON")
    input_type = Column(String(20), nullable=False, default="address")
    input_value = Column(String(255), nullable=False)
    asset = Column(String(50), nullable=False, default="TRC20:USDT")
    status = Column(String(50), nullable=False, default="QUEUED", index=True)
    max_hops = Column(Integer, nullable=False, default=4)
    min_relevant_usd = Column(Numeric(precision=10, scale=2), nullable=False, default=1.00)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    engine_version = Column(String(50), nullable=False, default="0.1.0")
    config = Column(JSON, nullable=True)
    graph_data = Column(JSON, nullable=True)
    node_count = Column(Integer, nullable=False, default=0)
    edge_count = Column(Integer, nullable=False, default=0)
    pruned_count = Column(Integer, nullable=False, default=0)
    duration_ms = Column(Integer, nullable=True)
    boundary_code = Column(String(50), nullable=True)
    investigator_summary = Column(Text, nullable=True)

    case = relationship("Case", back_populates="traces")
    attributions = relationship("AttributionResult", back_populates="trace", cascade="all, delete-orphan", lazy="selectin")
    evidence_items = relationship("EvidenceItemModel", back_populates="trace", cascade="all, delete-orphan", lazy="selectin")
    reports = relationship("ReportModel", back_populates="trace", cascade="all, delete-orphan", lazy="selectin")


class AttributionResult(Base):
    __tablename__ = "attribution_results"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    trace_id = Column(String(36), ForeignKey("traces.id", ondelete="CASCADE"), nullable=False, index=True)
    vasp_id = Column(String(100), nullable=False)
    vasp_name = Column(String(100), nullable=False)
    candidate_address = Column(String(255), nullable=False)
    confidence = Column(Numeric(precision=5, scale=4), nullable=False)
    confidence_band = Column(String(20), nullable=False)
    direct_tag_score = Column(Numeric(precision=5, scale=4), nullable=False)
    downstream_match_score = Column(Numeric(precision=5, scale=4), nullable=False, default=Decimal("0.0"))
    sweep_score = Column(Numeric(precision=5, scale=4), nullable=False)
    fan_in_score = Column(Numeric(precision=5, scale=4), nullable=False)
    temporal_score = Column(Numeric(precision=5, scale=4), nullable=False)
    verification_status = Column(String(50), nullable=False, default="VERIFIED")
    explanation = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    trace = relationship("Trace", back_populates="attributions")


class EvidenceItemModel(Base):
    __tablename__ = "evidence_items"

    id = Column(String(64), primary_key=True)
    case_id = Column(String(36), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True)
    trace_id = Column(String(36), ForeignKey("traces.id", ondelete="CASCADE"), nullable=True, index=True)
    evidence_type = Column(String(50), nullable=False)
    classification = Column(String(20), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    source = Column(String(100), nullable=False)
    source_reference = Column(String(255), nullable=True)
    payload = Column(JSON, nullable=False)
    parent_evidence_ids = Column(JSON, nullable=True)
    content_hash = Column(String(64), nullable=False, index=True)
    engine_version = Column(String(20), nullable=False, default="0.1.0")
    configuration_snapshot = Column(JSON, nullable=True)
    collected_at = Column(DateTime(timezone=True), nullable=False)
    analysis_timestamp = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    case = relationship("Case", back_populates="evidence_items")
    trace = relationship("Trace", back_populates="evidence_items")


class AuditEventModel(Base):
    __tablename__ = "audit_events"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    case_id = Column(String(36), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True)
    trace_id = Column(String(36), ForeignKey("traces.id", ondelete="SET NULL"), nullable=True, index=True)
    actor_id = Column(String(100), nullable=False, default="investigator")
    event_type = Column(String(50), nullable=False, index=True)
    action_summary = Column(Text, nullable=False)
    metadata_json = Column(JSON, nullable=True)
    content_hash = Column(String(64), nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    case = relationship("Case", back_populates="audit_events")


class ReportModel(Base):
    __tablename__ = "reports"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    case_id = Column(String(36), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True)
    trace_id = Column(String(36), ForeignKey("traces.id", ondelete="SET NULL"), nullable=True, index=True)
    report_type = Column(String(50), nullable=False, index=True)  # EVIDENCE_DOSSIER, SECTION_94_BNSS
    title = Column(String(255), nullable=False)
    file_path = Column(String(512), nullable=False)
    file_size_bytes = Column(Integer, nullable=False, default=0)
    content_hash = Column(String(64), nullable=False, index=True)  # SHA-256
    generated_by = Column(String(100), nullable=False, default="investigator")
    metadata_json = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    case = relationship("Case", back_populates="reports")
    trace = relationship("Trace", back_populates="reports")

