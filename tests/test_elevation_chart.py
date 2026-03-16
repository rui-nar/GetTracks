"""Tests for ElevationChart widget."""

import pytest
from PyQt6.QtWidgets import QWidget

from src.gui.elevation_chart import ElevationChart


@pytest.fixture
def chart(qtbot):
    w = ElevationChart()
    w.resize(400, 160)
    qtbot.addWidget(w)
    w.show()
    return w


class TestElevationChartState:
    def test_initial_state_is_empty(self, chart):
        assert chart._distances == []
        assert chart._elevations == []
        assert not chart._loading

    def test_set_data_stores_values(self, chart):
        chart.set_data([0.0, 1.0, 2.0], [100.0, 120.0, 110.0])
        assert chart._distances == [0.0, 1.0, 2.0]
        assert chart._elevations == [100.0, 120.0, 110.0]

    def test_set_data_clears_loading(self, chart):
        chart.set_loading(True)
        chart.set_data([0.0, 1.0], [100.0, 110.0])
        assert not chart._loading

    def test_set_loading_true_clears_data(self, chart):
        chart.set_data([0.0, 1.0], [100.0, 110.0])
        chart.set_loading(True)
        assert chart._distances == []
        assert chart._elevations == []

    def test_set_loading_stores_flag(self, chart):
        chart.set_loading(True)
        assert chart._loading

    def test_clear_resets_everything(self, chart):
        chart.set_data([0.0, 1.0], [100.0, 110.0], "Test Run")
        chart.clear()
        assert chart._distances == []
        assert chart._elevations == []
        assert chart._activity_name == ""
        assert not chart._loading

    def test_activity_name_stored(self, chart):
        chart.set_data([0.0, 1.0], [100.0, 110.0], "My Run")
        assert chart._activity_name == "My Run"


class TestElevationChartPainting:
    """Smoke tests — just ensure paintEvent doesn't raise."""

    def test_paints_without_data(self, chart, qtbot):
        chart.update()
        qtbot.wait(20)

    def test_paints_with_data(self, chart, qtbot):
        chart.set_data(list(range(10)), [100 + i * 5 for i in range(10)])
        chart.update()
        qtbot.wait(20)

    def test_paints_while_loading(self, chart, qtbot):
        chart.set_loading(True)
        chart.update()
        qtbot.wait(20)

    def test_paints_with_flat_elevation(self, chart, qtbot):
        chart.set_data([0.0, 1.0, 2.0], [200.0, 200.0, 200.0])
        chart.update()
        qtbot.wait(20)

    def test_paints_with_single_point(self, chart, qtbot):
        # Edge case: single point — range = 0
        chart.set_data([0.0], [100.0])
        chart.update()
        qtbot.wait(20)
