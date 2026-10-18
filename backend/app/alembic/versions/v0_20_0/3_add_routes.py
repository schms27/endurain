"""3: add planned routes

Revision ID: cb0c2a45883f
Revises: a4dd90d4f76e
Create Date: 2026-10-18 18:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "cb0c2a45883f"
down_revision: str | None = "a4dd90d4f76e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the routes table."""
    op.create_table(
        "routes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            comment="User ID that owns the route",
        ),
        sa.Column("name", sa.String(length=250), nullable=False, comment="Route name"),
        sa.Column("description", sa.String(length=2500), nullable=True, comment="Route description"),
        sa.Column("activity_type", sa.Integer(), nullable=True, comment="Intended activity type"),
        sa.Column("source", sa.SmallInteger(), nullable=False, comment="1 - import, 2 - activity"),
        sa.Column(
            "source_activity_id",
            sa.Integer(),
            sa.ForeignKey("activities.id", ondelete="SET NULL"),
            nullable=True,
            comment="Activity the route was saved from",
        ),
        sa.Column("original_filename", sa.String(length=250), nullable=True, comment="Name of the imported file"),
        sa.Column("geometry", sa.JSON(), nullable=False, comment="Simplified polyline as [[lat, lon, ele], ...]"),
        sa.Column("waypoints", sa.JSON(), nullable=False, comment="Points of interest"),
        sa.Column("distance", sa.Float(), nullable=False, comment="Route length in meters"),
        sa.Column("elevation_gain", sa.Integer(), nullable=True, comment="Elevation gain in meters"),
        sa.Column("elevation_loss", sa.Integer(), nullable=True, comment="Elevation loss in meters"),
        sa.Column("elevation_min", sa.Integer(), nullable=True, comment="Lowest elevation in meters"),
        sa.Column("elevation_max", sa.Integer(), nullable=True, comment="Highest elevation in meters"),
        sa.Column("is_loop", sa.Boolean(), nullable=False, comment="Start and end are close"),
        sa.Column("start_lat", sa.Float(), nullable=False, comment="Start latitude"),
        sa.Column("start_lon", sa.Float(), nullable=False, comment="Start longitude"),
        sa.Column("end_lat", sa.Float(), nullable=False, comment="End latitude"),
        sa.Column("end_lon", sa.Float(), nullable=False, comment="End longitude"),
        sa.Column("bbox_min_lat", sa.Float(), nullable=False, comment="Bounding box southern edge"),
        sa.Column("bbox_min_lon", sa.Float(), nullable=False, comment="Bounding box western edge"),
        sa.Column("bbox_max_lat", sa.Float(), nullable=False, comment="Bounding box northern edge"),
        sa.Column("bbox_max_lon", sa.Float(), nullable=False, comment="Bounding box eastern edge"),
        sa.Column("city", sa.String(length=250), nullable=True, comment="City of the route start"),
        sa.Column("town", sa.String(length=250), nullable=True, comment="Town of the route start"),
        sa.Column("country", sa.String(length=250), nullable=True, comment="Country of the route start"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_routes_user_id_created_at", "routes", ["user_id", "created_at"])


def downgrade() -> None:
    """Drop the routes table."""
    op.drop_index("ix_routes_user_id_created_at", table_name="routes")
    op.drop_table("routes")
