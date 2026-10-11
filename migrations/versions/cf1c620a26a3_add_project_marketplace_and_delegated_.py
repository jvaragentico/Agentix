"""Add project marketplace and delegated AI budgets."""

import sqlalchemy as sa
from alembic import op

revision = "cf1c620a26a3"
down_revision = "6d78c7cd9044"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("agents") as batch:
        batch.add_column(
            sa.Column("project_allowance", sa.BigInteger(), server_default="0", nullable=False)
        )
        batch.add_column(
            sa.Column("project_spent", sa.BigInteger(), server_default="0", nullable=False)
        )
        batch.create_check_constraint(
            "agent_allowance", "project_allowance >= 0 AND project_spent >= 0"
        )
    with op.batch_alter_table("projects") as batch:
        batch.add_column(sa.Column("description", sa.Text(), server_default="", nullable=False))
        batch.add_column(
            sa.Column("required_skills", sa.JSON(), server_default="[]", nullable=False)
        )
        batch.add_column(
            sa.Column("published", sa.Boolean(), server_default=sa.false(), nullable=False)
        )
        batch.add_column(sa.Column("posted_by_agent_id", sa.String(36), nullable=True))
        batch.create_foreign_key(
            "fk_project_posting_agent", "agents", ["posted_by_agent_id"], ["id"]
        )


def downgrade():
    with op.batch_alter_table("projects") as batch:
        batch.drop_constraint("fk_project_posting_agent", type_="foreignkey")
        batch.drop_column("posted_by_agent_id")
        batch.drop_column("published")
        batch.drop_column("required_skills")
        batch.drop_column("description")
    with op.batch_alter_table("agents") as batch:
        batch.drop_constraint("agent_allowance", type_="check")
        batch.drop_column("project_spent")
        batch.drop_column("project_allowance")
