"""pytest-qt tests for FilterWidget."""

from datetime import date

import pytest
from PyQt6.QtCore import QDate

from src.filters.filter_engine import FilterCriteria
from src.gui.filter_widget import FilterWidget, _DEFAULT_START


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _widget(qtbot):
    w = FilterWidget()
    qtbot.addWidget(w)
    return w


def _collect_signals(widget):
    """Return a list that accumulates every FilterCriteria emitted."""
    received = []
    widget.filters_changed.connect(received.append)
    return received


# ---------------------------------------------------------------------------
# Initial state
# ---------------------------------------------------------------------------

def test_initial_start_date(qtbot):
    assert _widget(qtbot)._start_date.date() == _DEFAULT_START


def test_initial_end_date_is_today(qtbot):
    assert _widget(qtbot)._end_date.date() == QDate.currentDate()


def test_initial_no_type_checkboxes(qtbot):
    assert _widget(qtbot)._type_checkboxes == {}


def test_initial_apply_button_exists(qtbot):
    w = _widget(qtbot)
    assert w._apply_btn.text() == "Apply Filters"


def test_initial_clear_button_exists(qtbot):
    w = _widget(qtbot)
    assert w._clear_btn.text() == "Clear"


# ---------------------------------------------------------------------------
# build_criteria — dates
# ---------------------------------------------------------------------------

def test_build_criteria_captures_start_date(qtbot):
    w = _widget(qtbot)
    w._start_date.setDate(QDate(2025, 1, 1))
    assert w.build_criteria().start_date == date(2025, 1, 1)


def test_build_criteria_captures_end_date(qtbot):
    w = _widget(qtbot)
    w._end_date.setDate(QDate(2025, 6, 30))
    assert w.build_criteria().end_date == date(2025, 6, 30)


def test_build_criteria_start_before_end(qtbot):
    w = _widget(qtbot)
    w._start_date.setDate(QDate(2025, 1, 1))
    w._end_date.setDate(QDate(2025, 12, 31))
    c = w.build_criteria()
    assert c.start_date < c.end_date


def test_build_criteria_dates_are_date_objects(qtbot):
    w = _widget(qtbot)
    c = w.build_criteria()
    assert isinstance(c.start_date, date)
    assert isinstance(c.end_date, date)


# ---------------------------------------------------------------------------
# build_criteria — activity types
# ---------------------------------------------------------------------------

def test_build_criteria_no_type_filter_when_no_checkboxes(qtbot):
    assert _widget(qtbot).build_criteria().activity_types is None


def test_build_criteria_no_type_filter_when_all_checked(qtbot, make_activity):
    w = _widget(qtbot)
    w.populate_types([make_activity(type="Run"), make_activity(id=2, type="Ride")])
    # All checked by default → no type constraint
    assert w.build_criteria().activity_types is None


def test_build_criteria_type_filter_when_one_unchecked(qtbot, make_activity):
    w = _widget(qtbot)
    w.populate_types([make_activity(type="Run"), make_activity(id=2, type="Ride")])
    w._type_checkboxes["Ride"].setChecked(False)
    c = w.build_criteria()
    assert c.activity_types == {"Run"}


def test_build_criteria_type_filter_multiple_unchecked(qtbot, make_activity):
    w = _widget(qtbot)
    activities = [
        make_activity(id=1, type="Run"),
        make_activity(id=2, type="Ride"),
        make_activity(id=3, type="Hike"),
    ]
    w.populate_types(activities)
    w._type_checkboxes["Ride"].setChecked(False)
    w._type_checkboxes["Hike"].setChecked(False)
    assert w.build_criteria().activity_types == {"Run"}


def test_build_criteria_all_unchecked_returns_empty_set(qtbot, make_activity):
    w = _widget(qtbot)
    w.populate_types([make_activity(type="Run")])
    w._type_checkboxes["Run"].setChecked(False)
    assert w.build_criteria().activity_types == set()


# ---------------------------------------------------------------------------
# Apply button
# ---------------------------------------------------------------------------

def test_apply_emits_filters_changed(qtbot):
    w = _widget(qtbot)
    received = _collect_signals(w)
    qtbot.mouseClick(w._apply_btn, pytest.importorskip("PyQt6.QtCore").Qt.MouseButton.LeftButton)
    assert len(received) == 1


