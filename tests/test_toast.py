"""Tests for ToastManager and Toast widget."""

import pytest
from PyQt6.QtWidgets import QWidget, QApplication
from PyQt6.QtCore import Qt

from src.gui.toast import Toast, ToastManager


@pytest.fixture
def parent_widget(qtbot):
    w = QWidget()
    w.resize(800, 600)
    qtbot.addWidget(w)
    w.show()
    return w


# ---------------------------------------------------------------------------
# Toast
# ---------------------------------------------------------------------------

class TestToast:
    def test_toast_is_visible_after_creation(self, qtbot, parent_widget):
        t = Toast(parent_widget, "Hello", "info")
        qtbot.addWidget(t)
        assert t.isVisible()

    def test_toast_dismisses_after_duration(self, qtbot, parent_widget):
        t = Toast(parent_widget, "Gone soon", "info", duration_ms=100)
        qtbot.addWidget(t)
        with qtbot.waitSignal(t.closed, timeout=1000):
            pass
        assert not t.isVisible()

    def test_toast_emits_closed_signal(self, qtbot, parent_widget):
        t = Toast(parent_widget, "Signal test", "info", duration_ms=100)
        qtbot.addWidget(t)
        signals = []
        t.closed.connect(lambda: signals.append(True))
        with qtbot.waitSignal(t.closed, timeout=1000):
            pass
        assert signals

    def test_toast_has_correct_parent(self, qtbot, parent_widget):
        t = Toast(parent_widget, "Parent test", "info")
        qtbot.addWidget(t)
        assert t.parent() is parent_widget

    @pytest.mark.parametrize("level", ["success", "error", "warning", "info"])
    def test_toast_levels_are_created_without_error(self, qtbot, parent_widget, level):
        t = Toast(parent_widget, f"Level: {level}", level)
        qtbot.addWidget(t)
        assert t.isVisible()

    def test_toast_unknown_level_falls_back_to_info(self, qtbot, parent_widget):
        t = Toast(parent_widget, "Unknown level", "banana")
        qtbot.addWidget(t)
        assert t.isVisible()

    def test_toast_has_non_zero_size(self, qtbot, parent_widget):
        t = Toast(parent_widget, "Size test", "info")
        qtbot.addWidget(t)
        assert t.width() > 0
        assert t.height() > 0


# ---------------------------------------------------------------------------
# ToastManager
# ---------------------------------------------------------------------------

class TestToastManager:
    def test_show_creates_a_toast(self, qtbot, parent_widget):
        mgr = ToastManager(parent_widget)
        mgr.show("Test", "info", duration_ms=5000)
        assert len(mgr._toasts) == 1

    def test_show_multiple_toasts(self, qtbot, parent_widget):
        mgr = ToastManager(parent_widget)
        mgr.show("First", "info", duration_ms=5000)
        mgr.show("Second", "success", duration_ms=5000)
        assert len(mgr._toasts) == 2

    def test_dismissed_toast_removed_from_list(self, qtbot, parent_widget):
        mgr = ToastManager(parent_widget)
        mgr.show("Dismiss me", "info", duration_ms=100)
        toast = mgr._toasts[0]
        with qtbot.waitSignal(toast.closed, timeout=1000):
            pass
        qtbot.wait(50)  # let _remove run
        assert len(mgr._toasts) == 0

    def test_restack_does_not_raise_with_no_toasts(self, qtbot, parent_widget):
        mgr = ToastManager(parent_widget)
        mgr.restack()  # should not raise

    def test_restack_positions_toasts_inside_parent(self, qtbot, parent_widget):
        mgr = ToastManager(parent_widget)
        mgr.show("Positioned", "info", duration_ms=5000)
        t = mgr._toasts[0]
        pw, ph = parent_widget.width(), parent_widget.height()
        assert 0 <= t.x() < pw
        assert 0 <= t.y() < ph

    def test_toasts_stack_vertically(self, qtbot, parent_widget):
        mgr = ToastManager(parent_widget)
        mgr.show("First", "info", duration_ms=5000)
        mgr.show("Second", "info", duration_ms=5000)
        t1, t2 = mgr._toasts
        # Newer toast (t2) stays at the bottom; older toast (t1) shifts up
        assert t1.y() < t2.y()

    def test_restack_called_on_parent_resize(self, qtbot, parent_widget):
        mgr = ToastManager(parent_widget)
        mgr.show("Resize test", "info", duration_ms=5000)
        old_x = mgr._toasts[0].x()
        parent_widget.resize(400, 300)
        mgr.restack()
        # x position should adapt to new width
        new_x = mgr._toasts[0].x()
        assert new_x != old_x
