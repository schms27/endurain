"""Scheduled auto import Pydantic schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, field_validator

# Intervals offered in the settings UI, in minutes.
ALLOWED_INTERVALS_MINUTES: tuple[int, ...] = (15, 30, 60, 180, 360, 720, 1440)
DEFAULT_INTERVAL_MINUTES = 60


class AutoImportSettingsUpdate(BaseModel):
    """
    Settings a user can change.

    Attributes:
        enabled: Whether the import folder is scanned on a schedule.
        interval_minutes: Minutes between two scans; one of
            ``ALLOWED_INTERVALS_MINUTES``.
    """

    enabled: StrictBool
    interval_minutes: StrictInt = Field(default=DEFAULT_INTERVAL_MINUTES)

    model_config = ConfigDict(extra="forbid")

    @field_validator("interval_minutes")
    @classmethod
    def _check_interval(cls, value: int) -> int:
        if value not in ALLOWED_INTERVALS_MINUTES:
            raise ValueError(f"interval_minutes must be one of {ALLOWED_INTERVALS_MINUTES}")
        return value


class AutoImportSettingsRead(BaseModel):
    """
    Settings plus folder and last-run status, as shown in the UI.

    Attributes:
        enabled: Whether the import folder is scanned on a schedule.
        interval_minutes: Minutes between two scans.
        folder: Import folder path, relative to the server's files
            directory.
        pending_files: Supported files currently waiting in the folder.
        last_run_at: When the last scan started, if ever.
        last_run_imported: Files imported by the last scan.
        last_run_failed: Files that failed in the last scan.
    """

    enabled: bool
    interval_minutes: int
    folder: str
    pending_files: int
    last_run_at: datetime | None = None
    last_run_imported: int = 0
    last_run_failed: int = 0
