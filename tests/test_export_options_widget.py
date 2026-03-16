"""pytest-qt tests for ExportOptionsWidget."""

import pytest
from src.gpx.processor import ExportOptions
from src.gui.export_options_widget import ExportOptionsWidget


def _widget(qtbot):
    w = ExportOptionsWidget()
    qtbot.addWidget(w)
    return w


def _collect_signals(widget):
    received = []
    widget.options_changed.connect(received.append)
    return received


# ---------------------------------------------------------------------------
# Initial state
# ---------------------------------------------------------------------------

def test_initial_concatenate_is_false(qtbot):
    assert _widget(qtbot).current_options().concatenate is False


def test_initial_include_time_is_true(qtbot):
    assert _widget(qtbot).current_options().include_time is True


def test_initial_include_elevation_is_true(qtbot):
    assert _widget(qtbot).current_options().include_elevation is True


def test_initial_returns_export_options_instance(qtbot):
    assert isinstance(_widget(qtbot).current_options(), ExportOptions)


# ---------------------------------------------------------------------------
# current_options() reflects checkbox state
# ---------------------------------------------------------------------------

def test_toggle_concatenate_updates_options(qtbot):
    w = _widget(qtbot)
    w._concatenate.setChecked(True)
    assert w.current_options().concatenate is True


def test_untoggle_concatenate_updates_options(qtbot):
    w = _widget(qtbot)
    w._concatenate.setChecked(True)
    w._concatenate.setChecked(False)
    assert w.current_options().concatenate is False


def test_toggle_include_time_updates_options(qtbot):
    w = _widget(qtbot)
    w._include_time.setChecked(False)
    assert w.current_options().include_time is False


def test_toggle_include_elevation_updates_options(qtbot):
    w = _widget(qtbot)
    w._include_elevation.setChecked(False)
    assert w.current_options().include_elevation is False


def test_all_off_produces_gps_only_options(qtbot):
    w = _widget(qtbot)
    w._include_time.setChecked(False)
    w._include_elevation.setChecked(False)
    opts = w.current_options()
    assert opts.include_time is False
    assert opts.include_elevation is False
    assert opts.concatenate is False


# ---------------------------------------------------------------------------
# options_changed signal
# ---------------------------------------------------------------------------

def test_signal_emitted_on_concatenate_toggle(qtbot):
    w = _widget(qtbot)
    received = _collect_signals(w)
    w._concatenate.setChecked(True)
    assert len(received) == 1


def test_signal_emitted_on_time_toggle(qtbot):
    w = _widget(qtbot)
    received = _collect_signals(w)
    w._include_time.setChecked(False)
    assert len(received) == 1


def test_signal_emitted_on_elevation_toggle(qtbot):
    w = _widget(qtbot)
    received = _collect_signals(w)
    w._include_elevation.setChecked(False)
    assert len(received) == 1


def test_signal_carries_export_options_instance(qtbot):
    w = _widget(qtbot)
    received = _collect_signals(w)
    w._concatenate.setChecked(True)
    assert isinstance(received[0], ExportOptions)


def test_signal_value_matches_current_options(qtbot):
    w = _widget(qtbot)
    received = _collect_signals(w)
    w._concatenate.setChecked(True)
    w._include_time.setChecked(False)
    assert received[-1].concatenate is True
    assert received[-1].include_time is False


def test_multiple_toggles_emit_multiple_signals(qtbot):
    w = _widget(qtbot)
    received = _collect_signals(w)
    w._concatenate.setChecked(True)
    w._include_time.setChecked(False)
    w._include_elevation.setChecked(False)
    assert len(received) == 3
