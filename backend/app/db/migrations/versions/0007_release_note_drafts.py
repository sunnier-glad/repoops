"""Track merged pull requests and editable release note drafts."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_release_note_drafts"
down_revision: str | Sequence[str] | None = "0006_remove_demo_flags"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "pull_requests", sa.Column("base_branch", sa.String(length=255), nullable=True)
    )
    op.add_column(
        "pull_requests", sa.Column("merged_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.create_table(
        "release_note_drafts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("repository_id", sa.Integer(), nullable=False),
        sa.Column("version", sa.String(length=100), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("source_snapshot_json", sa.Text(), nullable=False),
        sa.Column("source_pr_count", sa.Integer(), nullable=False),
        sa.Column("based_on_release_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["repository_id"], ["repositories.id"]),
        sa.ForeignKeyConstraint(["based_on_release_id"], ["releases.id"]),
        sa.UniqueConstraint("repository_id"),
    )
    op.create_index(
        "ix_release_note_drafts_repository_id",
        "release_note_drafts",
        ["repository_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_release_note_drafts_repository_id", table_name="release_note_drafts"
    )
    op.drop_table("release_note_drafts")
    op.drop_column("pull_requests", "merged_at")
    op.drop_column("pull_requests", "base_branch")
