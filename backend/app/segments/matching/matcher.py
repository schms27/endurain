"""Pure segment matching algorithm.

Finds every pass of a GPS track over a segment, start gate to end gate in
segment direction, while staying inside a corridor around the segment.
No database access: inputs are plain coordinate and time arrays, which
keeps the algorithm easy to test with synthetic tracks.

Steps for one track and one segment:

1. Project both to local metres around the segment start.
2. Find *gate passes*: runs of track points within ``gate_radius_m`` of
   the segment start (or end); each run is refined to the closest point
   on the track polyline, with an interpolated time and along-track
   distance.
3. Pair each start pass with a later end pass whose sub-track length
   (measured after light simplification, so GPS jitter does not inflate
   it) is within the length-ratio band, with no GPS gap above ``max_gap_m``,
   and whose sub-track covers at least ``min_coverage`` of the segment
   samples within ``corridor_m``.
4. Efforts never overlap: after a match, the next start pass must come
   after the matched end pass.
"""

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray

import core.geo as core_geo
import segments.constants as segments_constants


@dataclass(frozen=True)
class MatcherParams:
    """
    Tunable matching thresholds.

    Attributes:
        gate_radius_m: Distance to a gate point that counts as a pass.
        corridor_m: Max distance from the track to a segment sample.
        sample_spacing_m: Spacing of segment samples for coverage.
        min_coverage: Required fraction of covered segment samples.
        min_length_ratio: Lower bound of track length / segment length.
        max_length_ratio: Upper bound of track length / segment length.
        max_gap_m: Max distance between consecutive track points.
        length_simplify_m: Simplification tolerance used before measuring
            the sub-track length, so GPS jitter does not inflate it.
    """

    gate_radius_m: float = segments_constants.GATE_RADIUS_M
    corridor_m: float = segments_constants.CORRIDOR_M
    sample_spacing_m: float = segments_constants.SAMPLE_SPACING_M
    min_coverage: float = segments_constants.MIN_COVERAGE
    min_length_ratio: float = segments_constants.MIN_LENGTH_RATIO
    max_length_ratio: float = segments_constants.MAX_LENGTH_RATIO
    max_gap_m: float = segments_constants.MAX_GAP_M
    length_simplify_m: float = segments_constants.LENGTH_SIMPLIFY_TOLERANCE_M


DEFAULT_PARAMS = MatcherParams()

# Gate crossing fit: headings are measured over +/- this many points, and
# a point takes part when its heading is within ~45 degrees of the
# segment direction.
_HEADING_HALF_WINDOW = 2
_MIN_HEADING_ALIGNMENT = 0.7


@dataclass(frozen=True)
class MatchedEffort:
    """
    One matched pass over a segment.

    Attributes:
        start_index: Track index of the first point of the effort.
        end_index: Track index of the last point of the effort.
        start_time: Start gate crossing (seconds, same clock as input).
        end_time: End gate crossing (seconds, same clock as input).
        distance_m: Along-track distance between the gate crossings.
        coverage: Fraction of segment samples within the corridor.
    """

    start_index: int
    end_index: int
    start_time: float
    end_time: float
    distance_m: float
    coverage: float

    @property
    def elapsed_time(self) -> float:
        """Elapsed seconds between the gate crossings."""
        return self.end_time - self.start_time


@dataclass(frozen=True)
class _GatePass:
    """A refined crossing of a gate point by the track."""

    run_index: int
    edge: int
    fraction: float
    time: float
    along_m: float


def _runs(mask: NDArray[np.bool_]) -> list[tuple[int, int]]:
    """
    Return inclusive (start, end) index ranges where ``mask`` is True.

    Args:
        mask: Boolean array.

    Returns:
        List of inclusive index ranges.
    """
    if mask.size == 0:
        return []
    padded = np.concatenate(([False], mask, [False])).astype(np.int8)
    changes = np.diff(padded)
    starts = np.flatnonzero(changes == 1)
    ends = np.flatnonzero(changes == -1) - 1
    return list(zip(starts.tolist(), ends.tolist(), strict=True))


