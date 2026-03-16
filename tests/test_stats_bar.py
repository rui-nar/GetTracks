"""Tests for StatsBarWidget."""

import pytest
from datetime import datetime, timezone

from src.gui.stats_bar import StatsBarWidget, _fmt_time
from src.models.activity import Activity


# ---------------------------------------------------------------------------
# _fmt_time helper
# ---------------------------------------------------------------------------

class TestFmtTime:
    def test_minutes_only(self):
        assert _fmt_time(1800) == "30m"

    def test_hours_and_minutes(self):
        assert _fmt_time(5400) == "1h 30m"

    def test_whole_hours(self):
        assert _fmt_time(7200) == "2h 00m"

    def test_large_hours(self):
        # ≥10h → show only hours
        assert _fmt_time(36000) == "10h"

    def test_zero(self):
        assert _fmt_time(0) == "0m"


# ---------------------------------------------------------------------------
# StatsBarWidget
# ---------------------------------------------------------------------------

def _act(id, distance=10000, moving_time=3600, elevation=100):
    dt = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    return Activity(
        id=id, name=f"A{id}", type="Run",
        distance=distance, moving_time=moving_time, elapsed_time=moving_time,
        total_elevation_gain=elevation,
        start_date=dt, start_date_local=dt, timezone="UTC",
        achievement_count=0, kudos_count=0, comment_count=0,
        athlete_count=1, photo_count=0,
        trainer=False, commute=False, manual=False, private=False, flagged=False,
        average_speed=2.78, max_speed=5.0, has_heartrate=False,
        pr_count=0, total_photo_count=0, has_kudoed=False,
    )


class TestStatsBarWidget:
    @pytest.fixture
    def bar(self, qtbot):
        w = StatsBarWidget()
        qtbot.addWidget(w)
        return w

    def test_initial_shows_zero_activities(self, bar):
        assert "0" in bar._count_lbl.text()

    def test_update_stats_single_activity(self, bar):
        bar.update_stats([_act(1, distance=5000)])
        assert "1 activity" in bar._count_lbl.text()
        assert "5.0 km" in bar._dist_lbl.text()

    def test_update_stats_plural(self, bar):
        bar.update_stats([_act(1), _act(2)])
        assert "2 activities" in bar._count_lbl.text()

    def test_distance_sums_correctly(self, bar):
        bar.update_stats([_act(1, distance=10000), _act(2, distance=5000)])
        assert "15.0 km" in bar._dist_lbl.text()

    def test_elevation_sums_correctly(self, bar):
        bar.update_stats([_act(1, elevation=200), _act(2, elevation=300)])
        assert "500" in bar._elev_lbl.text()

    def test_empty_list_clears_stats(self, bar):
        bar.update_stats([_act(1)])
        bar.update_stats([])
        assert bar._dist_lbl.text() == ""
        assert bar._elev_lbl.text() == ""
        assert bar._time_lbl.text() == ""

    def test_elevation_label_has_up_arrow(self, bar):
        bar.update_stats([_act(1, elevation=100)])
        assert "↑" in bar._elev_lbl.text()

    def test_time_label_present(self, bar):
        bar.update_stats([_act(1, moving_time=3600)])
        assert bar._time_lbl.text() != ""
