"""Mark locally generated quality records as demo data."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_demo_data"
down_revision: str | Sequence[str] | None = "0004_jobs_ai"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for table in ("pull_requests", "workflow_runs", "releases"):
        op.add_column(
            table,
            sa.Column("is_demo", sa.Boolean(), nullable=False, server_default=sa.false()),
        )


def downgrade() -> None:
    for table in ("releases", "workflow_runs", "pull_requests"):
        op.drop_column(table, "is_demo")
