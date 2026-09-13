"""0003_evidence_hash_chain_and_reports

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-13 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    ctx = op.get_context()
    is_postgres = ctx.dialect.name == "postgresql"

    json_type = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")

    # 1. Audit events cryptographic hash chain columns & indexes
    with op.batch_alter_table("audit_events") as batch_op:
        batch_op.add_column(sa.Column("sequence_number", sa.Integer(), server_default="0", nullable=False))
        batch_op.add_column(sa.Column("prev_hash", sa.String(length=64), server_default="", nullable=False))
        batch_op.add_column(sa.Column("current_hash", sa.String(length=64), server_default="", nullable=False))
        batch_op.add_column(sa.Column("canonical_payload_hash", sa.String(length=64), server_default="", nullable=False))
        batch_op.create_index("ix_audit_events_sequence_number", ["sequence_number"], unique=False)
        batch_op.create_index("ix_audit_events_current_hash", ["current_hash"], unique=False)
        batch_op.create_index("ix_audit_case_sequence", ["case_id", "sequence_number"], unique=False)

    # 2. Evidence items cryptographic hash chain columns & indexes
    with op.batch_alter_table("evidence_items") as batch_op:
        batch_op.add_column(sa.Column("sequence_number", sa.Integer(), server_default="0", nullable=False))
        batch_op.add_column(sa.Column("prev_hash", sa.String(length=64), server_default="", nullable=False))
        batch_op.add_column(sa.Column("current_hash", sa.String(length=64), server_default="", nullable=False))
        batch_op.add_column(sa.Column("canonical_payload_hash", sa.String(length=64), server_default="", nullable=False))
        batch_op.add_column(sa.Column("actor_id", sa.String(length=100), server_default="system", nullable=False))
        batch_op.create_index("ix_evidence_items_sequence_number", ["sequence_number"], unique=False)
        batch_op.create_index("ix_evidence_items_current_hash", ["current_hash"], unique=False)
        batch_op.create_index("ix_evidence_case_sequence", ["case_id", "sequence_number"], unique=False)

    # 3. Reports vault & async job state columns & indexes
    with op.batch_alter_table("reports") as batch_op:
        batch_op.add_column(sa.Column("status", sa.String(length=50), server_default="COMPLETED", nullable=False))
        batch_op.add_column(sa.Column("storage_backend", sa.String(length=50), server_default="LOCAL", nullable=False))
        batch_op.add_column(sa.Column("storage_path", sa.String(length=512), nullable=True))
        batch_op.add_column(sa.Column("s3_key", sa.String(length=512), nullable=True))
        batch_op.add_column(sa.Column("file_hash", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("job_id", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("error_message", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("encryption_metadata", json_type, nullable=True))
        batch_op.add_column(sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.create_index("ix_reports_status", ["status"], unique=False)
        batch_op.create_index("ix_reports_s3_key", ["s3_key"], unique=False)
        batch_op.create_index("ix_reports_file_hash", ["file_hash"], unique=False)
        batch_op.create_index("ix_reports_job_id", ["job_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("reports") as batch_op:
        batch_op.drop_index("ix_reports_job_id")
        batch_op.drop_index("ix_reports_file_hash")
        batch_op.drop_index("ix_reports_s3_key")
        batch_op.drop_index("ix_reports_status")
        batch_op.drop_column("completed_at")
        batch_op.drop_column("encryption_metadata")
        batch_op.drop_column("error_message")
        batch_op.drop_column("job_id")
        batch_op.drop_column("file_hash")
        batch_op.drop_column("s3_key")
        batch_op.drop_column("storage_path")
        batch_op.drop_column("storage_backend")
        batch_op.drop_column("status")

    with op.batch_alter_table("evidence_items") as batch_op:
        batch_op.drop_index("ix_evidence_case_sequence")
        batch_op.drop_index("ix_evidence_items_current_hash")
        batch_op.drop_index("ix_evidence_items_sequence_number")
        batch_op.drop_column("actor_id")
        batch_op.drop_column("canonical_payload_hash")
        batch_op.drop_column("current_hash")
        batch_op.drop_column("prev_hash")
        batch_op.drop_column("sequence_number")

    with op.batch_alter_table("audit_events") as batch_op:
        batch_op.drop_index("ix_audit_case_sequence")
        batch_op.drop_index("ix_audit_events_current_hash")
        batch_op.drop_index("ix_audit_events_sequence_number")
        batch_op.drop_column("canonical_payload_hash")
        batch_op.drop_column("current_hash")
        batch_op.drop_column("prev_hash")
        batch_op.drop_column("sequence_number")
