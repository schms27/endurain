"""4: add segment leaderboard opt-out and segment server settings

Also merges the two v0.20.0 revision 3 heads (routes and auto import).

Revision ID: 7f3e2b9c1d4a
Revises: cb0c2a45883f, 02bfadfaa1bb
Create Date: 2026-10-18 22:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7f3e2b9c1d4a"
down_revision: str | Sequence[str] | None = ("cb0c2a45883f", "02bfadfaa1bb")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add the leaderboard opt-out and the segment server settings."""
    op.add_column(
        "users_privacy_settings",
        sa.Column(
            "hide_from_segment_leaderboards",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
            comment="Hide your efforts from other users' segment leaderboards",
        ),
    )
    op.add_column(
        "server_settings",
        sa.Column(
            "segments_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
            comment="Enable segments and segment matching",
        ),
    )
    op.add_column(
        "server_settings",
        sa.Column(
            "segments_public_creation",
            sa.String(length=10),
            nullable=False,
            server_default="all",
            comment="Who may create public segments (all, admins)",
        ),
    )


def downgrade() -> None:
    """Drop the leaderboard opt-out and the segment server settings."""
    op.drop_column("server_settings", "segments_public_creation")
    op.drop_column("server_settings", "segments_enabled")
    op.drop_column("users_privacy_settings", "hide_from_segment_leaderboards")
