"""Tests for the pure segment matching algorithm."""

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

import segments.matching.matcher as matcher
from tests._helpers import tracks

STRAIGHT = [(0.0, 0.0), (1000.0, 0.0)]


def _match(track_vertices, segment_vertices=STRAIGHT, **track_kwargs):
    lats, lons, times = tracks.track(track_vertices, **track_kwargs)
    seg_lats, seg_lons = tracks.segment(segment_vertices)
    return matcher.find_efforts(lats, lons, times, seg_lats, seg_lons)


def test_straight_pass_matches_with_expected_time():
    """A clean pass yields one effort timed from gate to gate."""
    efforts = _match([(-200.0, 0.0), (1200.0, 0.0)], speed_mps=5.0)
    assert len(efforts) == 1
    effort = efforts[0]
    assert effort.elapsed_time == pytest.approx(200.0, abs=0.5)
    assert effort.start_time == pytest.approx(40.0, abs=0.5)
    assert effort.distance_m == pytest.approx(1000.0, rel=0.01)
    assert effort.coverage == 1.0
    assert effort.start_index < effort.end_index


@pytest.mark.parametrize("seed", range(5))
def test_noisy_pass_still_matches(seed):
    """Typical GPS noise does not prevent a match."""
    efforts = _match([(-200.0, 0.0), (1200.0, 0.0)], speed_mps=5.0, noise_m=5.0, seed=seed)
    assert len(efforts) == 1
    assert efforts[0].elapsed_time == pytest.approx(200.0, abs=3.0)


def test_reverse_direction_does_not_match():
    """Segments are directional."""
    assert _match([(1200.0, 0.0), (-200.0, 0.0)]) == []


def test_out_and_back_matches_once():
    """Only the leg in segment direction counts."""
    efforts = _match([(-200.0, 0.0), (1200.0, 0.0), (-200.0, 0.0)])
    assert len(efforts) == 1


def test_three_laps_give_three_efforts():
    """Every lap over the segment is an effort, in track order."""
    lap = [(-200.0, 0.0), (1200.0, 0.0), (1200.0, 300.0), (-200.0, 300.0)]
    path = lap * 3 + [(-200.0, 0.0), (1200.0, 0.0)]
    efforts = _match(path, speed_mps=6.0)
    assert len(efforts) == 4
    starts = [effort.start_time for effort in efforts]
    assert starts == sorted(starts)
    assert all(effort.elapsed_time == pytest.approx(1000.0 / 6.0, abs=0.5) for effort in efforts)


def test_loop_segment_matches_each_lap():
    """A segment that starts and ends at the same point matches per lap."""
    square = [(0.0, 0.0), (100.0, 0.0), (100.0, 100.0), (0.0, 100.0), (0.0, 0.0)]
    path = [(-50.0, 0.0), *square, *square[1:], (50.0, 0.0)]
    efforts = _match(path, segment_vertices=square, speed_mps=4.0)
    assert len(efforts) == 2
    assert all(effort.elapsed_time == pytest.approx(100.0, abs=1.0) for effort in efforts)


def test_shortcut_does_not_match():
    """Cutting the corner of an L-shaped segment fails coverage and length."""
    corner = [(0.0, 0.0), (500.0, 0.0), (500.0, 500.0)]
    assert _match([(-100.0, 0.0), (0.0, 0.0), (500.0, 500.0), (500.0, 600.0)], segment_vertices=corner) == []


def test_parallel_road_does_not_match():
    """A road 50 m away is outside the gates and the corridor."""
    assert _match([(-200.0, 50.0), (1200.0, 50.0)]) == []


def test_large_detour_does_not_match():
    """A detour longer than the length ratio allows is rejected."""
    detour = [(-200.0, 0.0), (500.0, 0.0), (500.0, 400.0), (500.0, 0.0), (1200.0, 0.0)]
    assert _match(detour) == []


def _drop_points(lats, lons, times, x_from, x_to):
    x, _ = tracks.core_geo.to_local_xy(lats, lons, tracks.ORIGIN_LAT, tracks.ORIGIN_LON)
    keep = (x < x_from) | (x > x_to)
    return lats[keep], lons[keep], times[keep]


