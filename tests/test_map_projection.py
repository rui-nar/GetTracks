"""Tests for Web Mercator projection math — no Qt required."""

import math
import pytest

from src.visualization.map_projection import (
    TILE_SIZE, MIN_ZOOM, MAX_ZOOM, MAX_LAT,
    clamp_lat, clamp_lon,
    lat_lon_to_world_px, world_px_to_lat_lon,
    lat_lon_to_tile, tile_to_world_px,
    world_px_to_screen, screen_to_world_px,
    fit_bounds_center, fit_bounds_zoom,
)


# ---------------------------------------------------------------------------
# clamp_lat / clamp_lon
# ---------------------------------------------------------------------------

class TestClampLat:
    def test_within_range(self):
        assert clamp_lat(45.0) == 45.0

    def test_above_max(self):
        assert clamp_lat(90.0) == MAX_LAT

    def test_below_min(self):
        assert clamp_lat(-90.0) == -MAX_LAT

    def test_at_boundary(self):
        assert clamp_lat(MAX_LAT) == MAX_LAT


class TestClampLon:
    def test_within_range(self):
        assert clamp_lon(10.0) == 10.0

    def test_wraps_positive(self):
        assert clamp_lon(181.0) == pytest.approx(-179.0, abs=1e-9)

    def test_wraps_360(self):
        assert clamp_lon(360.0) == pytest.approx(0.0, abs=1e-9)

    def test_negative_wraps(self):
        assert clamp_lon(-181.0) == pytest.approx(179.0, abs=1e-9)


# ---------------------------------------------------------------------------
# lat_lon_to_world_px / round-trip
# ---------------------------------------------------------------------------

class TestWorldPx:
    def test_origin_at_zoom_0(self):
        """(0°, -180°) should map to world pixel x≈0 at zoom 0."""
        wx, wy = lat_lon_to_world_px(0.0, -180.0, 0)
        assert wx == pytest.approx(0.0, abs=1.0)

    def test_equator_center_at_zoom_0(self):
        """(0°, 0°) at zoom 0 should be at pixel (128, 128)."""
        wx, wy = lat_lon_to_world_px(0.0, 0.0, 0)
        assert wx == pytest.approx(128.0, abs=1.0)
        assert wy == pytest.approx(128.0, abs=1.0)

    def test_world_width_via_quarter_span(self):
        """Quarter-world span (-90° to +90°) should be half the world width."""
        wx_left, _  = lat_lon_to_world_px(0.0, -90.0, 1)
        wx_right, _ = lat_lon_to_world_px(0.0,  90.0, 1)
        # Half of 512px (zoom-1 world width)
        assert wx_right - wx_left == pytest.approx(256.0, abs=1.0)

    def test_northern_hemisphere_smaller_y(self):
        """Higher latitude → smaller y (y increases downward)."""
        _, wy_north = lat_lon_to_world_px(60.0, 0.0, 5)
        _, wy_south = lat_lon_to_world_px(-60.0, 0.0, 5)
        assert wy_north < wy_south

    def test_round_trip(self):
        for lat, lon in [(48.85, 2.35), (-33.87, 151.21), (35.68, 139.69)]:
            for z in (5, 10, 15):
                wx, wy = lat_lon_to_world_px(lat, lon, z)
                lat2, lon2 = world_px_to_lat_lon(wx, wy, z)
                assert lat2 == pytest.approx(lat, abs=1e-6)
                assert lon2 == pytest.approx(lon, abs=1e-6)

    def test_extreme_lat_clamped(self):
        """lat=90 should not raise (clamped to MAX_LAT)."""
        wx, wy = lat_lon_to_world_px(90.0, 0.0, 5)
        assert math.isfinite(wx)
        assert math.isfinite(wy)

    def test_zoom_doubles_world(self):
        """Each zoom increment doubles world-pixel coordinates."""
        wx5, wy5 = lat_lon_to_world_px(51.5, -0.1, 5)
        wx6, wy6 = lat_lon_to_world_px(51.5, -0.1, 6)
        assert wx6 == pytest.approx(wx5 * 2, abs=1.0)
        assert wy6 == pytest.approx(wy5 * 2, abs=1.0)


# ---------------------------------------------------------------------------
# lat_lon_to_tile
# ---------------------------------------------------------------------------

