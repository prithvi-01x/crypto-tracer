"""0001_initial_schema

Revision ID: 0001
Revises: 
Create Date: 2026-09-13 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Dialect detection via context (works in both online and offline modes)
    ctx = op.get_context()
    is_postgres = ctx.dialect.name == "postgresql"

    # Dialect-adaptive column types
    uuid_type = sa.String(length=36).with_variant(postgresql.UUID(as_uuid=False), "postgresql")
    json_type = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")

    # 1. cases table
    op.create_table(
        "cases",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("tenant_id", sa.String(length=100), server_default="TN-STATE", nullable=False),
        sa.Column("district_id", sa.String(length=100), server_default="CYBER-CRIME-HQ", nullable=False),
        sa.Column("police_station_id", sa.String(length=100), server_default="PS-CENTRAL", nullable=False),
        sa.Column("fir_number", sa.String(length=100), nullable=False),
        sa.Column("victim_reference", sa.Text(), nullable=True),
        sa.Column("loss_amount_inr", sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column("ack_number", sa.Text(), nullable=True),
        sa.Column("suspect_wallet", sa.String(length=255), nullable=True),
        sa.Column("chain", sa.String(length=50), server_default="TRON", nullable=False),
        sa.Column("asset", sa.String(length=50), server_default="TRC20:USDT", nullable=False),
        sa.Column("status", sa.String(length=50), server_default="OPEN", nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_cases_tenant_id", "cases", ["tenant_id"], unique=False)
    op.create_index("ix_cases_district_id", "cases", ["district_id"], unique=False)
    op.create_index("ix_cases_police_station_id", "cases", ["police_station_id"], unique=False)
    op.create_index("ix_cases_fir_number", "cases", ["fir_number"], unique=False)
    op.create_index("ix_cases_status", "cases", ["status"], unique=False)
    op.create_index("ix_cases_is_deleted", "cases", ["is_deleted"], unique=False)
    op.create_index("ix_cases_tenant_created", "cases", ["tenant_id", "created_at"], unique=False)
    op.create_index("ix_cases_tenant_fir", "cases", ["tenant_id", "fir_number"], unique=False)
    op.create_index("ix_cases_tenant_district", "cases", ["tenant_id", "district_id"], unique=False)
    op.create_index("ix_cases_tenant_is_deleted_created", "cases", ["tenant_id", "is_deleted", "created_at"], unique=False)

    # 2. traces table
    op.create_table(
        "traces",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("case_id", uuid_type, nullable=False),
        sa.Column("tenant_id", sa.String(length=100), server_default="TN-STATE", nullable=False),
        sa.Column("district_id", sa.String(length=100), server_default="CYBER-CRIME-HQ", nullable=False),
        sa.Column("police_station_id", sa.String(length=100), server_default="PS-CENTRAL", nullable=False),
        sa.Column("chain", sa.String(length=50), server_default="TRON", nullable=False),
        sa.Column("input_type", sa.String(length=20), server_default="address", nullable=False),
        sa.Column("input_value", sa.String(length=255), nullable=False),
        sa.Column("asset", sa.String(length=50), server_default="TRC20:USDT", nullable=False),
        sa.Column("status", sa.String(length=50), server_default="QUEUED", nullable=False),
        sa.Column("max_hops", sa.Integer(), server_default="4", nullable=False),
        sa.Column("min_relevant_usd", sa.Numeric(precision=10, scale=2), server_default="1.00", nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("engine_version", sa.String(length=50), server_default="0.1.0", nullable=False),
        sa.Column("config", json_type, nullable=True),
        sa.Column("graph_data", json_type, nullable=True),
        sa.Column("node_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("edge_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("pruned_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("boundary_code", sa.String(length=50), nullable=True),
        sa.Column("investigator_summary", sa.Text(), nullable=True),
        sa.Column("execution_mode", sa.String(length=20), server_default="DEMO", nullable=False),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_traces_case_id", "traces", ["case_id"], unique=False)
    op.create_index("ix_traces_tenant_id", "traces", ["tenant_id"], unique=False)
    op.create_index("ix_traces_district_id", "traces", ["district_id"], unique=False)
    op.create_index("ix_traces_police_station_id", "traces", ["police_station_id"], unique=False)
    op.create_index("ix_traces_status", "traces", ["status"], unique=False)
    op.create_index("ix_traces_tenant_case", "traces", ["tenant_id", "case_id"], unique=False)
    op.create_index("ix_traces_tenant_trace_id", "traces", ["tenant_id", "id"], unique=False)
    op.create_index("ix_traces_tenant_case_started", "traces", ["tenant_id", "case_id", "started_at"], unique=False)
    op.create_index("ix_traces_graph_data_gin", "traces", ["graph_data"], postgresql_using="gin")

    # 3. attribution_results table
    op.create_table(
        "attribution_results",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("trace_id", uuid_type, nullable=False),
        sa.Column("vasp_id", sa.String(length=100), nullable=False),
        sa.Column("vasp_name", sa.String(length=100), nullable=False),
        sa.Column("candidate_address", sa.String(length=255), nullable=False),
        sa.Column("confidence", sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column("confidence_band", sa.String(length=20), nullable=False),
        sa.Column("direct_tag_score", sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column("downstream_match_score", sa.Numeric(precision=5, scale=4), server_default="0.0", nullable=False),
        sa.Column("sweep_score", sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column("fan_in_score", sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column("temporal_score", sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column("verification_status", sa.String(length=50), server_default="VERIFIED", nullable=False),
        sa.Column("explanation", json_type, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["trace_id"], ["traces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_attribution_results_trace_id", "attribution_results", ["trace_id"], unique=False)

    # 4. evidence_items table (Law enforcement evidentiary immutability: ondelete RESTRICT on case_id)
    op.create_table(
        "evidence_items",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("case_id", uuid_type, nullable=False),
        sa.Column("trace_id", uuid_type, nullable=True),
        sa.Column("tenant_id", sa.String(length=100), server_default="TN-STATE", nullable=False),
        sa.Column("district_id", sa.String(length=100), server_default="CYBER-CRIME-HQ", nullable=False),
        sa.Column("police_station_id", sa.String(length=100), server_default="PS-CENTRAL", nullable=False),
        sa.Column("evidence_type", sa.String(length=50), nullable=False),
        sa.Column("classification", sa.String(length=20), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("source", sa.String(length=100), nullable=False),
        sa.Column("source_reference", sa.String(length=255), nullable=True),
        sa.Column("payload", json_type, nullable=False),
        sa.Column("parent_evidence_ids", json_type, nullable=True),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("engine_version", sa.String(length=20), server_default="0.1.0", nullable=False),
        sa.Column("configuration_snapshot", json_type, nullable=True),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("analysis_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["trace_id"], ["traces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_evidence_items_case_id", "evidence_items", ["case_id"], unique=False)
    op.create_index("ix_evidence_items_trace_id", "evidence_items", ["trace_id"], unique=False)
    op.create_index("ix_evidence_items_tenant_id", "evidence_items", ["tenant_id"], unique=False)
    op.create_index("ix_evidence_items_district_id", "evidence_items", ["district_id"], unique=False)
    op.create_index("ix_evidence_items_police_station_id", "evidence_items", ["police_station_id"], unique=False)
    op.create_index("ix_evidence_items_classification", "evidence_items", ["classification"], unique=False)
    op.create_index("ix_evidence_items_content_hash", "evidence_items", ["content_hash"], unique=False)
    op.create_index("ix_evidence_tenant_case", "evidence_items", ["tenant_id", "case_id"], unique=False)
    op.create_index("ix_evidence_tenant_trace", "evidence_items", ["tenant_id", "trace_id"], unique=False)
    op.create_index("ix_evidence_tenant_trace_created", "evidence_items", ["tenant_id", "trace_id", "created_at"], unique=False)
    op.create_index("ix_evidence_payload_gin", "evidence_items", ["payload"], postgresql_using="gin")

    # 5. audit_events table (Evidentiary immutability: ondelete RESTRICT on case_id)
    op.create_table(
        "audit_events",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("case_id", uuid_type, nullable=False),
        sa.Column("trace_id", uuid_type, nullable=True),
        sa.Column("tenant_id", sa.String(length=100), server_default="TN-STATE", nullable=False),
        sa.Column("district_id", sa.String(length=100), server_default="CYBER-CRIME-HQ", nullable=False),
        sa.Column("police_station_id", sa.String(length=100), server_default="PS-CENTRAL", nullable=False),
        sa.Column("actor_id", sa.String(length=100), server_default="investigator", nullable=False),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("action_summary", sa.Text(), nullable=False),
        sa.Column("metadata_json", json_type, nullable=True),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["trace_id"], ["traces.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_events_case_id", "audit_events", ["case_id"], unique=False)
    op.create_index("ix_audit_events_trace_id", "audit_events", ["trace_id"], unique=False)
    op.create_index("ix_audit_events_tenant_id", "audit_events", ["tenant_id"], unique=False)
    op.create_index("ix_audit_events_district_id", "audit_events", ["district_id"], unique=False)
    op.create_index("ix_audit_events_police_station_id", "audit_events", ["police_station_id"], unique=False)
    op.create_index("ix_audit_events_event_type", "audit_events", ["event_type"], unique=False)
    op.create_index("ix_audit_tenant_case", "audit_events", ["tenant_id", "case_id"], unique=False)

    # 6. reports table
    op.create_table(
        "reports",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("case_id", uuid_type, nullable=False),
        sa.Column("trace_id", uuid_type, nullable=True),
        sa.Column("tenant_id", sa.String(length=100), server_default="TN-STATE", nullable=False),
        sa.Column("district_id", sa.String(length=100), server_default="CYBER-CRIME-HQ", nullable=False),
        sa.Column("police_station_id", sa.String(length=100), server_default="PS-CENTRAL", nullable=False),
        sa.Column("report_type", sa.String(length=50), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("file_path", sa.String(length=512), nullable=False),
        sa.Column("file_size_bytes", sa.Integer(), server_default="0", nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("generated_by", sa.String(length=100), server_default="investigator", nullable=False),
        sa.Column("metadata_json", json_type, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["trace_id"], ["traces.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_reports_case_id", "reports", ["case_id"], unique=False)
    op.create_index("ix_reports_trace_id", "reports", ["trace_id"], unique=False)
    op.create_index("ix_reports_tenant_id", "reports", ["tenant_id"], unique=False)
    op.create_index("ix_reports_district_id", "reports", ["district_id"], unique=False)
    op.create_index("ix_reports_police_station_id", "reports", ["police_station_id"], unique=False)
    op.create_index("ix_reports_report_type", "reports", ["report_type"], unique=False)
    op.create_index("ix_reports_content_hash", "reports", ["content_hash"], unique=False)
    op.create_index("ix_reports_tenant_case", "reports", ["tenant_id", "case_id"], unique=False)
    op.create_index("ix_reports_tenant_report_id", "reports", ["tenant_id", "id"], unique=False)

    # 7. findings table
    op.create_table(
        "findings",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("case_id", uuid_type, nullable=False),
        sa.Column("trace_id", uuid_type, nullable=True),
        sa.Column("tenant_id", sa.String(length=100), server_default="TN-STATE", nullable=False),
        sa.Column("district_id", sa.String(length=100), server_default="CYBER-CRIME-HQ", nullable=False),
        sa.Column("police_station_id", sa.String(length=100), server_default="PS-CENTRAL", nullable=False),
        sa.Column("finding_type", sa.String(length=50), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("source_signal", sa.String(length=100), nullable=False),
        sa.Column("confidence", sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column("related_address", sa.String(length=255), nullable=True),
        sa.Column("related_tx_hash", sa.String(length=255), nullable=True),
        sa.Column("related_vasp", sa.String(length=100), nullable=True),
        sa.Column("evidence_refs", json_type, nullable=True),
        sa.Column("status", sa.String(length=20), server_default="OPEN", nullable=False),
        sa.Column("reviewed_by", sa.String(length=100), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_notes", sa.Text(), nullable=True),
        sa.Column("graph_node_id", sa.String(length=255), nullable=True),
        sa.Column("graph_edge_id", sa.String(length=255), nullable=True),
        sa.Column("raw_payload", json_type, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["trace_id"], ["traces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_findings_case_id", "findings", ["case_id"], unique=False)
    op.create_index("ix_findings_trace_id", "findings", ["trace_id"], unique=False)
    op.create_index("ix_findings_tenant_id", "findings", ["tenant_id"], unique=False)
    op.create_index("ix_findings_district_id", "findings", ["district_id"], unique=False)
    op.create_index("ix_findings_police_station_id", "findings", ["police_station_id"], unique=False)
    op.create_index("ix_findings_finding_type", "findings", ["finding_type"], unique=False)
    op.create_index("ix_findings_severity", "findings", ["severity"], unique=False)
    op.create_index("ix_findings_status", "findings", ["status"], unique=False)
    op.create_index("ix_findings_tenant_case", "findings", ["tenant_id", "case_id"], unique=False)
    op.create_index("ix_findings_tenant_trace", "findings", ["tenant_id", "trace_id"], unique=False)
    op.create_index("ix_findings_tenant_case_created", "findings", ["tenant_id", "case_id", "created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_evidence_payload_gin", table_name="evidence_items")
    op.drop_index("ix_traces_graph_data_gin", table_name="traces")
    op.drop_table("findings")
    op.drop_table("reports")
    op.drop_table("audit_events")
    op.drop_table("evidence_items")
    op.drop_table("attribution_results")
    op.drop_table("traces")
    op.drop_table("cases")
