"""Migration 8: backfill GPS bounding boxes for existing activities."""

from sqlalchemy.orm import Session

import activities.activity.crud as activity_crud
import activities.activity_streams.crud as activity_streams_crud
import activities.activity_streams.utils as activity_streams_utils
import core.logger as core_logger
import migrations.crud as migrations_crud


def process_migration_8(db: Session) -> None:
    """
    Backfill activity bounding boxes from their map streams.

    Segment matching uses the bounding box to find candidate activities
    without loading every GPS stream.

    Args:
        db: The SQLAlchemy database session.

    Returns:
        None.
    """
    core_logger.print_to_log_and_console("Started migration 8")

    last_id: int = 0
    updated: int = 0
    while True:
        try:
            batch = activity_streams_crud.get_map_streams_without_activity_bounding_box(db=db, after_id=last_id)
            if not batch:
                break
            for stream in batch:
                bbox = activity_streams_utils.bounding_box_from_lat_lon_waypoints(stream.stream_waypoints)
                if bbox is not None:
                    activity_crud.set_activity_bounding_box(stream.activity_id, bbox, db, commit=False)
                    updated += 1
            db.commit()
            last_id = batch[-1].id
        except Exception as err:
            db.rollback()
            core_logger.print_to_log_and_console(
                f"Migration 8 - Error backfilling activity bounding boxes: {err}",
                "error",
                exc=err,
            )
            core_logger.print_to_log_and_console(
                "Migration 8 failed to process all activities. Will try again later.",
                "error",
            )
            return

    try:
        migrations_crud.set_migration_as_executed(8, db)
    except Exception as err:
        core_logger.print_to_log_and_console(
            f"Migration 8 - Failed to set migration as executed: {err}",
            "error",
            exc=err,
        )
        return

    core_logger.print_to_log_and_console(f"Finished migration 8 ({updated} activities updated)")
