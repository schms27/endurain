"""Segment database models."""

from sqlalchemy import (
    JSON,
    Float,
    ForeignKey,
    Index,
    SmallInteger,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base, TimestampMixin


class Segment(TimestampMixin, Base):
    """
    A named stretch of road or trail that activities are matched against.

    The geometry is immutable after creation so stored efforts always stay
    valid; only name, description and visibility can change.

    Attributes:
        id: Primary key.
        user_id: Creator user ID (NULL once the creator is deleted).
        name: Segment name.
        description: Optional description.
        sport_group: Sport group whose activities are matched.
        visibility: 0 - public, 2 - private.
        geometry: Simplified ``[[lat, lon, ele | None], ...]`` polyline.
        distance: Length in metres.
        elevation_gain: Elevation gain in metres.
        elevation_loss: Elevation loss in metres.
        average_grade: Average grade in percent.
        maximum_grade: Maximum grade over 100 m windows, in percent.
        start_lat: Start latitude.
        start_lon: Start longitude.
        end_lat: End latitude.
        end_lon: End longitude.
        bbox_min_lat: Bounding box southern edge.
        bbox_min_lon: Bounding box western edge.
        bbox_max_lat: Bounding box northern edge.
        bbox_max_lon: Bounding box eastern edge.
        city: City of the start point.
        town: Town of the start point.
        country: Country of the start point.
        source_activity_id: Activity the segment was cut from.
        is_archived: Archived segments are hidden and no longer matched.
        matcher_version: Matcher version that produced stored efforts.
        effort_count: Number of stored efforts.
        athlete_count: Number of distinct users with efforts.
        created_at: Creation timestamp.
        updated_at: Last update timestamp.
    """

    __tablename__ = "segments"
    __table_args__ = (
        Index(
            "ix_segments_sport_group_bbox",
            "sport_group",
            "bbox_min_lat",
            "bbox_max_lat",
        ),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="User ID that created the segment",
    )
    name: Mapped[str] = mapped_column(
        String(250),
        nullable=False,
        comment="Segment name",
    )
    description: Mapped[str | None] = mapped_column(
        String(2500),
        nullable=True,
        comment="Segment description",
    )
    sport_group: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="Sport group (run, ride, e_ride, foot)",
    )
    visibility: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
        default=0,
        comment="0 - public, 2 - private",
    )
    geometry: Mapped[list] = mapped_column(
        JSON,
        nullable=False,
        comment="Simplified polyline as [[lat, lon, ele], ...]",
    )
    distance: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="Segment length in meters",
    )
    elevation_gain: Mapped[int | None] = mapped_column(
        nullable=True,
        comment="Elevation gain in meters",
    )
    elevation_loss: Mapped[int | None] = mapped_column(
        nullable=True,
        comment="Elevation loss in meters",
    )
    average_grade: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="Average grade in percent",
    )
    maximum_grade: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="Maximum grade over 100 m windows in percent",
    )
    start_lat: Mapped[float] = mapped_column(Float, nullable=False, comment="Start latitude")
    start_lon: Mapped[float] = mapped_column(Float, nullable=False, comment="Start longitude")
    end_lat: Mapped[float] = mapped_column(Float, nullable=False, comment="End latitude")
    end_lon: Mapped[float] = mapped_column(Float, nullable=False, comment="End longitude")
    bbox_min_lat: Mapped[float] = mapped_column(Float, nullable=False, comment="Bounding box southern edge")
    bbox_min_lon: Mapped[float] = mapped_column(Float, nullable=False, comment="Bounding box western edge")
    bbox_max_lat: Mapped[float] = mapped_column(Float, nullable=False, comment="Bounding box northern edge")
    bbox_max_lon: Mapped[float] = mapped_column(Float, nullable=False, comment="Bounding box eastern edge")
    city: Mapped[str | None] = mapped_column(
        String(250),
        nullable=True,
        comment="City of the segment start",
    )
    town: Mapped[str | None] = mapped_column(
        String(250),
        nullable=True,
        comment="Town of the segment start",
    )
    country: Mapped[str | None] = mapped_column(
        String(250),
        nullable=True,
        comment="Country of the segment start",
    )
    source_activity_id: Mapped[int | None] = mapped_column(
        ForeignKey("activities.id", ondelete="SET NULL"),
        nullable=True,
        comment="Activity the segment was created from",
    )
    is_archived: Mapped[bool] = mapped_column(
        nullable=False,
        default=False,
        comment="Archived segments are hidden and not matched",
    )
    matcher_version: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
        default=0,
        comment="Matcher version that produced the stored efforts",
    )
    effort_count: Mapped[int] = mapped_column(
        nullable=False,
        default=0,
        comment="Number of stored efforts",
    )
    athlete_count: Mapped[int] = mapped_column(
        nullable=False,
        default=0,
        comment="Number of distinct users with efforts",
    )
