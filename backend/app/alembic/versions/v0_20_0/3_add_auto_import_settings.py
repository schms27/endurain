"""3: add per-user scheduled auto import settings

Revision ID: 02bfadfaa1bb
Revises: d34bd5e7539c
Create Date: 2026-10-18 20:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "02bfadfaa1bb"
down_revision: str | None = "d34bd5e7539c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the users_auto_import_settings table."""
    op.create_table(
        "users_auto_import_settings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            comment="User ID that the auto import settings belong to",
        ),
        sa.Column(
            "enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
            comment="Whether scheduled auto import is enabled",
        ),
        sa.Column(
            "interval_minutes",
            sa.Integer(),
            nullable=False,
            server_default="60",
            comment="Minutes between two scans of the user's import folder",
        ),
        sa.Column(
            "last_run_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="When the last auto import scan started",
        ),
        sa.Column(
            "last_run_imported",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="Files imported by the last scan",
        ),
        sa.Column(
            "last_run_failed",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="Files that failed to import in the last scan",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_users_auto_import_settings_user_id"),
        "users_auto_import_settings",
        ["user_id"],
        unique=True,
    )


def downgrade() -> None:
    """Drop the users_auto_import_settings table."""
    op.drop_index(op.f("ix_users_auto_import_settings_user_id"), table_name="users_auto_import_settings")
    op.drop_table("users_auto_import_settings")
