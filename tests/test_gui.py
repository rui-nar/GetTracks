"""Unit tests for GUI components (mocked to avoid display issues)."""

import pytest
from unittest.mock import MagicMock, patch
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

from src.config.settings import Config
from src.models.activity import Activity
from src.gui.main_window import ActivityListWidget, ActivityDetailsWidget


@pytest.fixture(scope="session")
def qapp():
    """Create QApplication instance for tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


def test_activity_list_widget(qapp):
    """Test ActivityListWidget basic functionality."""
    widget = ActivityListWidget()

    # Create test activities
    activities = [
        Activity(
            id=1, name='Run 1', type='Run', distance=5000.0,
            moving_time=1200, elapsed_time=1250, total_elevation_gain=50.0,
            start_date_local=MagicMock(), start_date=MagicMock(),
            timezone='UTC', achievement_count=0, kudos_count=0,
            comment_count=0, athlete_count=1, photo_count=0,
            trainer=False, commute=False, manual=False, private=False,
            flagged=False, gear_id=None, average_speed=4.17, max_speed=5.5,
            has_heartrate=False, average_heartrate=None, max_heartrate=None,
            heartrate_opt_out=False, display_hide_heartrate_option=False,
            elev_high=None, elev_low=None, pr_count=0, total_photo_count=0,
            has_kudoed=False
        )
    ]

    # Mock datetime methods
    activities[0].start_date_local.strftime = MagicMock(return_value="2023-01-01 08:00")

    widget.set_activities(activities)

    assert widget.count() == 1
    assert len(widget.activities) == 1


def test_activity_details_widget(qapp):
    """Test ActivityDetailsWidget displays activity info."""
    widget = ActivityDetailsWidget()

    activity = Activity(
        id=1, name='Test Run', type='Run', distance=10000.0,
        moving_time=1800, elapsed_time=1850, total_elevation_gain=100.0,
        start_date_local=MagicMock(), start_date=MagicMock(),
        timezone='UTC', achievement_count=2, kudos_count=5,
        comment_count=1, athlete_count=1, photo_count=3,
        trainer=False, commute=False, manual=False, private=False,
        flagged=False, gear_id=None, average_speed=5.56, max_speed=7.0,
        has_heartrate=True, average_heartrate=150.0, max_heartrate=180.0,
        heartrate_opt_out=False, display_hide_heartrate_option=True,
        elev_high=200.0, elev_low=100.0, pr_count=1, total_photo_count=3,
        has_kudoed=False
    )

    # Mock datetime methods
    activity.start_date_local.strftime = MagicMock(return_value="2023-01-01 08:00")

    widget.set_activity(activity)

    assert widget.current_activity == activity
    assert widget.title_label.text() == "Test Run"
    # Details text should contain activity information
    details_text = widget.details_text.toPlainText()
    assert "Test Run" in details_text
    assert "10.00 km" in details_text
    assert "150 bpm" in details_text


def test_activity_list_selection(qapp):
    """Test activity selection functionality."""
    widget = ActivityListWidget()

    # Create test activity
    activity = Activity(
        id=1, name='Selected Run', type='Run', distance=5000.0,
        moving_time=1200, elapsed_time=1250, total_elevation_gain=50.0,
        start_date_local=MagicMock(), start_date=MagicMock(),
        timezone='UTC', achievement_count=0, kudos_count=0,
        comment_count=0, athlete_count=1, photo_count=0,
        trainer=False, commute=False, manual=False, private=False,
        flagged=False, gear_id=None, average_speed=4.17, max_speed=5.5,
        has_heartrate=False, average_heartrate=None, max_heartrate=None,
        heartrate_opt_out=False, display_hide_heartrate_option=False,
        elev_high=None, elev_low=None, pr_count=0, total_photo_count=0,
        has_kudoed=False
    )

    activity.start_date_local.strftime = MagicMock(return_value="2023-01-01 08:00")

    widget.set_activities([activity])

    # Test selection
    item = widget.item(0)
    widget.setCurrentItem(item)

    selected = widget.get_selected_activities()
    assert len(selected) == 1
    assert selected[0] == activity