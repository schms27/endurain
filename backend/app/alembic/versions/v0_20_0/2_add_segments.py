"""2: add segments, segment efforts, match queue and activity bounding boxes

Revision ID: d34bd5e7539c
Revises: a4dd90d4f76e
Create Date: 2026-10-18 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d34bd5e7539c"
down_revision: str | None = "a4dd90d4f76e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_BBOX_COLUMNS = (
    ("bbox_min_lat", "Southern edge of the GPS track bounding box"),
    ("bbox_min_lon", "Western edge of the GPS track bounding box"),
    ("bbox_max_lat", "Northern edge of the GPS track bounding box"),
    ("bbox_max_lon", "Eastern edge of the GPS track bounding box"),
)


def upgrade() -> None:
    """Create segment tables, add activity bounding boxes and register the backfill."""
    for name, comment in _BBOX_COLUMNS:
        op.add_column("activities", sa.Column(name, sa.Float(), nullable=True, comment=comment))
    op.create_index(
        "ix_activities_activity_type_bbox",
        "activities",
        ["activity_type", "bbox_min_lat", "bbox_max_lat"],
    )

    op.create_table(
        "segments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
            comment="User ID that created the segment",
        ),
        sa.Column("name", sa.String(length=250), nullable=False, comment="Segment name"),
        sa.Column("description", sa.String(length=2500), nullable=True, comment="Segment description"),
        sa.Column("sport_group", sa.String(length=20), nullable=False, comment="Sport group (run, ride, e_ride, foot)"),
        sa.Column("visibility", sa.SmallInteger(), nullable=False, comment="0 - public, 2 - private"),
        sa.Column("geometry", sa.JSON(), nullable=False, comment="Simplified polyline as [[lat, lon, ele], ...]"),
        sa.Column("distance", sa.Float(), nullable=False, comment="Segment length in meters"),
        sa.Column("elevation_gain", sa.Integer(), nullable=True, comment="Elevation gain in meters"),
        sa.Column("elevation_loss", sa.Integer(), nullable=True, comment="Elevation loss in meters"),
        sa.Column("average_grade", sa.Float(), nullable=True, comment="Average grade in percent"),
        sa.Column("maximum_grade", sa.Float(), nullable=True, comment="Maximum grade over 100 m windows in percent"),
        sa.Column("start_lat", sa.Float(), nullable=False, comment="Start latitude"),
        sa.Column("start_lon", sa.Float(), nullable=False, comment="Start longitude"),
        sa.Column("end_lat", sa.Float(), nullable=False, comment="End latitude"),
        sa.Column("end_lon", sa.Float(), nullable=False, comment="End longitude"),
        sa.Column("bbox_min_lat", sa.Float(), nullable=False, comment="Bounding box southern edge"),
        sa.Column("bbox_min_lon", sa.Float(), nullable=False, comment="Bounding box western edge"),
        sa.Column("bbox_max_lat", sa.Float(), nullable=False, comment="Bounding box northern edge"),
        sa.Column("bbox_max_lon", sa.Float(), nullable=False, comment="Bounding box eastern edge"),
        sa.Column("city", sa.String(length=250), nullable=True, comment="City of the segment start"),
        sa.Column("town", sa.String(length=250), nullable=True, comment="Town of the segment start"),
        sa.Column("country", sa.String(length=250), nullable=True, comment="Country of the segment start"),
        sa.Column(
            "source_activity_id",
            sa.Integer(),
            sa.ForeignKey("activities.id", ondelete="SET NULL"),
            nullable=True,
            comment="Activity the segment was created from",
        ),
        sa.Column("is_archived", sa.Boolean(), nullable=False, comment="Archived segments are hidden and not matched"),
        sa.Column(
            "matcher_version",
            sa.SmallInteger(),
            nullable=False,
            comment="Matcher version that produced the stored efforts",
        ),
        sa.Column("effort_count", sa.Integer(), nullable=False, comment="Number of stored efforts"),
        sa.Column("athlete_count", sa.Integer(), nullable=False, comment="Number of distinct users with efforts"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_segments_user_id"), "segments", ["user_id"])
    op.create_index("ix_segments_sport_group_bbox", "segments", ["sport_group", "bbox_min_lat", "bbox_max_lat"])

    op.create_table(
        "segment_efforts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "segment_id",
            sa.Integer(),
            sa.ForeignKey("segments.id", ondelete="CASCADE"),
            nullable=False,
            comment="Segment ID that the effort belongs to",
        ),
        sa.Column(
            "activity_id",
            sa.Integer(),
            sa.ForeignKey("activities.id", ondelete="CASCADE"),
            nullable=False,
            comment="Activity ID that produced the effort",
        ),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            comment="User ID that owns the activity",
        ),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False, comment="Start gate crossing time"),
        sa.Column(
            "elapsed_time",
            sa.DECIMAL(precision=20, scale=10),
            nullable=False,
            comment="Elapsed time from start to end gate (s)",
        ),
        sa.Column("distance", sa.Float(), nullable=False, comment="Distance travelled on the segment (m)"),
        sa.Column("start_index", sa.Integer(), nullable=False, comment="Lat/lon stream index where the effort starts"),
        sa.Column("end_index", sa.Integer(), nullable=False, comment="Lat/lon stream index where the effort ends"),
        sa.Column("average_hr", sa.Integer(), nullable=True, comment="Average heart rate (bpm)"),
        sa.Column("max_hr", sa.Integer(), nullable=True, comment="Max heart rate (bpm)"),
        sa.Column("average_power", sa.Integer(), nullable=True, comment="Average power (watts)"),
        sa.Column("normalized_power", sa.Integer(), nullable=True, comment="Normalized power (watts)"),
        sa.Column("average_cad", sa.Integer(), nullable=True, comment="Average cadence (rpm)"),
        sa.Column("average_speed", sa.Float(), nullable=True, comment="Average speed (m/s)"),
        sa.Column("is_excluded", sa.Boolean(), nullable=False, comment="Effort hidden by its owner"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
            comment="Effort creation date",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "activity_id",
            "segment_id",
            "start_index",
            name="uq_segment_efforts_activity_segment_start",
        ),
    )
    op.create_index(op.f("ix_segment_efforts_activity_id"), "segment_efforts", ["activity_id"])
    op.create_index(op.f("ix_segment_efforts_user_id"), "segment_efforts", ["user_id"])
    op.create_index("ix_segment_efforts_segment_elapsed", "segment_efforts", ["segment_id", "elapsed_time"])
    op.create_index(
        "ix_segment_efforts_segment_user_elapsed",
        "segment_efforts",
        ["segment_id", "user_id", "elapsed_time"],
    )
    op.create_index("ix_segment_efforts_segment_start_time", "segment_efforts", ["segment_id", "start_time"])

    op.create_table(
        "segment_match_queue",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "activity_id",
            sa.Integer(),
            sa.ForeignKey("activities.id", ondelete="CASCADE"),
            nullable=True,
            comment="Activity to match against candidate segments",
        ),
        sa.Column(
            "segment_id",
            sa.Integer(),
            sa.ForeignKey("segments.id", ondelete="CASCADE"),
            nullable=True,
            comment="Segment to backfill against candidate activities",
        ),
        sa.Column("cursor", sa.Integer(), nullable=False, comment="Last activity ID processed by a segment backfill"),
        sa.Column("attempts", sa.Integer(), nullable=False, comment="Number of failed processing attempts"),
        sa.Column("last_error", sa.String(length=250), nullable=True, comment="Last processing error"),
        sa.Column(
            "enqueued_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
            comment="When the item was queued",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "(activity_id IS NULL) <> (segment_id IS NULL)",
            name="ck_segment_match_queue_one_target",
        ),
    )
    op.create_index(op.f("ix_segment_match_queue_activity_id"), "segment_match_queue", ["activity_id"])
    op.create_index(op.f("ix_segment_match_queue_segment_id"), "segment_match_queue", ["segment_id"])

    op.execute(
        """
    INSERT INTO migrations (id, name, description, executed) VALUES
    (8, 'v0.20.0', 'Backfill GPS bounding boxes for existing activities', false);
    """
    )


def downgrade() -> None:
    """Drop segment tables and activity bounding boxes, and remove the backfill registration."""
    op.execute("DELETE FROM migrations WHERE id = 8;")
    op.drop_index(op.f("ix_segment_match_queue_segment_id"), table_name="segment_match_queue")
    op.drop_index(op.f("ix_segment_match_queue_activity_id"), table_name="segment_match_queue")
    op.drop_table("segment_match_queue")
    op.drop_index("ix_segment_efforts_segment_start_time", table_name="segment_efforts")
    op.drop_index("ix_segment_efforts_segment_user_elapsed", table_name="segment_efforts")
    op.drop_index("ix_segment_efforts_segment_elapsed", table_name="segment_efforts")
    op.drop_index(op.f("ix_segment_efforts_user_id"), table_name="segment_efforts")
    op.drop_index(op.f("ix_segment_efforts_activity_id"), table_name="segment_efforts")
    op.drop_table("segment_efforts")
    op.drop_index("ix_segments_sport_group_bbox", table_name="segments")
    op.drop_index(op.f("ix_segments_user_id"), table_name="segments")
    op.drop_table("segments")
    op.drop_index("ix_activities_activity_type_bbox", table_name="activities")
    for name, _ in reversed(_BBOX_COLUMNS):
        op.drop_column("activities", name)
