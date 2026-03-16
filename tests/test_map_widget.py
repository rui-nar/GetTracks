"""Tests for MapWidget static helpers — no WebEngine / display required."""

from datetime import datetime

import polyline as polyline_codec
import pytest

from src.models.activity import Activity
from src.models.track import Track, TrackPoint
from src.visualization.map_widget import (
    MapWidget, _DEFAULT_COLOR, _TYPE_COLORS, _TRACK_PALETTE, _TILE_OPTIONS
)

# A known encoded polyline (3-point route near London) and its decoded coords.
_COORDS = [(51.5074, -0.1278), (51.5080, -0.1284), (51.5090, -0.1295)]
_ENCODED = polyline_codec.encode(_COORDS)


def _make(id=1, type="Run", start_latlng=None, polyline=None,
          distance=10000.0, moving_time=3600, **kwargs):
    return Activity(
        id=id, name="Test", type=type,
        distance=distance, moving_time=moving_time, elapsed_time=moving_time + 60,
        total_elevation_gain=50.0,
        start_date=datetime(2024, 6, 15, 7, 0),
        start_date_local=datetime(2024, 6, 15, 9, 0),
        timezone="UTC",
        achievement_count=0, kudos_count=0, comment_count=0,
        athlete_count=1, photo_count=0,
        trainer=False, commute=False, manual=False, private=False, flagged=False,
        average_speed=2.78, max_speed=3.5,
        has_heartrate=False, pr_count=0, total_photo_count=0, has_kudoed=False,
        start_latlng=start_latlng,
        summary_polyline=polyline,
        **kwargs,
    )


# ---------------------------------------------------------------------------
# _decode_polyline
# ---------------------------------------------------------------------------

def test_decode_polyline_valid_returns_coords():
    activity = _make(polyline=_ENCODED)
    result = MapWidget._decode_polyline(activity)
    assert result is not None
    assert len(result) == len(_COORDS)


def test_decode_polyline_values_match():
    activity = _make(polyline=_ENCODED)
    result = MapWidget._decode_polyline(activity)
    for (rlat, rlng), (elat, elng) in zip(result, _COORDS):
        assert abs(rlat - elat) < 1e-4
        assert abs(rlng - elng) < 1e-4


def test_decode_polyline_none_returns_none():
    assert MapWidget._decode_polyline(_make(polyline=None)) is None


def test_decode_polyline_empty_string_returns_none():
    assert MapWidget._decode_polyline(_make(polyline="")) is None


def test_decode_polyline_invalid_string_returns_coords():
    # polyline.decode never raises — it happily decodes any bytes as numbers.
    # The important contract is: no crash, some result is returned.
    result = MapWidget._decode_polyline(_make(polyline="!!!invalid!!!"))
    # result may be arbitrary coords, but it must be a list (not None)
    assert isinstance(result, list)


def test_decode_polyline_single_point():
    encoded = polyline_codec.encode([(51.5, -0.1)])
    result = MapWidget._decode_polyline(_make(polyline=encoded))
    assert result is not None
    assert len(result) == 1


# ---------------------------------------------------------------------------
# _build_popup
# ---------------------------------------------------------------------------

def test_build_popup_contains_name():
    activity = _make()
    activity = Activity(**{**activity.__dict__, "name": "Epic Ride"})
    html = MapWidget._build_popup(activity)
    assert "Epic Ride" in html


def test_build_popup_contains_type():
    activity = _make(type="Ride")
    assert "Ride" in MapWidget._build_popup(activity)


def test_build_popup_contains_distance_km():
    activity = _make(distance=15000.0)
    assert "15.00" in MapWidget._build_popup(activity)


def test_build_popup_contains_date():
    activity = _make()
    assert "2024-06-15" in MapWidget._build_popup(activity)


def test_build_popup_time_hours_and_minutes():
    activity = _make(moving_time=5400)  # 1h 30m
    html = MapWidget._build_popup(activity)
    assert "1h" in html
    assert "30" in html