def test_apply_emits_correct_dates(qtbot):
    w = _widget(qtbot)
    w._start_date.setDate(QDate(2025, 3, 1))
    w._end_date.setDate(QDate(2025, 9, 30))
    received = _collect_signals(w)
    w._on_apply()
    assert received[0].start_date == date(2025, 3, 1)
    assert received[0].end_date == date(2025, 9, 30)


def test_apply_emits_type_filter_when_unchecked(qtbot, make_activity):
    w = _widget(qtbot)
    w.populate_types([make_activity(type="Run"), make_activity(id=2, type="Ride")])
    w._type_checkboxes["Ride"].setChecked(False)
    received = _collect_signals(w)
    w._on_apply()
    assert received[0].activity_types == {"Run"}


def test_apply_emits_filterCriteria_instance(qtbot):
    w = _widget(qtbot)
    received = _collect_signals(w)
    w._on_apply()
    assert isinstance(received[0], FilterCriteria)


def test_no_signal_on_date_change_without_apply(qtbot):
    w = _widget(qtbot)
    received = _collect_signals(w)
    w._start_date.setDate(QDate(2026, 1, 1))
    assert received == []


# ---------------------------------------------------------------------------
# Clear button
# ---------------------------------------------------------------------------

def test_clear_resets_start_date(qtbot):
    w = _widget(qtbot)
    w._start_date.setDate(QDate(2025, 6, 1))
    w._on_clear()
    assert w._start_date.date() == _DEFAULT_START


def test_clear_resets_end_date_to_today(qtbot):
    w = _widget(qtbot)
    w._end_date.setDate(QDate(2020, 1, 1))
    w._on_clear()
    assert w._end_date.date() == QDate.currentDate()


def test_clear_rechecks_all_type_boxes(qtbot, make_activity):
    w = _widget(qtbot)
    w.populate_types([make_activity(type="Run"), make_activity(id=2, type="Ride")])
    w._type_checkboxes["Run"].setChecked(False)
    w._on_clear()
    assert all(cb.isChecked() for cb in w._type_checkboxes.values())


def test_clear_emits_empty_criteria(qtbot):
    w = _widget(qtbot)
    received = _collect_signals(w)
    w._on_clear()
    assert len(received) == 1
    assert received[0].is_empty()


# ---------------------------------------------------------------------------
# populate_types
# ---------------------------------------------------------------------------

def test_populate_types_creates_checkboxes(qtbot, make_activity):
    w = _widget(qtbot)
    w.populate_types([make_activity(type="Run"), make_activity(id=2, type="Ride")])
    assert set(w._type_checkboxes.keys()) == {"Run", "Ride"}


def test_populate_types_all_checked_initially(qtbot, make_activity):
    w = _widget(qtbot)
    w.populate_types([make_activity(type="Run"), make_activity(id=2, type="Walk")])
    assert all(cb.isChecked() for cb in w._type_checkboxes.values())


def test_populate_types_sorted_alphabetically(qtbot, make_activity):
    w = _widget(qtbot)
    activities = [
        make_activity(id=1, type="Walk"),
        make_activity(id=2, type="Run"),
        make_activity(id=3, type="Hike"),
    ]
    w.populate_types(activities)
    assert list(w._type_checkboxes.keys()) == ["Hike", "Run", "Walk"]


def test_populate_types_deduplicates(qtbot, make_activity):
    w = _widget(qtbot)
    w.populate_types([make_activity(id=1, type="Run"), make_activity(id=2, type="Run")])
    assert list(w._type_checkboxes.keys()) == ["Run"]


def test_populate_types_replaces_previous(qtbot, make_activity):
    w = _widget(qtbot)
    w.populate_types([make_activity(type="Run")])
    w.populate_types([make_activity(type="Ride")])
    assert set(w._type_checkboxes.keys()) == {"Ride"}


def test_populate_types_empty_list_clears_checkboxes(qtbot, make_activity):
    w = _widget(qtbot)
    w.populate_types([make_activity(type="Run")])
    w.populate_types([])
    assert w._type_checkboxes == {}
