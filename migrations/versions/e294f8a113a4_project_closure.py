"""Track project closure and exactly-once unused budget refunds."""

import sqlalchemy as sa
from alembic import op

revision = "e294f8a113a4"
down_revision = "cf1c620a26a3"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("projects") as batch:
        batch.add_column(
            sa.Column("closed", sa.Boolean(), server_default=sa.false(), nullable=False)
        )
        batch.add_column(
            sa.Column("refunded_credits", sa.BigInteger(), server_default="0", nullable=False)
        )


def downgrade():
    with op.batch_alter_table("projects") as batch:
        batch.drop_column("refunded_credits")
        batch.drop_column("closed")
