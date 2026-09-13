"""0002_async_job_state

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-13 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    ctx = op.get_context()
    is_postgres = ctx.dialect.name == "postgresql"

    json_type = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")

    with op.batch_alter_table("traces") as batch_op:
        batch_op.add_column(sa.Column("job_id", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("worker_id", sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column("current_hop", sa.Integer(), server_default="0", nullable=False))
        batch_op.add_column(sa.Column("progress_percent", sa.Numeric(precision=5, scale=2), server_default="0.0", nullable=False))
        batch_op.add_column(sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("retry_count", sa.Integer(), server_default="0", nullable=False))
        batch_op.add_column(sa.Column("max_retries", sa.Integer(), server_default="3", nullable=False))
        batch_op.add_column(sa.Column("checkpoint_data", json_type, nullable=True))
        batch_op.add_column(sa.Column("error_message", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("cancel_reason", sa.Text(), nullable=True))
        batch_op.create_index("ix_traces_job_id", ["job_id"], unique=False)
        batch_op.create_index("ix_traces_status_heartbeat", ["status", "heartbeat_at"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("traces") as batch_op:
        batch_op.drop_index("ix_traces_status_heartbeat")
        batch_op.drop_index("ix_traces_job_id")
        batch_op.drop_column("cancel_reason")
        batch_op.drop_column("cancelled_at")
        batch_op.drop_column("error_message")
        batch_op.drop_column("checkpoint_data")
        batch_op.drop_column("max_retries")
        batch_op.drop_column("retry_count")
        batch_op.drop_column("heartbeat_at")
        batch_op.drop_column("progress_percent")
        batch_op.drop_column("current_hop")
        batch_op.drop_column("worker_id")
        batch_op.drop_column("job_id")