def test_small_gps_gap_still_matches():
    """A tunnel-sized gap below the limit is tolerated."""
    lats, lons, times = _drop_points(*tracks.track([(-200.0, 0.0), (1200.0, 0.0)]), 400.0, 600.0)
    seg_lats, seg_lons = tracks.segment(STRAIGHT)
    assert len(matcher.find_efforts(lats, lons, times, seg_lats, seg_lons)) == 1


def test_large_gps_gap_does_not_match():
    """A gap above the limit invalidates the effort."""
    lats, lons, times = _drop_points(*tracks.track([(-200.0, 0.0), (1200.0, 0.0)]), 200.0, 800.0)
    seg_lats, seg_lons = tracks.segment(STRAIGHT)
    assert matcher.find_efforts(lats, lons, times, seg_lats, seg_lons) == []


def test_smart_recording_agrees_with_one_second_recording():
    """Irregular sampling gives the same elapsed time within a second."""
    path = [(-200.0, 0.0), (1200.0, 0.0)]
    every_second = _match(path, speed_mps=4.0)
    smart = _match(path, speed_mps=4.0, interval_s=[1.0, 7.0, 3.0, 10.0, 2.0])
    assert len(every_second) == len(smart) == 1
    assert smart[0].elapsed_time == pytest.approx(every_second[0].elapsed_time, abs=1.0)


def test_track_starting_at_segment_start():
    """An activity that starts on the start gate still matches."""
    efforts = _match([(0.0, 0.0), (1200.0, 0.0)])
    assert len(efforts) == 1
    assert efforts[0].start_index == 0


def test_track_far_away_does_not_match():
    """No gate passes means no efforts."""
    assert _match([(5000.0, 5000.0), (6000.0, 5000.0)]) == []


@pytest.mark.parametrize(
    ("track_size", "segment_size"),
    [(1, 10), (10, 1), (0, 0)],
)
def test_degenerate_inputs(track_size, segment_size):
    """Too few points returns no efforts."""
    lats = np.linspace(0, 0.01, track_size)
    seg = np.linspace(0, 0.01, segment_size)
    assert matcher.find_efforts(lats, lats, np.arange(track_size), seg, seg) == []


def test_zero_length_segment():
    """A segment whose points coincide never matches."""
    lats, lons, times = tracks.track([(-200.0, 0.0), (200.0, 0.0)])
    point = tracks.to_lat_lon(np.zeros(3), np.zeros(3))
    assert matcher.find_efforts(lats, lons, times, *point) == []


def test_mismatched_track_arrays():
    """Track arrays of different lengths are rejected."""
    assert matcher.find_efforts([0, 1], [0, 1], [0], [0, 1], [0, 1]) == []


def test_custom_params_tighten_coverage():
    """A stricter corridor rejects a pass that the default accepts."""
    lats, lons, times = tracks.track([(-200.0, 0.0), (300.0, 0.0), (500.0, 20.0), (700.0, 0.0), (1200.0, 0.0)])
    seg_lats, seg_lons = tracks.segment(STRAIGHT)
    assert len(matcher.find_efforts(lats, lons, times, seg_lats, seg_lons)) == 1
    strict = matcher.MatcherParams(corridor_m=5.0, min_coverage=0.99)
    assert matcher.find_efforts(lats, lons, times, seg_lats, seg_lons, strict) == []


@settings(max_examples=25, deadline=None)
@given(
    speed=st.floats(min_value=2.0, max_value=15.0),
    lead_in=st.floats(min_value=0.0, max_value=500.0),
)
def test_elapsed_time_matches_speed(speed, lead_in):
    """Elapsed time is segment length over speed, whatever the lead-in."""
    efforts = _match([(-lead_in, 0.0), (1200.0, 0.0)], speed_mps=speed)
    assert len(efforts) == 1
    assert efforts[0].elapsed_time == pytest.approx(1000.0 / speed, abs=1.0)
    assert efforts[0].elapsed_time > 0