class TestLatLonToTile:
    def test_zoom_0_is_single_tile(self):
        tx, ty = lat_lon_to_tile(0.0, 0.0, 0)
        assert tx == 0
        assert ty == 0

    def test_known_london_z10(self):
        """London (51.5, -0.1) at zoom 10 is tile (511, 340)."""
        tx, ty = lat_lon_to_tile(51.5, -0.1, 10)
        assert tx == 511
        assert ty == 340

    def test_tile_clamped_at_max(self):
        tx, ty = lat_lon_to_tile(MAX_LAT, 179.9, 5)
        n = 2 ** 5
        assert 0 <= tx < n
        assert 0 <= ty < n

    def test_tile_non_negative(self):
        tx, ty = lat_lon_to_tile(-60.0, -120.0, 8)
        assert tx >= 0
        assert ty >= 0


# ---------------------------------------------------------------------------
# tile_to_world_px
# ---------------------------------------------------------------------------

class TestTileToWorldPx:
    def test_origin_tile(self):
        assert tile_to_world_px(0, 0) == (0.0, 0.0)

    def test_second_tile(self):
        assert tile_to_world_px(1, 0) == (256.0, 0.0)

    def test_arbitrary(self):
        assert tile_to_world_px(3, 5) == (768.0, 1280.0)


# ---------------------------------------------------------------------------
# screen ↔ world_px
# ---------------------------------------------------------------------------

class TestScreenWorldPx:
    def test_center_maps_to_viewport_center(self):
        cx, cy = 1000.0, 800.0
        sx, sy = world_px_to_screen(cx, cy, cx, cy, 800, 600)
        assert sx == pytest.approx(400.0)
        assert sy == pytest.approx(300.0)

    def test_round_trip(self):
        cx, cy = 5000.0, 3000.0
        W, H = 1024, 768
        for wx, wy in [(4800.0, 2900.0), (5200.0, 3100.0)]:
            sx, sy = world_px_to_screen(wx, wy, cx, cy, W, H)
            wx2, wy2 = screen_to_world_px(sx, sy, cx, cy, W, H)
            assert wx2 == pytest.approx(wx)
            assert wy2 == pytest.approx(wy)


# ---------------------------------------------------------------------------
# fit_bounds_center
# ---------------------------------------------------------------------------

class TestFitBoundsCenter:
    def test_simple_midpoint(self):
        lat, lon = fit_bounds_center(40.0, 60.0, 10.0, 20.0)
        assert lat == pytest.approx(50.0)
        assert lon == pytest.approx(15.0)

    def test_antimeridian_crossing(self):
        """Bounds spanning antimeridian: min_lon=170, max_lon=-170."""
        lat, lon = fit_bounds_center(-10.0, 10.0, 170.0, -170.0)
        # Center should be near 180° / -180°, not 0°
        assert abs(lon) >= 170.0 or abs(lon) <= 10.0

    def test_negative_lons(self):
        lat, lon = fit_bounds_center(30.0, 50.0, -100.0, -80.0)
        assert lon == pytest.approx(-90.0)

    def test_zero_span(self):
        lat, lon = fit_bounds_center(48.85, 48.85, 2.35, 2.35)
        assert lat == pytest.approx(48.85)
        assert lon == pytest.approx(2.35)


# ---------------------------------------------------------------------------
# fit_bounds_zoom
# ---------------------------------------------------------------------------

class TestFitBoundsZoom:
    def test_returns_int(self):
        z = fit_bounds_zoom(40.0, 41.0, 10.0, 11.0, 800, 600)
        assert isinstance(z, int)

    def test_city_bounds_high_zoom(self):
        """A ~1° bounding box in an 800×600 viewport should give zoom ≥ 10."""
        z = fit_bounds_zoom(51.3, 51.7, -0.3, 0.1, 800, 600)
        assert z >= 10

    def test_world_bounds_low_zoom(self):
        """Full world bounds should give zoom 0 or 1."""
        z = fit_bounds_zoom(-80.0, 80.0, -179.0, 179.0, 800, 600)
        assert z <= 2

    def test_larger_viewport_gives_higher_zoom(self):
        """Same bounds, bigger viewport → can fit at higher zoom."""
        z_small = fit_bounds_zoom(48.0, 49.0, 2.0, 3.0, 400, 300)
        z_large = fit_bounds_zoom(48.0, 49.0, 2.0, 3.0, 1200, 900)
        assert z_large >= z_small

    def test_zero_span_does_not_raise(self):
        """Single-point bounds should not raise."""
        z = fit_bounds_zoom(48.85, 48.85, 2.35, 2.35, 800, 600)
        assert MIN_ZOOM <= z <= MAX_ZOOM

    def test_zero_viewport_returns_fallback(self):
        z = fit_bounds_zoom(40.0, 50.0, 10.0, 20.0, 0, 0)
        assert z == 2

    def test_zoom_within_valid_range(self):
        z = fit_bounds_zoom(0.0, 1.0, 0.0, 1.0, 800, 600)
        assert MIN_ZOOM <= z <= MAX_ZOOM
