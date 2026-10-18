"""Constants for segments, segment efforts and segment matching."""

from enum import StrEnum
from typing import Final


class SportGroup(StrEnum):
    """
    Group of activity types that share segments.

    Members:
        RUN: Outdoor running.
        RIDE: Outdoor cycling without motor assistance.
        E_RIDE: Motor-assisted cycling.
        FOOT: Walking and hiking.
    """

    RUN = "run"
    RIDE = "ride"
    E_RIDE = "e_ride"
    FOOT = "foot"


# Activity types matched against each sport group. Virtual and indoor
# types (3, 7, 28, 31, 40) are deliberately absent: their coordinates are
# synthetic or missing.
SPORT_GROUP_ACTIVITY_TYPES: Final[dict[SportGroup, tuple[int, ...]]] = {
    SportGroup.RUN: (1, 2, 34),
    SportGroup.RIDE: (4, 5, 6, 27, 29),
    SportGroup.E_RIDE: (35, 36),
    SportGroup.FOOT: (11, 12, 44),
}

ACTIVITY_TYPE_SPORT_GROUP: Final[dict[int, SportGroup]] = {
    activity_type: group
    for group, activity_types in SPORT_GROUP_ACTIVITY_TYPES.items()
    for activity_type in activity_types
}

# Segment visibility uses the same codes as activities. Followers-only
# segments are not supported (they would need rematching whenever the
# follow graph changes).
SEGMENT_VISIBILITY_PUBLIC: Final[int] = 0
SEGMENT_VISIBILITY_PRIVATE: Final[int] = 2

# Segment creation limits.
MIN_SEGMENT_DISTANCE_M: Final[dict[SportGroup, float]] = {
    SportGroup.RUN: 200.0,
    SportGroup.FOOT: 200.0,
    SportGroup.RIDE: 400.0,
    SportGroup.E_RIDE: 400.0,
}
MAX_SEGMENT_DISTANCE_M: Final[float] = 100_000.0
MIN_SEGMENT_POINTS: Final[int] = 10
SEGMENT_SIMPLIFY_TOLERANCE_M: Final[float] = 2.0
GRADE_WINDOW_M: Final[float] = 100.0

# Duplicate check for a proposed segment: endpoints within this distance
# and length within this relative difference of an existing segment.
SIMILAR_ENDPOINT_M: Final[float] = 30.0
SIMILAR_DISTANCE_RATIO: Final[float] = 0.05

# Leaderboards.
LEADERBOARD_MAX_RECORDS: Final[int] = 100
LEADERBOARD_RECENT_DAYS: Final[int] = 90

# Matcher parameters. Bump MATCHER_VERSION whenever a change alters
# matching results so stored efforts get recomputed.
MATCHER_VERSION: Final[int] = 1
GATE_RADIUS_M: Final[float] = 25.0
CORRIDOR_M: Final[float] = 30.0
SAMPLE_SPACING_M: Final[float] = 10.0
MIN_COVERAGE: Final[float] = 0.90
MIN_LENGTH_RATIO: Final[float] = 0.85
MAX_LENGTH_RATIO: Final[float] = 1.30
MAX_GAP_M: Final[float] = 500.0
# Raw GPS jitter inflates path length, so the length ratio is measured on
# the sub-track simplified with this tolerance (half the corridor: wide
# enough to absorb 5 m white noise at 1 Hz, far below real detours).
LENGTH_SIMPLIFY_TOLERANCE_M: Final[float] = 15.0

# Queue processing.
QUEUE_DRAIN_TIME_BUDGET_S: Final[float] = 50.0
QUEUE_MAX_ATTEMPTS: Final[int] = 3
BACKFILL_BATCH_SIZE: Final[int] = 200
# Arbitrary constant key for pg_try_advisory_lock around the queue drain.
QUEUE_ADVISORY_LOCK_KEY: Final[int] = 0x5E6D_E175
