"""Collapsible section widget displaying Polarsteps waypoints below the project list."""

from __future__ import annotations

from typing import List, Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QFrame, QLabel, QListWidget, QListWidgetItem,
    QPushButton, QVBoxLayout, QWidget,
)

from src.models.waypoint import TripStep


class WaypointsSectionWidget(QWidget):
    """Collapsible section showing all project waypoints.

    Signals
    -------
    waypoint_selected
        Emitted when the user clicks a row. Carries the TripStep.
    """

    waypoint_selected = pyqtSignal(object)  # TripStep

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
        self._list.itemClicked.connect(self._on_item_clicked)
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
        step = item.data(Qt.ItemDataRole.UserRole)
        if step is not None:
            self.waypoint_selected.emit(step)
