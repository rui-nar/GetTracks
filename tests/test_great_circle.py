"""Tests for great_circle.py — no Qt required."""

import math
import pytest

from src.models.great_circle import great_circle_points, haversine_km


class TestGreatCirclePoints:
    def test_returns_n_points(self):
        pts = great_circle_points(0, 0, 10, 10, n_points=20)
        assert len(pts) == 20

    def test_first_point_matches_start(self):
        pts = great_circle_points(48.85, 2.35, 51.5, -0.12, n_points=50)
        assert pts[0][0] == pytest.approx(48.85, abs=1e-4)
        assert pts[0][1] == pytest.approx(2.35,  abs=1e-4)

    def test_last_point_matches_end(self):
        pts = great_circle_points(48.85, 2.35, 51.5, -0.12, n_points=50)
        assert pts[-1][0] == pytest.approx(51.5,  abs=1e-4)
        assert pts[-1][1] == pytest.approx(-0.12, abs=1e-4)

    def test_all_points_finite(self):
        pts = great_circle_points(-33.87, 151.21, 35.68, 139.69, n_points=50)
        for lat, lon in pts:
            assert math.isfinite(lat)
            assert math.isfinite(lon)

    def test_all_lats_in_range(self):
        pts = great_circle_points(-33.87, 151.21, 35.68, 139.69, n_points=50)
        for lat, lon in pts:
            assert -90.0 <= lat <= 90.0
            assert -180.0 <= lon <= 180.0

    def test_coincident_points_fallback(self):
        """Coincident endpoints return a 2-point degenerate arc without raising."""
        pts = great_circle_points(10.0, 20.0, 10.0, 20.0, n_points=50)
        assert len(pts) == 2
        assert pts[0] == (10.0, 20.0)
        assert pts[1] == (10.0, 20.0)

    def test_antipodal_points_fallback(self):
        """Antipodal endpoints (great circle undefined) return 2-point line."""
        pts = great_circle_points(0.0, 0.0, 0.0, 180.0, n_points=50)
        assert len(pts) == 2

    def test_minimum_n_points(self):
        pts = great_circle_points(0, 0, 1, 1, n_points=2)
        assert len(pts) == 2

    def test_n_points_below_2_raises(self):
        with pytest.raises(ValueError):
            great_circle_points(0, 0, 1, 1, n_points=1)

    def test_long_haul_curve(self):
        """NYC → Tokyo: intermediate points should curve through the north."""
        pts = great_circle_points(40.71, -74.01, 35.68, 139.69, n_points=100)
        max_lat = max(p[0] for p in pts)
        # Great circle between these cities peaks well above 60°N
        assert max_lat > 65.0

    def test_default_n_points(self):
        pts = great_circle_points(0, 0, 10, 10)
        assert len(pts) == 50


class TestHaversineKm:
    def test_zero_distance(self):
        assert haversine_km(48.85, 2.35, 48.85, 2.35) == pytest.approx(0.0, abs=1e-6)

    def test_paris_london_approx(self):
        """Paris → London is roughly 340 km."""
        d = haversine_km(48.85, 2.35, 51.50, -0.12)
        assert 330 < d < 360

    def test_symmetric(self):
        d1 = haversine_km(48.85, 2.35, 51.50, -0.12)
        d2 = haversine_km(51.50, -0.12, 48.85, 2.35)
        assert d1 == pytest.approx(d2, rel=1e-9)

    def test_nyc_tokyo(self):
        """NYC → Tokyo is roughly 10 800 km."""
        d = haversine_km(40.71, -74.01, 35.68, 139.69)
        assert 10_500 < d < 11_000

    def test_positive_distance(self):
        d = haversine_km(0, 0, 1, 1)
        assert d > 0