def test_build_popup_returns_html_string():
    html = MapWidget._build_popup(_make())
    assert html.startswith("<div")
    assert "</div>" in html


# ---------------------------------------------------------------------------
# _calculate_center
# ---------------------------------------------------------------------------

def test_calculate_center_single_activity():
    activity = _make(start_latlng=[51.5, -0.1])
    lat, lng = MapWidget._calculate_center([activity])
    assert abs(lat - 51.5) < 1e-6
    assert abs(lng - (-0.1)) < 1e-6


def test_calculate_center_two_activities():
    a1 = _make(id=1, start_latlng=[50.0, -1.0])
    a2 = _make(id=2, start_latlng=[52.0, -3.0])
    lat, lng = MapWidget._calculate_center([a1, a2])
    assert abs(lat - 51.0) < 1e-6
    assert abs(lng - (-2.0)) < 1e-6


def test_calculate_center_skips_activities_without_latlng():
    a_with = _make(id=1, start_latlng=[50.0, 10.0])
    a_without = _make(id=2, start_latlng=None)
    lat, lng = MapWidget._calculate_center([a_with, a_without])
    assert abs(lat - 50.0) < 1e-6


def test_calculate_center_empty_list_returns_default():
    lat, lng = MapWidget._calculate_center([])
    assert lat == 40.7128
    assert lng == -74.0060


def test_calculate_center_no_latlng_activities_returns_default():
    activities = [_make(id=i, start_latlng=None) for i in range(3)]
    lat, lng = MapWidget._calculate_center(activities)
    assert lat == 40.7128
    assert lng == -74.0060


# ---------------------------------------------------------------------------
# _midpoint
# ---------------------------------------------------------------------------

def test_midpoint_odd_length():
    coords = [(1.0, 1.0), (2.0, 2.0), (3.0, 3.0)]
    assert MapWidget._midpoint(coords) == (2.0, 2.0)


def test_midpoint_even_length():
    coords = [(1.0, 1.0), (2.0, 2.0), (3.0, 3.0), (4.0, 4.0)]
    assert MapWidget._midpoint(coords) == (3.0, 3.0)


def test_midpoint_single_element():
    coords = [(5.0, 10.0)]
    assert MapWidget._midpoint(coords) == (5.0, 10.0)


# ---------------------------------------------------------------------------
# Color mapping
# ---------------------------------------------------------------------------

def test_run_uses_blue_color():
    assert _TYPE_COLORS["run"] == "#3388ff"


def test_ride_uses_red_color():
    assert _TYPE_COLORS["ride"] == "#e03030"


def test_unknown_type_falls_back_to_default():
    assert _DEFAULT_COLOR == "#666666"


# ---------------------------------------------------------------------------
# _TRACK_PALETTE
# ---------------------------------------------------------------------------

def test_track_palette_has_entries():
    assert len(_TRACK_PALETTE) >= 2


def test_track_palette_colors_are_hex():
    for color in _TRACK_PALETTE:
        assert color.startswith("#")
        assert len(color) == 7


def test_track_palette_cycles_without_index_error():
    for i in range(len(_TRACK_PALETTE) * 3):
        _ = _TRACK_PALETTE[i % len(_TRACK_PALETTE)]


# ---------------------------------------------------------------------------
# _TILE_OPTIONS
# ---------------------------------------------------------------------------

def test_tile_options_has_at_least_two_entries():
    assert len(_TILE_OPTIONS) >= 2


def test_tile_options_contains_openstreetmap():
    assert any("OpenStreetMap" in v for v in _TILE_OPTIONS.values())


def test_tile_options_keys_are_strings():
    for k in _TILE_OPTIONS:
        assert isinstance(k, str)


def test_tile_options_values_are_strings():
    for v in _TILE_OPTIONS.values():
        assert isinstance(v, str)
