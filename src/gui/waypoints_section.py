"""Collapsible section widget displaying Polarsteps waypoints below the project list."""

from __future__ import annotations

from typing import List, Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QKeySequence
from PyQt6.QtWidgets import (
    QAbstractItemView, QFrame, QLabel, QListWidget, QListWidgetItem,
    QMenu, QPushButton, QVBoxLayout, QWidget,
)

from src.models.waypoint import TripStep


class WaypointsSectionWidget(QWidget):
    """Collapsible section showing all project waypoints.

    Signals
    -------
    waypoint_selected
        Emitted when the user clicks a row. Carries the TripStep.
    """

    waypoint_selected = pyqtSignal(object)   # TripStep
    waypoints_removed = pyqtSignal(list)     # List[TripStep]

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._steps: List[TripStep] = []
        self._expanded: bool = True
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 4, 0, 0)
        root.setSpacing(0)

        # Collapse toggle button
        self._toggle_btn = QPushButton("▼  Waypoints (0)")
        self._toggle_btn.setFlat(True)
        font = QFont()
        font.setBold(True)
        self._toggle_btn.setFont(font)
        self._toggle_btn.setStyleSheet(
            "QPushButton { text-align: left; padding: 4px 4px; }"
            "QPushButton:hover { background: #e8e8e8; }"
        )
        self._toggle_btn.clicked.connect(self._toggle)
        root.addWidget(self._toggle_btn)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        root.addWidget(sep)

        # List
        self._list = QListWidget()
        self._list.setAlternatingRowColors(True)
        self._list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._list.itemClicked.connect(self._on_item_clicked)
        self._list.customContextMenuRequested.connect(self._on_context_menu)
        self._list.installEventFilter(self)
        root.addWidget(self._list)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_waypoints(self, steps: List[TripStep]) -> None:
        """Rebuild the list from *steps*."""
        self._steps = steps
        self._list.clear()
        for step in steps:
            date_str = step.date.strftime("%Y-%m-%d")
            photos_str = f"  [{len(step.photos)} 📷]" if step.photos else ""
            wi = QListWidgetItem(f"📍 {step.name}  ·  {date_str}{photos_str}")
            wi.setData(Qt.ItemDataRole.UserRole, step)
            self._list.addItem(wi)
        self._toggle_btn.setText(
            f"{'▼' if self._expanded else '▶'}  Waypoints ({len(steps)})"
        )

    def highlight(self, step: TripStep) -> None:
        """Select the row for *step* without emitting a signal."""
        for i in range(self._list.count()):
            item = self._list.item(i)
            if item.data(Qt.ItemDataRole.UserRole) is step:
                self._list.setCurrentItem(item)
                return

    # ------------------------------------------------------------------
    # Handlers
    # ------------------------------------------------------------------

    def _toggle(self) -> None:
        self._expanded = not self._expanded
        self._list.setVisible(self._expanded)
        label = f"{'▼' if self._expanded else '▶'}  Waypoints ({len(self._steps)})"
        self._toggle_btn.setText(label)

    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        # Only navigate to a waypoint on a plain single-click; Shift/Ctrl multi-select
        # must not collapse the selection by triggering highlight().
        if len(self._list.selectedItems()) != 1:
            return
        step = item.data(Qt.ItemDataRole.UserRole)
        if step is not None:
            self.waypoint_selected.emit(step)

    def _on_context_menu(self, pos) -> None:
        if not self._list.selectedItems():
            return
        menu = QMenu(self)
        n = len(self._list.selectedItems())
        label = f"Remove {n} waypoint{'s' if n > 1 else ''}"
        act = menu.addAction(label)
        if menu.exec(self._list.mapToGlobal(pos)) == act:
            self._remove_selected()

    def _remove_selected(self) -> None:
        to_remove = [
            wi.data(Qt.ItemDataRole.UserRole)
            for wi in self._list.selectedItems()
            if wi.data(Qt.ItemDataRole.UserRole) is not None
        ]
        if to_remove:
            self.waypoints_removed.emit(to_remove)

    def eventFilter(self, obj, event) -> bool:
        from PyQt6.QtCore import QEvent
        if obj is self._list and event.type() == QEvent.Type.KeyPress:
            if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
                self._remove_selected()
                return True
            if (event.key() == Qt.Key.Key_A and
                    event.modifiers() & Qt.KeyboardModifier.ControlModifier):
                self._list.selectAll()
                return True
        return super().eventFilter(obj, event)
