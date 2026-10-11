"""Add task execution leases and lifecycle events."""

import sqlalchemy as sa
from alembic import op

revision = "6d78c7cd9044"
down_revision = "f30efb85c0bc"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("tasks") as batch:
        batch.add_column(sa.Column("lease_token_hash", sa.String(64), nullable=True))
        batch.add_column(sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("attempts", sa.Integer(), server_default="0", nullable=False))
        batch.create_unique_constraint("uq_tasks_lease_token_hash", ["lease_token_hash"])
        batch.create_check_constraint("nonnegative_task_attempts", "attempts >= 0")
        batch.create_index("ix_tasks_inbox", ["agent_id", "state", "lease_expires_at"])
    # Old workers have no execution token. Preserve reservations but allow reclaim.
    op.execute("UPDATE tasks SET lease_expires_at = CURRENT_TIMESTAMP WHERE state = 'running'")
    op.create_table(
        "task_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("task_id", sa.String(36), sa.ForeignKey("tasks.id"), nullable=False),
        sa.Column("actor_owner_id", sa.String(36), sa.ForeignKey("owners.id"), nullable=False),
        sa.Column("actor_agent_id", sa.String(36), sa.ForeignKey("agents.id"), nullable=True),
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_task_events_task_id", "task_events", ["task_id"])


def downgrade():
    op.drop_index("ix_task_events_task_id", table_name="task_events")
    op.drop_table("task_events")
    with op.batch_alter_table("tasks") as batch:
        batch.drop_index("ix_tasks_inbox")
        batch.drop_constraint("uq_tasks_lease_token_hash", type_="unique")
        batch.drop_constraint("nonnegative_task_attempts", type_="check")
        batch.drop_column("attempts")
        batch.drop_column("lease_expires_at")
        batch.drop_column("lease_token_hash")
