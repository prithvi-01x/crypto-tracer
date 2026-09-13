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
    Index,
    Boolean,
)
from sqlalchemy.sql import false
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB as PG_JSONB
from sqlalchemy.orm import declarative_base, relationship

from backend.app.config import (
    DEFAULT_TENANT_ID,
    DEFAULT_DISTRICT_ID,
    DEFAULT_POLICE_STATION_ID,
)
from backend.app.core.crypto import EncryptedString, EncryptedText

Base = declarative_base()

# Dialect-agnostic type definitions (compiles to UUID/JSONB on Postgres, String/JSON on SQLite)
UUID_TYPE = String(36).with_variant(PG_UUID(as_uuid=False), "postgresql")
JSONB_TYPE = JSON().with_variant(PG_JSONB, "postgresql")


def generate_uuid() -> str:
    return str(uuid.uuid4())


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Case(Base):
    __tablename__ = "cases"

    id = Column(UUID_TYPE, primary_key=True, default=generate_uuid)
    tenant_id = Column(String(100), nullable=False, default=DEFAULT_TENANT_ID, server_default=DEFAULT_TENANT_ID, index=True)
    district_id = Column(String(100), nullable=False, default=DEFAULT_DISTRICT_ID, server_default=DEFAULT_DISTRICT_ID, index=True)
    police_station_id = Column(String(100), nullable=False, default=DEFAULT_POLICE_STATION_ID, server_default=DEFAULT_POLICE_STATION_ID, index=True)
    fir_number = Column(String(100), nullable=False, index=True)
    victim_reference = Column(EncryptedString, nullable=True)
    loss_amount_inr = Column(Numeric(precision=15, scale=2), nullable=True)
    ack_number = Column(EncryptedString, nullable=True)
    suspect_wallet = Column(String(255), nullable=True)
    chain = Column(String(50), nullable=False, default="TRON")
    asset = Column(String(50), nullable=False, default="TRC20:USDT")
    status = Column(String(50), nullable=False, default="OPEN", index=True)
    notes = Column(EncryptedText, nullable=True)

    # Soft-delete tracking (Feature 17)
    is_deleted = Column(Boolean, nullable=False, default=False, server_default=false(), index=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    __table_args__ = (
        Index("ix_cases_tenant_created", "tenant_id", "created_at"),
        Index("ix_cases_tenant_fir", "tenant_id", "fir_number"),
        Index("ix_cases_tenant_district", "tenant_id", "district_id"),
        Index("ix_cases_tenant_is_deleted_created", "tenant_id", "is_deleted", "created_at"),
    )

    @property
    def station_id(self) -> str:
        return self.police_station_id

    traces = relationship("Trace", back_populates="case", cascade="all, delete-orphan", lazy="selectin")
    evidence_items = relationship("EvidenceItemModel", back_populates="case", lazy="selectin", passive_deletes="all")
    audit_events = relationship("AuditEventModel", back_populates="case", lazy="selectin", passive_deletes="all")
    reports = relationship("ReportModel", back_populates="case", cascade="all, delete-orphan", lazy="selectin")
    findings = relationship("FindingRecord", back_populates="case", cascade="all, delete-orphan", lazy="selectin")


class Trace(Base):
    __tablename__ = "traces"

    id = Column(UUID_TYPE, primary_key=True, default=generate_uuid)
    case_id = Column(UUID_TYPE, ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id = Column(String(100), nullable=False, default=DEFAULT_TENANT_ID, server_default=DEFAULT_TENANT_ID, index=True)
    district_id = Column(String(100), nullable=False, default=DEFAULT_DISTRICT_ID, server_default=DEFAULT_DISTRICT_ID, index=True)
    police_station_id = Column(String(100), nullable=False, default=DEFAULT_POLICE_STATION_ID, server_default=DEFAULT_POLICE_STATION_ID, index=True)
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
    config = Column(JSONB_TYPE, nullable=True)
    graph_data = Column(JSONB_TYPE, nullable=True)
    node_count = Column(Integer, nullable=False, default=0)
    edge_count = Column(Integer, nullable=False, default=0)
    pruned_count = Column(Integer, nullable=False, default=0)
    duration_ms = Column(Integer, nullable=True)
    boundary_code = Column(String(50), nullable=True)
    investigator_summary = Column(Text, nullable=True)
    execution_mode = Column(String(20), nullable=False, default="DEMO")

    # M4 Async Job State & Recovery Columns
    job_id = Column(String(64), nullable=True)
    worker_id = Column(String(100), nullable=True)
    current_hop = Column(Integer, nullable=False, default=0, server_default="0")
    progress_percent = Column(Numeric(precision=5, scale=2), nullable=False, default=0.0, server_default="0.0")
    heartbeat_at = Column(DateTime(timezone=True), nullable=True)
    retry_count = Column(Integer, nullable=False, default=0, server_default="0")
    max_retries = Column(Integer, nullable=False, default=3, server_default="3")
    checkpoint_data = Column(JSONB_TYPE, nullable=True)
    error_message = Column(Text, nullable=True)
    cancelled_at = Column(DateTime(timezone=True), nullable=True)
    cancel_reason = Column(Text, nullable=True)

    __table_args__ = (
        Index("ix_traces_tenant_case", "tenant_id", "case_id"),
        Index("ix_traces_tenant_trace_id", "tenant_id", "id"),
        Index("ix_traces_tenant_case_started", "tenant_id", "case_id", "started_at"),
        Index("ix_traces_graph_data_gin", "graph_data", postgresql_using="gin"),
        Index("ix_traces_job_id", "job_id"),
        Index("ix_traces_status_heartbeat", "status", "heartbeat_at"),
    )

    @property
    def station_id(self) -> str:
        return self.police_station_id

    case = relationship("Case", back_populates="traces")
    attributions = relationship("AttributionResult", back_populates="trace", cascade="all, delete-orphan", lazy="selectin")
    evidence_items = relationship("EvidenceItemModel", back_populates="trace", cascade="all, delete-orphan", lazy="selectin")
    reports = relationship("ReportModel", back_populates="trace", cascade="all, delete-orphan", lazy="selectin")
    findings = relationship("FindingRecord", back_populates="trace", cascade="all, delete-orphan", lazy="selectin")


class AttributionResult(Base):
    __tablename__ = "attribution_results"

    id = Column(UUID_TYPE, primary_key=True, default=generate_uuid)
    trace_id = Column(UUID_TYPE, ForeignKey("traces.id", ondelete="CASCADE"), nullable=False, index=True)
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
    explanation = Column(JSONB_TYPE, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    trace = relationship("Trace", back_populates="attributions")


class EvidenceItemModel(Base):
    __tablename__ = "evidence_items"

    id = Column(String(64), primary_key=True)
    case_id = Column(UUID_TYPE, ForeignKey("cases.id", ondelete="RESTRICT"), nullable=False, index=True)
    trace_id = Column(UUID_TYPE, ForeignKey("traces.id", ondelete="CASCADE"), nullable=True, index=True)
    tenant_id = Column(String(100), nullable=False, default=DEFAULT_TENANT_ID, server_default=DEFAULT_TENANT_ID, index=True)
    district_id = Column(String(100), nullable=False, default=DEFAULT_DISTRICT_ID, server_default=DEFAULT_DISTRICT_ID, index=True)
    police_station_id = Column(String(100), nullable=False, default=DEFAULT_POLICE_STATION_ID, server_default=DEFAULT_POLICE_STATION_ID, index=True)
    evidence_type = Column(String(50), nullable=False)
    classification = Column(String(20), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    source = Column(String(100), nullable=False)
    source_reference = Column(String(255), nullable=True)
    payload = Column(JSONB_TYPE, nullable=False)
    parent_evidence_ids = Column(JSONB_TYPE, nullable=True)
    content_hash = Column(String(64), nullable=False, index=True)
    engine_version = Column(String(20), nullable=False, default="0.1.0")
    configuration_snapshot = Column(JSONB_TYPE, nullable=True)
    collected_at = Column(DateTime(timezone=True), nullable=False)
    analysis_timestamp = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    # M5 Cryptographic Hash Chain Ledger
    sequence_number = Column(Integer, nullable=False, default=0, server_default="0")
    prev_hash = Column(String(64), nullable=False, default="", server_default="")
    current_hash = Column(String(64), nullable=False, default="", server_default="")
    canonical_payload_hash = Column(String(64), nullable=False, default="", server_default="")
    actor_id = Column(String(100), nullable=False, default="system", server_default="system")

    __table_args__ = (
        Index("ix_evidence_tenant_case", "tenant_id", "case_id"),
        Index("ix_evidence_tenant_trace", "tenant_id", "trace_id"),
        Index("ix_evidence_tenant_trace_created", "tenant_id", "trace_id", "created_at"),
        Index("ix_evidence_payload_gin", "payload", postgresql_using="gin"),
        Index("ix_evidence_items_sequence_number", "sequence_number"),
        Index("ix_evidence_items_current_hash", "current_hash"),
        Index("ix_evidence_case_sequence", "case_id", "sequence_number"),
    )

    @property
    def station_id(self) -> str:
        return self.police_station_id

    @property
    def prev_event_hash(self) -> str:
        return self.prev_hash

    case = relationship("Case", back_populates="evidence_items")
    trace = relationship("Trace", back_populates="evidence_items")


class AuditEventModel(Base):
    __tablename__ = "audit_events"

    id = Column(UUID_TYPE, primary_key=True, default=generate_uuid)
    case_id = Column(UUID_TYPE, ForeignKey("cases.id", ondelete="RESTRICT"), nullable=False, index=True)
    trace_id = Column(UUID_TYPE, ForeignKey("traces.id", ondelete="SET NULL"), nullable=True, index=True)
    tenant_id = Column(String(100), nullable=False, default=DEFAULT_TENANT_ID, server_default=DEFAULT_TENANT_ID, index=True)
    district_id = Column(String(100), nullable=False, default=DEFAULT_DISTRICT_ID, server_default=DEFAULT_DISTRICT_ID, index=True)
    police_station_id = Column(String(100), nullable=False, default=DEFAULT_POLICE_STATION_ID, server_default=DEFAULT_POLICE_STATION_ID, index=True)
    actor_id = Column(String(100), nullable=False, default="investigator")
    event_type = Column(String(50), nullable=False, index=True)
    action_summary = Column(Text, nullable=False)
    metadata_json = Column(JSONB_TYPE, nullable=True)
    content_hash = Column(String(64), nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    # M5 Cryptographic Hash Chain Ledger
    sequence_number = Column(Integer, nullable=False, default=0, server_default="0")
    prev_hash = Column(String(64), nullable=False, default="", server_default="")
    current_hash = Column(String(64), nullable=False, default="", server_default="")
    canonical_payload_hash = Column(String(64), nullable=False, default="", server_default="")

    __table_args__ = (
        Index("ix_audit_tenant_case", "tenant_id", "case_id"),
        Index("ix_audit_events_sequence_number", "sequence_number"),
        Index("ix_audit_events_current_hash", "current_hash"),
        Index("ix_audit_case_sequence", "case_id", "sequence_number"),
    )

    @property
    def station_id(self) -> str:
        return self.police_station_id

    @property
    def prev_event_hash(self) -> str:
        return self.prev_hash

    case = relationship("Case", back_populates="audit_events")


class ReportModel(Base):
    __tablename__ = "reports"

    id = Column(UUID_TYPE, primary_key=True, default=generate_uuid)
    case_id = Column(UUID_TYPE, ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True)
    trace_id = Column(UUID_TYPE, ForeignKey("traces.id", ondelete="SET NULL"), nullable=True, index=True)
    tenant_id = Column(String(100), nullable=False, default=DEFAULT_TENANT_ID, server_default=DEFAULT_TENANT_ID, index=True)
    district_id = Column(String(100), nullable=False, default=DEFAULT_DISTRICT_ID, server_default=DEFAULT_DISTRICT_ID, index=True)
    police_station_id = Column(String(100), nullable=False, default=DEFAULT_POLICE_STATION_ID, server_default=DEFAULT_POLICE_STATION_ID, index=True)
    report_type = Column(String(50), nullable=False, index=True)  # EVIDENCE_DOSSIER, SECTION_94_BNSS
    title = Column(String(255), nullable=False)
    file_path = Column(String(512), nullable=False)
    file_size_bytes = Column(Integer, nullable=False, default=0)
    content_hash = Column(String(64), nullable=False, index=True)  # SHA-256
    generated_by = Column(String(100), nullable=False, default="investigator")
    metadata_json = Column(JSONB_TYPE, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    # M5 Async PDF Generation & Storage Vault
    status = Column(String(50), nullable=False, default="COMPLETED", server_default="COMPLETED")
    storage_backend = Column(String(50), nullable=False, default="LOCAL", server_default="LOCAL")
    storage_path = Column(String(512), nullable=True)
    s3_key = Column(String(512), nullable=True)
    file_hash = Column(String(64), nullable=True)
    job_id = Column(String(64), nullable=True)
    error_message = Column(Text, nullable=True)
    encryption_metadata = Column(JSONB_TYPE, nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_reports_tenant_case", "tenant_id", "case_id"),
        Index("ix_reports_tenant_report_id", "tenant_id", "id"),
        Index("ix_reports_status", "status"),
        Index("ix_reports_s3_key", "s3_key"),
        Index("ix_reports_file_hash", "file_hash"),
        Index("ix_reports_job_id", "job_id"),
    )

    @property
    def station_id(self) -> str:
        return self.police_station_id

    @property
    def storage_key(self) -> str:
        return self.s3_key or self.storage_path or self.file_path

    case = relationship("Case", back_populates="reports")
    trace = relationship("Trace", back_populates="reports")


class FindingRecord(Base):
    __tablename__ = "findings"

    id = Column(String(64), primary_key=True)
    case_id = Column(UUID_TYPE, ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True)
    trace_id = Column(UUID_TYPE, ForeignKey("traces.id", ondelete="CASCADE"), nullable=True, index=True)
    tenant_id = Column(String(100), nullable=False, default=DEFAULT_TENANT_ID, server_default=DEFAULT_TENANT_ID, index=True)
    district_id = Column(String(100), nullable=False, default=DEFAULT_DISTRICT_ID, server_default=DEFAULT_DISTRICT_ID, index=True)
    police_station_id = Column(String(100), nullable=False, default=DEFAULT_POLICE_STATION_ID, server_default=DEFAULT_POLICE_STATION_ID, index=True)
    finding_type = Column(String(50), nullable=False, index=True)
    severity = Column(String(20), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    source_signal = Column(String(100), nullable=False)
    confidence = Column(Numeric(precision=5, scale=4), nullable=True)
    related_address = Column(String(255), nullable=True)
    related_tx_hash = Column(String(255), nullable=True)
    related_vasp = Column(String(100), nullable=True)
    evidence_refs = Column(JSONB_TYPE, nullable=True)
    status = Column(String(20), nullable=False, default="OPEN", index=True)  # OPEN, REVIEWED, DISMISSED
    reviewed_by = Column(String(100), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    review_notes = Column(Text, nullable=True)
    graph_node_id = Column(String(255), nullable=True)
    graph_edge_id = Column(String(255), nullable=True)
    raw_payload = Column(JSONB_TYPE, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    __table_args__ = (
        Index("ix_findings_tenant_case", "tenant_id", "case_id"),
        Index("ix_findings_tenant_trace", "tenant_id", "trace_id"),
        Index("ix_findings_tenant_case_created", "tenant_id", "case_id", "created_at"),
    )

    @property
    def station_id(self) -> str:
        return self.police_station_id

    case = relationship("Case", back_populates="findings")
    trace = relationship("Trace", back_populates="findings")
