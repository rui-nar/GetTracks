"""Floating toast notification overlay for transient status messages."""

from PyQt6.QtWidgets import QFrame, QLabel, QHBoxLayout
from PyQt6.QtCore import Qt, QTimer, pyqtSignal


class Toast(QFrame):
    """A single auto-dismissing notification frame rendered inside the parent widget."""

    closed = pyqtSignal()

    _STYLES: dict = {
        "success": "background:#e8f5e9; border:1px solid #2e7d32; color:#1b5e20;",
        "error":   "background:#ffebee; border:1px solid #c62828; color:#b71c1c;",
        "warning": "background:#fff3e0; border:1px solid #e65100; color:#bf360c;",
        "info":    "background:#e3f2fd; border:1px solid #1565c0; color:#0d47a1;",
    }

    def __init__(self, parent, message: str, level: str = "info", duration_ms: int = 4000):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.SubWindow)

        style = self._STYLES.get(level, self._STYLES["info"])
        self.setStyleSheet(
            f"QFrame {{ {style} border-radius:6px; }}"
            "QLabel { background:transparent; border:none; font-size:13px; }"
        )

        label = QLabel(message)
        label.setWordWrap(True)
        label.setMaximumWidth(380)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.addWidget(label)

        self.adjustSize()
        self.raise_()
        self.show()

        QTimer.singleShot(duration_ms, self._dismiss)

    def _dismiss(self) -> None:
        self.closed.emit()
        self.hide()
        self.deleteLater()


class ToastManager:
    """Stacks Toast widgets in the bottom-right corner of a parent QWidget."""

    MARGIN = 14
    SPACING = 8

    def __init__(self, parent) -> None:
        self._parent = parent
        self._toasts: list[Toast] = []

    def show(self, message: str, level: str = "info", duration_ms: int = 4000) -> None:
        """Display a new toast notification."""
        t = Toast(self._parent, message, level, duration_ms)
        t.closed.connect(lambda: self._remove(t))
        self._toasts.append(t)
        self._restack()

    def _remove(self, toast: Toast) -> None:
        self._toasts = [t for t in self._toasts if t is not toast]
        self._restack()

    def restack(self) -> None:
        """Re-position all visible toasts (call from parent resizeEvent)."""
        self._restack()

    def _restack(self) -> None:
        pw = self._parent.width()
        ph = self._parent.height()
        y = ph - self.MARGIN
        for t in reversed(self._toasts):
            if not t.isVisible():
                continue
            y -= t.height()
            t.move(pw - t.width() - self.MARGIN, y)
            y -= self.SPACING