def _merge_close_runs(
    runs: list[tuple[int, int]],
    gate_distance: NDArray[np.float64],
    leave_radius_m: float,
) -> list[tuple[int, int]]:
    """
    Merge gate runs split by GPS jitter.

    A noisy point can briefly leave the gate radius, splitting one pass
    into several short runs. Two runs are separate passes only if the
    track really left the gate's vicinity in between.

    Args:
        runs: Inclusive index ranges in track order.
        gate_distance: Distance from each track point to the gate.
        leave_radius_m: Distance the track must exceed between two runs
            for them to count as separate passes.

    Returns:
        The merged index ranges.
    """
    merged: list[tuple[int, int]] = []
    for first, last in runs:
        if merged:
            between = gate_distance[merged[-1][1] + 1 : first]
            if between.size == 0 or float(between.max()) < leave_radius_m:
                merged[-1] = (merged[-1][0], last)
                continue
        merged.append((first, last))
    return merged


def _gate_crossing_time(
    gate_x: float,
    gate_y: float,
    direction: tuple[float, float],
    track_x: NDArray[np.float64],
    track_y: NDArray[np.float64],
    times: NDArray[np.float64],
    lo: int,
    hi: int,
) -> float | None:
    """
    Estimate when the track crosses a gate line.

    The gate line passes through the gate point, perpendicular to the
    segment direction. Fitting the signed distance to that line against
    time with a straight line averages out GPS noise, which snapping to
    the nearest (jittery) track edge does not. Only points whose smoothed
    heading follows the segment direction take part, so a gate placed on
    a corner is not skewed by the perpendicular approach or exit.

    Args:
        gate_x: Gate x in local metres.
        gate_y: Gate y in local metres.
        direction: Unit vector of the segment direction at the gate.
        track_x: Track x in local metres.
        track_y: Track y in local metres.
        times: Track timestamps in seconds.
        lo: First track index of the gate window.
        hi: Last track index of the gate window (inclusive).

    Returns:
        The crossing time, or None when the fit is not usable (too few
        aligned points, not moving in segment direction, or crossing
        outside the window).
    """
    indices = np.arange(lo, hi + 1)
    before = np.clip(indices - _HEADING_HALF_WINDOW, 0, track_x.size - 1)
    after = np.clip(indices + _HEADING_HALF_WINDOW, 0, track_x.size - 1)
    heading_x = track_x[after] - track_x[before]
    heading_y = track_y[after] - track_y[before]
    heading_norm = np.hypot(heading_x, heading_y)
    along = heading_x * direction[0] + heading_y * direction[1]
    aligned = indices[along >= _MIN_HEADING_ALIGNMENT * heading_norm]
    if aligned.size < 3 or times[aligned[-1]] <= times[aligned[0]]:
        return None
    signed = (track_x[aligned] - gate_x) * direction[0] + (track_y[aligned] - gate_y) * direction[1]
    offset_times = times[aligned] - times[aligned[0]]
    slope, intercept = np.polyfit(offset_times, signed, 1)
    if slope <= 0:
        return None
    crossing = float(times[aligned[0]] - intercept / slope)
    if not times[lo] <= crossing <= times[hi]:
        return None
    return crossing


def _gate_passes(
    gate_x: float,
    gate_y: float,
    direction: tuple[float, float] | None,
    track_x: NDArray[np.float64],
    track_y: NDArray[np.float64],
    times: NDArray[np.float64],
    cumulative: NDArray[np.float64],
    radius_m: float,
) -> list[_GatePass]:
    """
    Find and refine all passes of the track near a gate point.

    Args:
        gate_x: Gate x in local metres.
        gate_y: Gate y in local metres.
        direction: Unit segment direction at the gate, if known.
        track_x: Track x in local metres.
        track_y: Track y in local metres.
        times: Track timestamps in seconds.
        cumulative: Along-track distance at each track point.
        radius_m: Gate radius in metres.

    Returns:
        Gate passes in track order.
    """
    gate_distance = np.hypot(track_x - gate_x, track_y - gate_y)
    last_point = track_x.size - 1
    runs = _merge_close_runs(_runs(gate_distance < radius_m), gate_distance, 2 * radius_m)
    passes: list[_GatePass] = []
    for run_index, (first, last) in enumerate(runs):
        # Include the edges entering and leaving the run so the crossing
        # can lie between a point inside and one outside the gate.
        lo = max(first - 1, 0)
        hi = min(last + 1, last_point)
        crossing = None
        if direction is not None:
            crossing = _gate_crossing_time(gate_x, gate_y, direction, track_x, track_y, times, lo, hi)
        if crossing is None:
            edge_offset, fraction, _ = core_geo.project_onto_polyline(
                gate_x,
                gate_y,
                track_x[lo : hi + 1],
                track_y[lo : hi + 1],
            )
            edge = lo + edge_offset
            time = float(times[edge] + fraction * (times[edge + 1] - times[edge]))
        else:
            time = crossing
            edge = int(np.clip(np.searchsorted(times, time, side="right") - 1, 0, last_point - 1))
            span = float(times[edge + 1] - times[edge])
            fraction = float(np.clip((time - times[edge]) / span, 0.0, 1.0)) if span > 0 else 0.0
        along = cumulative[edge] + fraction * (cumulative[edge + 1] - cumulative[edge])
        passes.append(_GatePass(run_index, edge, fraction, time, float(along)))
    return passes


