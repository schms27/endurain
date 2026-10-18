"""5: add route sharing (visibility, share token, endpoint trimming, copies)

Revision ID: 5c8d1a3f9b20
Revises: 7f3e2b9c1d4a
Create Date: 2026-10-18 23:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "5c8d1a3f9b20"
down_revision: str | None = "7f3e2b9c1d4a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add the sharing columns to routes; existing routes stay private."""
    op.add_column(
        "routes",
        sa.Column(
            "visibility",
            sa.SmallInteger(),
            nullable=False,
            server_default="2",
            comment="0 - public, 1 - followers, 2 - private",
        ),
    )
    op.add_column(
        "routes",
        sa.Column("share_token", sa.String(length=43), nullable=True, comment="Unlisted share link token"),
    )
    op.add_column(
        "routes",
        sa.Column(
            "hide_endpoints_m",
            sa.SmallInteger(),
            nullable=False,
            server_default="0",
            comment="Metres hidden at both ends for non-owners",
        ),
    )
    op.add_column(
        "routes",
        sa.Column(
            "source_route_id",
            sa.Integer(),
            sa.ForeignKey("routes.id", ondelete="SET NULL", name="fk_routes_source_route_id"),
            nullable=True,
            comment="Route this one was copied from",
        ),
    )
    op.alter_column(
        "routes",
        "source",
        existing_type=sa.SmallInteger(),
        existing_nullable=False,
        comment="1 - import, 2 - activity, 4 - copy",
        existing_comment="1 - import, 2 - activity",
    )
    op.create_index("ix_routes_share_token", "routes", ["share_token"], unique=True)


def downgrade() -> None:
    """Drop the sharing columns; copied routes become plain imports."""
    op.drop_index("ix_routes_share_token", table_name="routes")
    op.execute("UPDATE routes SET source = 1 WHERE source = 4")
    op.alter_column(
        "routes",
        "source",
        existing_type=sa.SmallInteger(),
        existing_nullable=False,
        comment="1 - import, 2 - activity",
        existing_comment="1 - import, 2 - activity, 4 - copy",
    )
    op.drop_constraint("fk_routes_source_route_id", "routes", type_="foreignkey")
    op.drop_column("routes", "source_route_id")
    op.drop_column("routes", "hide_endpoints_m")
    op.drop_column("routes", "share_token")
    op.drop_column("routes", "visibility")
