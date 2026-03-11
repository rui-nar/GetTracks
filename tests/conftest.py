"""Shared fixtures for all test modules."""

from datetime import datetime
import pytest

from src.models.activity import Activity


@pytest.fixture
def make_activity():
    """Factory fixture — call with keyword overrides to customise any field."""
    def _make(**kwargs):
        defaults = dict(
            id=1,
            name="Morning Run",
            type="Run",
            distance=10000.0,
            moving_time=3600,
            elapsed_time=3660,
            total_elevation_gain=100.0,
            start_date=datetime(2024, 6, 15, 7, 0),
            start_date_local=datetime(2024, 6, 15, 9, 0),
            timezone="Europe/Paris",
            achievement_count=2,
            kudos_count=5,
            comment_count=1,
            athlete_count=1,
            photo_count=0,
            trainer=False,
            commute=False,
            manual=False,
            private=False,
            flagged=False,
            average_speed=2.78,   # m/s ≈ 10 km/h
            max_speed=3.5,
            has_heartrate=False,
            pr_count=0,
            total_photo_count=0,
            has_kudoed=False,
        )
        defaults.update(kwargs)
        return Activity(**defaults)
    return _make
