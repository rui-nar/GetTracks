"""Unit tests for TrackPoint and Track models."""

from datetime import datetime, timezone

import pytest

from src.models.track import Track, TrackPoint


# ---------------------------------------------------------------------------
# TrackPoint
# ---------------------------------------------------------------------------

class TestTrackPoint:

    def test_required_fields(self):
        pt = TrackPoint(lat=48.8566, lon=2.3522)
        assert pt.lat == 48.8566
        assert pt.lon == 2.3522

    def test_elevation_defaults_to_none(self):
        assert TrackPoint(lat=0.0, lon=0.0).elevation is None

    def test_time_defaults_to_none(self):
        assert TrackPoint(lat=0.0, lon=0.0).time is None

    def test_elevation_stored(self):
        pt = TrackPoint(lat=0.0, lon=0.0, elevation=250.5)
        assert pt.elevation == 250.5

    def test_time_stored(self):
        t = datetime(2025, 6, 1, 8, 0, tzinfo=timezone.utc)
        pt = TrackPoint(lat=0.0, lon=0.0, time=t)
        assert pt.time == t

    def test_negative_coordinates(self):
        pt = TrackPoint(lat=-33.8688, lon=-70.6693)
        assert pt.lat < 0
        assert pt.lon < 0


# ---------------------------------------------------------------------------
# Track
# ---------------------------------------------------------------------------

class TestTrack:

    def _make_track(self, n_points=3, **kwargs):
        pts = [TrackPoint(lat=float(i), lon=float(i)) for i in range(n_points)]
        defaults = dict(
            activity_id=1,
            activity_name="Morning Run",
            start_time=datetime(2025, 6, 1, 7, 0, tzinfo=timezone.utc),
            points=pts,
        )
        defaults.update(kwargs)
        return Track(**defaults)

    def test_required_fields_stored(self):
        t = self._make_track()
        assert t.activity_id == 1
        assert t.activity_name == "Morning Run"
        assert t.start_time == datetime(2025, 6, 1, 7, 0, tzinfo=timezone.utc)

    def test_points_default_empty(self):
        t = Track(activity_id=1, activity_name="x",
                  start_time=datetime(2025, 1, 1, tzinfo=timezone.utc))
        assert t.points == []

    def test_len_matches_points(self):
        t = self._make_track(n_points=5)
        assert len(t) == 5

    def test_len_empty(self):
        t = self._make_track(n_points=0)
        assert len(t) == 0

    def test_is_empty_true(self):
        t = self._make_track(n_points=0)
        assert t.is_empty() is True

    def test_is_empty_false(self):
        t = self._make_track(n_points=1)
        assert t.is_empty() is False

    def test_points_list_accessible(self):
        pts = [TrackPoint(lat=1.0, lon=2.0), TrackPoint(lat=3.0, lon=4.0)]
        t = Track(activity_id=2, activity_name="Ride",
                  start_time=datetime(2025, 1, 1, tzinfo=timezone.utc),
                  points=pts)
        assert len(t.points) == 2
        assert t.points[0].lat == 1.0

    def test_independent_points_lists(self):
        """Two tracks with default points must not share the same list."""
        t1 = Track(activity_id=1, activity_name="a",
                   start_time=datetime(2025, 1, 1, tzinfo=timezone.utc))
        t2 = Track(activity_id=2, activity_name="b",
                   start_time=datetime(2025, 1, 2, tzinfo=timezone.utc))
        t1.points.append(TrackPoint(lat=0.0, lon=0.0))
        assert len(t2.points) == 0

    def test_activity_id_preserved(self):
        t = self._make_track(activity_id=42)
        assert t.activity_id == 42

    def test_activity_name_preserved(self):
        t = self._make_track(activity_name="Evening Hike")
        assert t.activity_name == "Evening Hike"
