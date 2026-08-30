"""Remove obsolete demo-data flags from quality records."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_remove_demo_flags"
down_revision: str | Sequence[str] | None = "0005_demo_data"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for table in ("pull_requests", "workflow_runs", "releases"):
        with op.batch_alter_table(table) as batch_op:
            batch_op.drop_column("is_demo")


def downgrade() -> None:
    for table in ("releases", "workflow_runs", "pull_requests"):
        with op.batch_alter_table(table) as batch_op:
            batch_op.add_column(
                sa.Column(
                    "is_demo",
                    sa.Boolean(),
                    nullable=False,
                    server_default=sa.false(),
                )
            )
