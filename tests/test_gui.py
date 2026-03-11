"""pytest-qt tests for ActivityListWidget and ActivityDetailsWidget."""

from datetime import datetime

import pytest
from PyQt6.QtCore import Qt

from src.gui.main_window import ActivityListWidget, ActivityDetailsWidget


# ---------------------------------------------------------------------------
# ActivityListWidget
# ---------------------------------------------------------------------------

class TestActivityListWidget:

    def test_empty_list_shows_no_items(self, qtbot):
        w = ActivityListWidget()
        qtbot.addWidget(w)
        w.set_activities([])
        assert w.count() == 0

    def test_set_activities_populates_items(self, qtbot, make_activity):
        w = ActivityListWidget()
        qtbot.addWidget(w)
        w.set_activities([make_activity(id=1), make_activity(id=2)])
        assert w.count() == 2

    def test_set_activities_stores_activity_count(self, qtbot, make_activity):
        w = ActivityListWidget()
        qtbot.addWidget(w)
        activities = [make_activity(id=i) for i in range(5)]
        w.set_activities(activities)
        assert len(w.activities) == 5

    def test_item_text_contains_name(self, qtbot, make_activity):
        w = ActivityListWidget()
        qtbot.addWidget(w)
        w.set_activities([make_activity(name="Sunday Long Run")])
        assert "Sunday Long Run" in w.item(0).text()

    def test_item_text_contains_type(self, qtbot, make_activity):
        w = ActivityListWidget()
        qtbot.addWidget(w)
        w.set_activities([make_activity(type="Ride")])
        assert "Ride" in w.item(0).text()

    def test_item_text_contains_distance_km(self, qtbot, make_activity):
        w = ActivityListWidget()
        qtbot.addWidget(w)
        w.set_activities([make_activity(distance=21097.5)])
        assert "21.1" in w.item(0).text()

    def test_item_text_contains_date(self, qtbot, make_activity):
        w = ActivityListWidget()
        qtbot.addWidget(w)
        w.set_activities([make_activity(start_date_local=datetime(2025, 8, 20, 7, 30))])
        assert "2025-08-20" in w.item(0).text()

    def test_item_stores_activity_as_user_role(self, qtbot, make_activity):
        w = ActivityListWidget()
        qtbot.addWidget(w)
        activity = make_activity()
        w.set_activities([activity])
        stored = w.item(0).data(Qt.ItemDataRole.UserRole)
        assert stored is activity

    def test_set_activities_clears_previous(self, qtbot, make_activity):
        w = ActivityListWidget()
        qtbot.addWidget(w)
        w.set_activities([make_activity(id=1), make_activity(id=2)])
        w.set_activities([make_activity(id=3)])
        assert w.count() == 1

    def test_activity_selected_signal_emitted_on_click(self, qtbot, make_activity):
        w = ActivityListWidget()
        qtbot.addWidget(w)
        activity = make_activity()
        w.set_activities([activity])
        received = []
        w.activity_selected.connect(received.append)
        w.itemClicked.emit(w.item(0))
        assert len(received) == 1

    def test_activity_selected_signal_carries_correct_activity(self, qtbot, make_activity):
        w = ActivityListWidget()
        qtbot.addWidget(w)
        activity = make_activity(name="Specific Activity")
        w.set_activities([activity])
        received = []
        w.activity_selected.connect(received.append)
        w.itemClicked.emit(w.item(0))
        assert received[0].name == "Specific Activity"

    def test_get_selected_activities_returns_selection(self, qtbot, make_activity):
        w = ActivityListWidget()
        qtbot.addWidget(w)
        activity = make_activity()
        w.set_activities([activity])
        w.setCurrentItem(w.item(0))
        assert len(w.get_selected_activities()) == 1
        assert w.get_selected_activities()[0] is activity

    def test_get_selected_activities_empty_when_none_selected(self, qtbot, make_activity):
        w = ActivityListWidget()
        qtbot.addWidget(w)
        w.set_activities([make_activity()])
        assert w.get_selected_activities() == []

    def test_ordering_preserved(self, qtbot, make_activity):
        w = ActivityListWidget()
        qtbot.addWidget(w)
        activities = [make_activity(id=i, name=f"Activity {i}") for i in range(3)]
        w.set_activities(activities)
        for i in range(3):
            item = w.item(i)
            stored = item.data(Qt.ItemDataRole.UserRole)
            assert stored.id == i


# ---------------------------------------------------------------------------
# ActivityDetailsWidget
# ---------------------------------------------------------------------------

class TestActivityDetailsWidget:

    def test_initial_placeholder_text(self, qtbot):
        w = ActivityDetailsWidget()
        qtbot.addWidget(w)
        assert "Select" in w.title_label.text()

    def test_set_activity_updates_title(self, qtbot, make_activity):
        w = ActivityDetailsWidget()
        qtbot.addWidget(w)
        w.set_activity(make_activity(name="Evening Ride"))
        assert w.title_label.text() == "Evening Ride"

    def test_set_activity_stores_current(self, qtbot, make_activity):
        w = ActivityDetailsWidget()
        qtbot.addWidget(w)
        activity = make_activity()
        w.set_activity(activity)
        assert w.current_activity is activity

    def test_details_contains_type(self, qtbot, make_activity):
        w = ActivityDetailsWidget()
        qtbot.addWidget(w)
        w.set_activity(make_activity(type="Hike"))
        assert "Hike" in w.details_text.toPlainText()

    def test_details_contains_distance(self, qtbot, make_activity):
        w = ActivityDetailsWidget()
        qtbot.addWidget(w)
        w.set_activity(make_activity(distance=42195.0))
        assert "42.20" in w.details_text.toPlainText()

    def test_details_contains_date(self, qtbot, make_activity):
        w = ActivityDetailsWidget()
        qtbot.addWidget(w)
        w.set_activity(make_activity(start_date_local=datetime(2025, 11, 5, 6, 0)))
        assert "2025-11-05" in w.details_text.toPlainText()

    def test_details_contains_elevation(self, qtbot, make_activity):
        w = ActivityDetailsWidget()
        qtbot.addWidget(w)
        w.set_activity(make_activity(total_elevation_gain=350.0))
        assert "350" in w.details_text.toPlainText()

    def test_details_shows_heartrate_when_available(self, qtbot, make_activity):
        w = ActivityDetailsWidget()
        qtbot.addWidget(w)
        w.set_activity(make_activity(
            has_heartrate=True,
            average_heartrate=155.0,
            max_heartrate=182,
        ))
        text = w.details_text.toPlainText()
        assert "155" in text
        assert "182" in text

    def test_details_omits_heartrate_when_unavailable(self, qtbot, make_activity):
        w = ActivityDetailsWidget()
        qtbot.addWidget(w)
        w.set_activity(make_activity(has_heartrate=False, average_heartrate=None))
        assert "bpm" not in w.details_text.toPlainText()

    def test_details_contains_kudos(self, qtbot, make_activity):
        w = ActivityDetailsWidget()
        qtbot.addWidget(w)
        w.set_activity(make_activity(kudos_count=42))
        assert "42" in w.details_text.toPlainText()

    def test_replacing_activity_updates_title(self, qtbot, make_activity):
        w = ActivityDetailsWidget()
        qtbot.addWidget(w)
        w.set_activity(make_activity(name="First"))
        w.set_activity(make_activity(name="Second"))
        assert w.title_label.text() == "Second"
