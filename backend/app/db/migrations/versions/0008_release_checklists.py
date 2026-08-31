"""Persist manual release readiness confirmations."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008_release_checklists"
down_revision: str | Sequence[str] | None = "0007_release_note_drafts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "release_checklists",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("repository_id", sa.Integer(), nullable=False),
        sa.Column("version", sa.String(length=100), nullable=False),
        sa.Column(
            "change_scope_confirmed",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column(
            "rollback_plan_confirmed",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column(
            "release_window_confirmed",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("confirmed_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["repository_id"], ["repositories.id"]),
        sa.ForeignKeyConstraint(["confirmed_by_user_id"], ["users.id"]),
        sa.UniqueConstraint("repository_id"),
    )
    op.create_index(
        "ix_release_checklists_repository_id",
        "release_checklists",
        ["repository_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_release_checklists_repository_id", table_name="release_checklists")
    op.drop_table("release_checklists")
