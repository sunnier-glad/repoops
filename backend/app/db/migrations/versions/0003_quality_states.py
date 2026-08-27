"""Create pull request, workflow run and release state tables."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_quality_states"
down_revision: str | Sequence[str] | None = "0002_repositories_webhooks"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "pull_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("repository_id", sa.Integer(), nullable=False),
        sa.Column("github_id", sa.BigInteger(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("state", sa.String(length=30), nullable=False),
        sa.Column("head_branch", sa.String(length=255), nullable=True),
        sa.Column("head_sha", sa.String(length=100), nullable=True),
        sa.Column("author_login", sa.String(length=100), nullable=True),
        sa.Column("html_url", sa.String(length=500), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["repository_id"], ["repositories.id"]),
        sa.UniqueConstraint("repository_id", "number", name="uq_pull_requests_number"),
    )
    op.create_index("ix_pull_requests_repository_id", "pull_requests", ["repository_id"])
    op.create_table(
        "workflow_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("repository_id", sa.Integer(), nullable=False),
        sa.Column("github_id", sa.BigInteger(), nullable=False),
        sa.Column("workflow_name", sa.String(length=200), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("conclusion", sa.String(length=30), nullable=True),
        sa.Column("branch", sa.String(length=255), nullable=True),
        sa.Column("commit_sha", sa.String(length=100), nullable=True),
        sa.Column("html_url", sa.String(length=500), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["repository_id"], ["repositories.id"]),
        sa.UniqueConstraint("repository_id", "github_id", name="uq_workflow_runs_github"),
    )
    op.create_index("ix_workflow_runs_repository_id", "workflow_runs", ["repository_id"])
    op.create_table(
        "releases",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("repository_id", sa.Integer(), nullable=False),
        sa.Column("github_id", sa.BigInteger(), nullable=False),
        sa.Column("tag_name", sa.String(length=200), nullable=False),
        sa.Column("name", sa.String(length=500), nullable=True),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("html_url", sa.String(length=500), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["repository_id"], ["repositories.id"]),
        sa.UniqueConstraint("repository_id", "github_id", name="uq_releases_github"),
    )
    op.create_index("ix_releases_repository_id", "releases", ["repository_id"])


def downgrade() -> None:
    op.drop_index("ix_releases_repository_id", table_name="releases")
    op.drop_table("releases")
    op.drop_index("ix_workflow_runs_repository_id", table_name="workflow_runs")
    op.drop_table("workflow_runs")
    op.drop_index("ix_pull_requests_repository_id", table_name="pull_requests")
    op.drop_table("pull_requests")