def _gate_direction(
    sample_x: NDArray[np.float64],
    sample_y: NDArray[np.float64],
    at_start: bool,
) -> tuple[float, float] | None:
    """
    Unit direction of the segment over its first or last ~20 m.

    Args:
        sample_x: Evenly spaced segment sample x.
        sample_y: Evenly spaced segment sample y.
        at_start: Direction at the start (True) or the end (False).

    Returns:
        The unit vector, or None for a degenerate segment.
    """
    step = min(2, sample_x.size - 1)
    if step < 1:
        return None
    if at_start:
        dx, dy = sample_x[step] - sample_x[0], sample_y[step] - sample_y[0]
    else:
        dx, dy = sample_x[-1] - sample_x[-1 - step], sample_y[-1] - sample_y[-1 - step]
    norm = float(np.hypot(dx, dy))
    if norm == 0:
        return None
    return float(dx / norm), float(dy / norm)


def _segment_samples(
    segment_x: NDArray[np.float64],
    segment_y: NDArray[np.float64],
    spacing_m: float,
) -> tuple[NDArray[np.float64], NDArray[np.float64], float]:
    """
    Sample the segment polyline at a fixed spacing.

    Args:
        segment_x: Segment x in local metres.
        segment_y: Segment y in local metres.
        spacing_m: Sample spacing in metres.

    Returns:
        Tuple of (sample x, sample y, segment length in metres).
    """
    steps = np.hypot(np.diff(segment_x), np.diff(segment_y))
    cumulative = np.concatenate(([0.0], np.cumsum(steps)))
    grid, sample_x = core_geo.resample_by_distance(cumulative, segment_x, spacing_m)
    sample_y = np.interp(grid, cumulative, segment_y)
    return sample_x, sample_y, float(cumulative[-1])


