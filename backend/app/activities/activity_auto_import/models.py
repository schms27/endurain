"""Scheduled auto import settings database models."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class UsersAutoImportSettings(Base):
    """
    Per-user scheduled auto import configuration and last-run status.

    Attributes:
        id: Primary key.
        user_id: Foreign key to users table (one row per user).
        enabled: Whether the user's import folder is scanned on a schedule.
        interval_minutes: Minutes between two scans.
        last_run_at: When the last scan started.
        last_run_imported: Files imported by the last scan.
        last_run_failed: Files that failed in the last scan.
    """

    __tablename__ = "users_auto_import_settings"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
        comment="User ID that the auto import settings belong to",
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether scheduled auto import is enabled",
    )
    interval_minutes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=60,
        comment="Minutes between two scans of the user's import folder",
    )
    last_run_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When the last auto import scan started",
    )
    last_run_imported: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Files imported by the last scan",
    )
    last_run_failed: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Files that failed to import in the last scan",
    )
