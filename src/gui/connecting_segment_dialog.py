"""Dialog for creating or editing a ConnectingSegment between two activities."""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox,
    QFormLayout, QGroupBox, QHBoxLayout, QLabel, QPushButton,
    QVBoxLayout, QWidget, QLineEdit,
)

from src.models.activity import Activity
from src.models.great_circle import haversine_km
from src.models.project import ConnectingSegment, SegmentEndpoint


_SEGMENT_TYPES = ["train", "flight", "boat", "bus"]
_SEGMENT_LABELS = {
    "train":  "Train 🚂",
    "flight": "Flight ✈",
    "boat":   "Boat ⛴",
    "bus":    "Bus 🚌",
}


class ConnectingSegmentDialog(QDialog):
    """Modal dialog to define a great-circle connecting segment.

    Parameters
    ----------
    prev_activity:
        Activity ending just before this segment (used for auto-fill of start).
    next_activity:
        Activity starting just after this segment (used for auto-fill of end).
    segment:
        Existing segment to edit; None to create a new one.
    """

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        prev_activity: Optional[Activity] = None,
        next_activity: Optional[Activity] = None,
        segment: Optional[ConnectingSegment] = None,
    ) -> None:
        super().__init__(parent)
        self._prev = prev_activity
        self._next = next_activity
        self._editing = segment

        self.setWindowTitle("Connecting segment" if segment is None else "Edit segment")
        self.setMinimumWidth(420)
        self._build_ui()
        self._populate(segment)
        self._update_distance()

    # ------------------------------------------------------------------
    # Result
    # ------------------------------------------------------------------

    def result_segment(self) -> ConnectingSegment:
        """Return the constructed / edited segment.  Only valid after accept()."""
        seg_type = _SEGMENT_TYPES[self._type_combo.currentIndex()]
        start = SegmentEndpoint(
            lat=self._start_lat.value(),
            lon=self._start_lon.value(),
            source=self._start_source,
        )
        end = SegmentEndpoint(
            lat=self._end_lat.value(),
            lon=self._end_lon.value(),
            source=self._end_source,
        )
        existing_id = self._editing.id if self._editing else None
        return ConnectingSegment(
            id=existing_id or ConnectingSegment.__dataclass_fields__["id"].default_factory(),
            segment_type=seg_type,
            label=self._label_edit.text().strip(),
            start=start,
            end=end,
        )

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        # Type
        self._type_combo = QComboBox()
        for t in _SEGMENT_TYPES:
            self._type_combo.addItem(_SEGMENT_LABELS[t], t)
        form.addRow("Type:", self._type_combo)

        # Start group
        start_box = QGroupBox("Start")
        sl = QHBoxLayout(start_box)
        self._start_lat = self._make_lat_spin()
        self._start_lon = self._make_lon_spin()
        sl.addWidget(QLabel("Lat"))
        sl.addWidget(self._start_lat)
        sl.addWidget(QLabel("Lon"))
        sl.addWidget(self._start_lon)
        if self._prev is not None:
            btn = QPushButton("← Use end of previous activity")
            btn.clicked.connect(self._fill_start_from_prev)
            sl.addWidget(btn)
        form.addRow(start_box)

        # End group
        end_box = QGroupBox("End")
        el = QHBoxLayout(end_box)
        self._end_lat = self._make_lat_spin()
        self._end_lon = self._make_lon_spin()
        el.addWidget(QLabel("Lat"))
        el.addWidget(self._end_lat)
        el.addWidget(QLabel("Lon"))
        el.addWidget(self._end_lon)
        if self._next is not None:
            btn = QPushButton("Use start of next activity →")
            btn.clicked.connect(self._fill_end_from_next)
            el.addWidget(btn)
        form.addRow(end_box)

        # Label
        self._label_edit = QLineEdit()
        self._label_edit.setPlaceholderText("e.g. Basel → Paris (TGV)")
        form.addRow("Label:", self._label_edit)

        # Distance (read-only)
        self._dist_label = QLabel("— km")
        form.addRow("Distance:", self._dist_label)

        layout.addLayout(form)

        # Connect spinboxes to distance updater
        for spin in (self._start_lat, self._start_lon, self._end_lat, self._end_lon):
            spin.valueChanged.connect(self._update_distance)

        # Buttons
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.button(QDialogButtonBox.StandardButton.Ok).setText("Insert")
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _populate(self, segment: Optional[ConnectingSegment]) -> None:
        self._start_source = "auto"
        self._end_source = "auto"

        if segment is not None:
            idx = _SEGMENT_TYPES.index(segment.segment_type) if segment.segment_type in _SEGMENT_TYPES else 0
            self._type_combo.setCurrentIndex(idx)
            self._start_lat.setValue(segment.start.lat)
            self._start_lon.setValue(segment.start.lon)
            self._end_lat.setValue(segment.end.lat)
            self._end_lon.setValue(segment.end.lon)
            self._label_edit.setText(segment.label)
            self._start_source = segment.start.source
            self._end_source = segment.end.source
        else:
            # Auto-fill from adjacent activities if available
            if self._prev is not None:
                self._fill_start_from_prev()
            if self._next is not None:
                self._fill_end_from_next()

    def _fill_start_from_prev(self) -> None:
        if self._prev is None:
            return
        coords = self._prev.end_latlng or self._prev.start_latlng
        if coords:
            self._start_lat.setValue(coords[0])
            self._start_lon.setValue(coords[1])
            self._start_source = "auto"

    def _fill_end_from_next(self) -> None:
        if self._next is None:
            return
        coords = self._next.start_latlng
        if coords:
            self._end_lat.setValue(coords[0])
            self._end_lon.setValue(coords[1])
            self._end_source = "auto"

    def _update_distance(self) -> None:
        try:
            d = haversine_km(
                self._start_lat.value(), self._start_lon.value(),
                self._end_lat.value(), self._end_lon.value(),
            )
            self._dist_label.setText(f"≈ {d:.0f} km (great circle)")
        except Exception:
            self._dist_label.setText("—")

    @staticmethod
    def _make_lat_spin() -> QDoubleSpinBox:
        s = QDoubleSpinBox()
        s.setRange(-90.0, 90.0)
        s.setDecimals(6)
        s.setSingleStep(0.01)
        return s

    @staticmethod
    def _make_lon_spin() -> QDoubleSpinBox:
        s = QDoubleSpinBox()
        s.setRange(-180.0, 180.0)
        s.setDecimals(6)
        s.setSingleStep(0.01)
        return s
