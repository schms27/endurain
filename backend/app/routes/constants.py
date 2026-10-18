"""Constants for planned routes."""

from enum import IntEnum, StrEnum
from typing import Final


class RouteSource(IntEnum):
    """
    How a route was created.

    Members:
        IMPORT: Imported from a GPX, TCX or FIT file.
        ACTIVITY: Saved from a recorded activity.
        COPY: Copied from another user's shared route.
    """

    IMPORT = 1
    ACTIVITY = 2
    COPY = 4


class RouteVisibility(IntEnum):
    """
    Who can see a route; same codes as activity visibility.

    Members:
        PUBLIC: Every signed-in user, and anonymous visitors when public
            shareable links are enabled.
        FOLLOWERS: Accepted followers of the owner.
        PRIVATE: Only the owner.
    """

    PUBLIC = 0
    FOLLOWERS = 1
    PRIVATE = 2


class PoiKind(StrEnum):
    """
    Point-of-interest categories on a route.

    Members:
        GENERIC: Anything else.
        WATER: Drinking water.
        FOOD: Food or restaurant.
        SUMMIT: Summit or peak.
        VIEWPOINT: Scenic viewpoint.
        DANGER: Hazard or caution.
        SHELTER: Hut or shelter.
        TOILET: Toilet or restroom.
    """

    GENERIC = "generic"
    WATER = "water"
    FOOD = "food"
    SUMMIT = "summit"
    VIEWPOINT = "viewpoint"
    DANGER = "danger"
    SHELTER = "shelter"
    TOILET = "toilet"


# Keywords in a GPX <sym>/<type> or FIT course point type that map to a kind.
POI_KIND_KEYWORDS: Final[tuple[tuple[PoiKind, tuple[str, ...]], ...]] = (
    (PoiKind.WATER, ("water", "drink", "fountain")),
    (PoiKind.FOOD, ("food", "restaurant", "cafe", "snack")),
    (PoiKind.SUMMIT, ("summit", "peak", "mountain")),
    (PoiKind.VIEWPOINT, ("view", "scenic", "overlook")),
    (PoiKind.DANGER, ("danger", "caution", "warning", "hazard")),
    (PoiKind.SHELTER, ("shelter", "hut", "lodge")),
    (PoiKind.TOILET, ("toilet", "restroom", "wc")),
)

# Import limits.
ROUTE_FILE_EXTENSIONS: Final[frozenset[str]] = frozenset({"gpx", "tcx", "fit"})
MAX_ROUTE_FILE_BYTES: Final[int] = 20 * 1024 * 1024
MAX_RAW_POINTS: Final[int] = 500_000
MAX_POIS: Final[int] = 500
MAX_POI_NAME_LENGTH: Final[int] = 250
MAX_POI_DESCRIPTION_LENGTH: Final[int] = 1000

# Stored geometry: simplified until at most MAX_STORED_POINTS remain.
MAX_STORED_POINTS: Final[int] = 20_000
SIMPLIFY_TOLERANCE_M: Final[float] = 1.0

# A route whose start and end are this close is a loop.
LOOP_THRESHOLD_M: Final[float] = 100.0

# Sharing.
SHARE_TOKEN_BYTES: Final[int] = 32
SHARE_TOKEN_LENGTH: Final[int] = 43
MAX_HIDE_ENDPOINTS_M: Final[int] = 2000

# Home-location warning: a route endpoint this close to the start of at least
# HOME_MIN_ACTIVITIES of the owner's activities probably reveals where they live.
HOME_RADIUS_M: Final[float] = 200.0
HOME_MIN_ACTIVITIES: Final[int] = 3

# FIT positions are stored in semicircles.
FIT_SEMICIRCLES_TO_DEGREES: Final[float] = 180.0 / 2**31
