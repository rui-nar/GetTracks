"""Filter panel widget for GetTracks."""

from datetime import date
from typing import Dict, List, Optional, Set

from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QGroupBox,
    QDateEdit, QCheckBox, QPushButton, QLabel,
)
from PyQt6.QtCore import pyqtSignal, QDate

from src.filters.filter_engine import FilterCriteria, FilterEngine
from src.models.activity import Activity

_DEFAULT_START = QDate(2010, 1, 1)


class FilterWidget(QWidget):
    """Filter panel for filtering activities by date range and type."""

    filters_changed = pyqtSignal(object)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._type_checkboxes: Dict[str, QCheckBox] = {}
        self._setup_ui()

    def _setup_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        group = QGroupBox("Filters")
        layout = QVBoxLayout(group)
        layout.setSpacing(6)

        # --- Row 1: Date range (always active, no enabling checkbox) ---
        date_row = QHBoxLayout()
        date_row.addWidget(QLabel("From:"))

        self._start_date = QDateEdit()
        self._start_date.setDisplayFormat("yyyy-MM-dd")
        self._start_date.setDate(_DEFAULT_START)
        self._start_date.setToolTip("Click year/month/day and type, or use ↑↓ arrow keys")
        date_row.addWidget(self._start_date)

        date_row.addWidget(QLabel("To:"))

        self._end_date = QDateEdit()
        self._end_date.setDisplayFormat("yyyy-MM-dd")
        self._end_date.setDate(QDate.currentDate())
        self._end_date.setToolTip("Click year/month/day and type, or use ↑↓ arrow keys")
        date_row.addWidget(self._end_date)

        date_row.addStretch()
        layout.addLayout(date_row)

        # --- Row 2: Activity types ---
        self._types_row = QHBoxLayout()
        self._types_row.setSpacing(8)
        self._types_row.addWidget(QLabel("Types:"))
        self._types_row.addStretch()
        layout.addLayout(self._types_row)

        # --- Row 3: Buttons ---
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self._apply_btn = QPushButton("Apply Filters")
        self._apply_btn.clicked.connect(self._on_apply)
        btn_row.addWidget(self._apply_btn)

        self._clear_btn = QPushButton("Clear")
        self._clear_btn.setFixedWidth(55)
        self._clear_btn.clicked.connect(self._on_clear)
        btn_row.addWidget(self._clear_btn)

        layout.addLayout(btn_row)
        outer.addWidget(group)

    def populate_types(self, activities: List[Activity]) -> None:
        """Rebuild type checkboxes from the given activity list."""
        for cb in self._type_checkboxes.values():
            self._types_row.removeWidget(cb)
            cb.deleteLater()
        self._type_checkboxes.clear()

        stretch_index = self._types_row.count() - 1
        for i, activity_type in enumerate(FilterEngine.extract_activity_types(activities)):
            cb = QCheckBox(activity_type)
            cb.setChecked(True)
            self._types_row.insertWidget(stretch_index + i, cb)
            self._type_checkboxes[activity_type] = cb

    def build_criteria(self) -> FilterCriteria:
        """Read current widget state and return a FilterCriteria."""
        start_date: date = self._start_date.date().toPyDate()
        end_date: date = self._end_date.date().toPyDate()

        selected_types: Optional[Set[str]] = None
        if self._type_checkboxes:
            checked = {t for t, cb in self._type_checkboxes.items() if cb.isChecked()}
            if len(checked) < len(self._type_checkboxes):
                selected_types = checked

        return FilterCriteria(
            start_date=start_date,
            end_date=end_date,
            activity_types=selected_types,
        )

    def _on_apply(self) -> None:
        self.filters_changed.emit(self.build_criteria())

    def _on_clear(self) -> None:
        self._start_date.setDate(_DEFAULT_START)
        self._end_date.setDate(QDate.currentDate())
        for cb in self._type_checkboxes.values():
            cb.setChecked(True)
        self.filters_changed.emit(FilterCriteria())