def _sub_track(
    start: _GatePass,
    end: _GatePass,
    track_x: NDArray[np.float64],
    track_y: NDArray[np.float64],
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """
    Build the track polyline between two gate crossings.

    Args:
        start: Start gate pass.
        end: End gate pass.
        track_x: Track x in local metres.
        track_y: Track y in local metres.

    Returns:
        Tuple of (x, y) arrays from the start crossing to the end crossing.
    """

    def _point(gate: _GatePass, coords: NDArray[np.float64]) -> float:
        return float(coords[gate.edge] + gate.fraction * (coords[gate.edge + 1] - coords[gate.edge]))

    inner = slice(start.edge + 1, end.edge + 1)
    sub_x = np.concatenate(([_point(start, track_x)], track_x[inner], [_point(end, track_x)]))
    sub_y = np.concatenate(([_point(start, track_y)], track_y[inner], [_point(end, track_y)]))
    return sub_x, sub_y


def _simplified_length(
    x: NDArray[np.float64],
    y: NDArray[np.float64],
    tolerance_m: float,
) -> float:
    """
    Length of a polyline after Douglas-Peucker simplification.

    Args:
        x: Polyline x in metres.
        y: Polyline y in metres.
        tolerance_m: Simplification tolerance in metres.

    Returns:
        The simplified length in metres.
    """
    keep = core_geo.simplify_indices(x, y, tolerance_m)
    return float(np.sum(np.hypot(np.diff(x[keep]), np.diff(y[keep]))))


def find_efforts(
    track_lats: ArrayLike,
    track_lons: ArrayLike,
    track_times: ArrayLike,
    segment_lats: ArrayLike,
    segment_lons: ArrayLike,
    params: MatcherParams = DEFAULT_PARAMS,
) -> list[MatchedEffort]:
    """
    Find every effort of a track over a segment.

    Args:
        track_lats: Track latitudes.
        track_lons: Track longitudes.
        track_times: Track timestamps in seconds (monotonic).
        segment_lats: Segment polyline latitudes.
        segment_lons: Segment polyline longitudes.
        params: Matching thresholds.

    Returns:
        Non-overlapping efforts in track order.
    """
    lats = core_geo.as_float_array(track_lats)
    lons = core_geo.as_float_array(track_lons)
    times = core_geo.as_float_array(track_times)
    seg_lats = core_geo.as_float_array(segment_lats)
    seg_lons = core_geo.as_float_array(segment_lons)
    if lats.size < 2 or seg_lats.size < 2 or not (lats.size == lons.size == times.size):
        return []

    ref_lat, ref_lon = float(seg_lats[0]), float(seg_lons[0])
    track_x, track_y = core_geo.to_local_xy(lats, lons, ref_lat, ref_lon)
    segment_x, segment_y = core_geo.to_local_xy(seg_lats, seg_lons, ref_lat, ref_lon)
    sample_x, sample_y, segment_length = _segment_samples(segment_x, segment_y, params.sample_spacing_m)
    if segment_length <= 0:
        return []

    cumulative = np.concatenate(([0.0], np.cumsum(np.hypot(np.diff(track_x), np.diff(track_y)))))
    start_passes = _gate_passes(
        float(segment_x[0]),
        float(segment_y[0]),
        _gate_direction(sample_x, sample_y, at_start=True),
        track_x,
        track_y,
        times,
        cumulative,
        params.gate_radius_m,
    )
    end_passes = _gate_passes(
        float(segment_x[-1]),
        float(segment_y[-1]),
        _gate_direction(sample_x, sample_y, at_start=False),
        track_x,
        track_y,
        times,
        cumulative,
        params.gate_radius_m,
    )
    if not start_passes or not end_passes:
        return []

    # A loop segment starts and ends at the same gate; its start and end
    # passes are the same runs and must not pair with themselves.
    is_loop = float(np.hypot(segment_x[-1] - segment_x[0], segment_y[-1] - segment_y[0])) < params.gate_radius_m
    min_length = params.min_length_ratio * segment_length
    max_length = params.max_length_ratio * segment_length

    efforts: list[MatchedEffort] = []
    earliest_start_along = -np.inf
    for start in start_passes:
        # Allow up to one gate radius of overlap: on a loop segment the
        # next lap's start crossing can sit just before the previous end.
        if start.along_m < earliest_start_along - params.gate_radius_m:
            continue
        for end in end_passes:
            if end.along_m <= start.along_m or (is_loop and end.run_index == start.run_index):
                continue
            # Simplification only shortens a path, so a raw length below
            # the minimum can be rejected before building the sub-track.
            if end.along_m - start.along_m < min_length:
                continue
            sub_x, sub_y = _sub_track(start, end, track_x, track_y)
            length = _simplified_length(sub_x, sub_y, params.length_simplify_m)
            if length < min_length:
                continue
            if length > max_length:
                break
            point_steps = np.diff(cumulative[start.edge : end.edge + 2])
            if point_steps.size and float(point_steps.max()) > params.max_gap_m:
                break
            distances = core_geo.distances_to_polyline(sample_x, sample_y, sub_x, sub_y)
            coverage = float(np.mean(distances <= params.corridor_m))
            if coverage < params.min_coverage or end.time <= start.time:
                continue
            efforts.append(
                MatchedEffort(
                    start_index=start.edge,
                    end_index=end.edge + 1,
                    start_time=start.time,
                    end_time=end.time,
                    distance_m=float(length),
                    coverage=coverage,
                )
            )
            earliest_start_along = end.along_m
            break
    return efforts
