"""Planned route database models."""

from sqlalchemy import JSON, Float, ForeignKey, Index, SmallInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base, TimestampMixin


class Route(TimestampMixin, Base):
    """
    A planned path without timestamps, owned by one user.

    Attributes:
        id: Primary key.
        user_id: Owner user ID.
        name: Route name.
        description: Optional description.
        activity_type: Intended sport (activity type code).
        source: How the route was created (see RouteSource).
        source_activity_id: Activity the route was saved from.
        original_filename: Name of the imported file.
        geometry: Simplified ``[[lat, lon, ele | None], ...]`` polyline.
        waypoints: Points of interest.
        distance: Length in metres (from the unsimplified points).
        elevation_gain: Elevation gain in metres.
        elevation_loss: Elevation loss in metres.
        elevation_min: Lowest elevation in metres.
        elevation_max: Highest elevation in metres.
        is_loop: Whether start and end are close together.
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
        created_at: Creation timestamp.
        updated_at: Last update timestamp.
    """

    __tablename__ = "routes"
    __table_args__ = (Index("ix_routes_user_id_created_at", "user_id", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        comment="User ID that owns the route",
    )
    name: Mapped[str] = mapped_column(String(250), nullable=False, comment="Route name")
    description: Mapped[str | None] = mapped_column(String(2500), nullable=True, comment="Route description")
    activity_type: Mapped[int | None] = mapped_column(nullable=True, comment="Intended activity type")
    source: Mapped[int] = mapped_column(SmallInteger, nullable=False, comment="1 - import, 2 - activity")
    source_activity_id: Mapped[int | None] = mapped_column(
        ForeignKey("activities.id", ondelete="SET NULL"),
        nullable=True,
        comment="Activity the route was saved from",
    )
    original_filename: Mapped[str | None] = mapped_column(
        String(250),
        nullable=True,
        comment="Name of the imported file",
    )
    geometry: Mapped[list] = mapped_column(
        JSON,
        nullable=False,
        comment="Simplified polyline as [[lat, lon, ele], ...]",
    )
    waypoints: Mapped[list] = mapped_column(JSON, nullable=False, comment="Points of interest")
    distance: Mapped[float] = mapped_column(Float, nullable=False, comment="Route length in meters")
    elevation_gain: Mapped[int | None] = mapped_column(nullable=True, comment="Elevation gain in meters")
    elevation_loss: Mapped[int | None] = mapped_column(nullable=True, comment="Elevation loss in meters")
    elevation_min: Mapped[int | None] = mapped_column(nullable=True, comment="Lowest elevation in meters")
    elevation_max: Mapped[int | None] = mapped_column(nullable=True, comment="Highest elevation in meters")
    is_loop: Mapped[bool] = mapped_column(nullable=False, default=False, comment="Start and end are close")
    start_lat: Mapped[float] = mapped_column(Float, nullable=False, comment="Start latitude")
    start_lon: Mapped[float] = mapped_column(Float, nullable=False, comment="Start longitude")
    end_lat: Mapped[float] = mapped_column(Float, nullable=False, comment="End latitude")
    end_lon: Mapped[float] = mapped_column(Float, nullable=False, comment="End longitude")
    bbox_min_lat: Mapped[float] = mapped_column(Float, nullable=False, comment="Bounding box southern edge")
    bbox_min_lon: Mapped[float] = mapped_column(Float, nullable=False, comment="Bounding box western edge")
    bbox_max_lat: Mapped[float] = mapped_column(Float, nullable=False, comment="Bounding box northern edge")
    bbox_max_lon: Mapped[float] = mapped_column(Float, nullable=False, comment="Bounding box eastern edge")
    city: Mapped[str | None] = mapped_column(String(250), nullable=True, comment="City of the route start")
    town: Mapped[str | None] = mapped_column(String(250), nullable=True, comment="Town of the route start")
    country: Mapped[str | None] = mapped_column(String(250), nullable=True, comment="Country of the route start")
