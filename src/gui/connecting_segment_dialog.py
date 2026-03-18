"""Dialog for creating or editing a ConnectingSegment between two activities."""

from __future__ import annotations

from typing import List, Optional, Tuple

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QButtonGroup
from PyQt6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox,
    QFormLayout, QGroupBox, QHBoxLayout, QLabel, QPushButton,
    QVBoxLayout, QWidget, QLineEdit,
)

from src.models.activity import Activity
from src.models.great_circle import haversine_km
from src.models.project import ConnectingSegment, Project, ProjectItem, SegmentEndpoint


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


# ---------------------------------------------------------------------------
# Transport type icon buttons
# ---------------------------------------------------------------------------

_TRANSPORT_ICONS = [
    ("train",  "🚂", "Train"),
    ("flight", "✈",  "Flight"),
    ("boat",   "⛴",  "Boat"),
    ("bus",    "🚌",  "Bus"),
]

_BTN_STYLE_NORMAL  = (
    "QPushButton { font-size: 22px; padding: 8px 14px; border: 2px solid #cccccc;"
    " border-radius: 8px; background: #f5f5f5; }"
    "QPushButton:hover { background: #e0e8ff; border-color: #7baaf7; }"
)
_BTN_STYLE_CHECKED = (
    "QPushButton { font-size: 22px; padding: 8px 14px; border: 2px solid #1565C0;"
    " border-radius: 8px; background: #1565C0; color: white; }"
)


# ---------------------------------------------------------------------------
# AddTransportationDialog
# ---------------------------------------------------------------------------

class AddTransportationDialog(QDialog):
    """Dialog to add or edit a transportation segment in the project.

    Parameters
    ----------
    project:
        The current project (used to populate the position combo).
    segment:
        Existing segment to edit; if provided the dialog pre-fills all
        fields and the position combo is set to the segment's position.
        Pass ``segment_index`` as the 0-based index in ``project.items``.
    segment_index:
        Only meaningful when ``segment`` is not None — the position of the
        segment in ``project.items`` (used to pre-select the combo and to
        return the correct ``result_index``).

    After ``exec()`` returns ``Accepted`` use :meth:`result_segment` and
    :meth:`result_index` to retrieve the segment and the insertion index.
    """

    def __init__(
        self,
        project: Project,
        parent: Optional[QWidget] = None,
        segment: Optional[ConnectingSegment] = None,
        segment_index: int = 0,
    ) -> None:
        super().__init__(parent)
        self._project = project
        self._act_map = {a.id: a for a in project.activities}
        self._insert_index = 0
        self._existing_segment = segment

        self.setWindowTitle("Edit transportation" if segment else "Add transportation")
        self.setMinimumWidth(500)
        self._build_ui()
        if segment:
            self._prefill_segment(segment, segment_index)
        else:
            # Trigger initial auto-fill
            self._on_position_changed(0)

    # ------------------------------------------------------------------
    # Public results
    # ------------------------------------------------------------------

    def result_segment(self) -> ConnectingSegment:
        """Return the built segment.  Only valid after ``accept()``."""
        seg_type = _TRANSPORT_ICONS[self._selected_type_index()][0]
        start = SegmentEndpoint(
            lat=self._start_lat.value(),
            lon=self._start_lon.value(),
            source="auto",
        )
        end = SegmentEndpoint(
            lat=self._end_lat.value(),
            lon=self._end_lon.value(),
            source="auto",
        )
        existing_id = self._existing_segment.id if self._existing_segment else None
        return ConnectingSegment(
            id=existing_id or ConnectingSegment.__dataclass_fields__["id"].default_factory(),
            segment_type=seg_type,
            label=self._label_edit.text().strip(),
            start=start,
            end=end,
        )

    def result_index(self) -> int:
        """Return the index at which the segment should be inserted/replaced in project.items."""
        return self._insert_index

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # ── Transport type buttons ────────────────────────────────────
        type_label = QLabel("Transport type:")
        type_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(type_label)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        self._type_buttons: List[QPushButton] = []
        self._type_group = QButtonGroup(self)
        self._type_group.setExclusive(True)

        for i, (_, icon, label) in enumerate(_TRANSPORT_ICONS):
            btn = QPushButton(f"{icon}\n{label}")
            btn.setCheckable(True)
            btn.setStyleSheet(_BTN_STYLE_NORMAL)
            btn.setMinimumWidth(90)
            btn.toggled.connect(lambda checked, b=btn: self._on_type_toggled(b, checked))
            self._type_group.addButton(btn, i)
            self._type_buttons.append(btn)
            btn_row.addWidget(btn)

        btn_row.addStretch()
        layout.addLayout(btn_row)
        # Select first by default
        self._type_buttons[0].setChecked(True)

        # ── Position ──────────────────────────────────────────────────
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._position_combo = QComboBox()
        self._populate_position_combo()
        self._position_combo.currentIndexChanged.connect(self._on_position_changed)
        form.addRow("Insert after:", self._position_combo)

        # Label
        self._label_edit = QLineEdit()
        self._label_edit.setPlaceholderText("e.g. Basel → Paris (TGV)")
        form.addRow("Label:", self._label_edit)

        layout.addLayout(form)

        # ── Start / End coordinates ───────────────────────────────────
        coord_layout = QFormLayout()
        coord_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        start_row = QHBoxLayout()
        self._start_lat = self._make_lat_spin()
        self._start_lon = self._make_lon_spin()
        start_row.addWidget(QLabel("Lat"))
        start_row.addWidget(self._start_lat)
        start_row.addWidget(QLabel("Lon"))
        start_row.addWidget(self._start_lon)
        coord_layout.addRow("Start:", start_row)

        end_row = QHBoxLayout()
        self._end_lat = self._make_lat_spin()
        self._end_lon = self._make_lon_spin()
        end_row.addWidget(QLabel("Lat"))
        end_row.addWidget(self._end_lat)
        end_row.addWidget(QLabel("Lon"))
        end_row.addWidget(self._end_lon)
        coord_layout.addRow("End:", end_row)

        self._dist_label = QLabel("— km")
        coord_layout.addRow("Distance:", self._dist_label)

        layout.addLayout(coord_layout)

        for spin in (self._start_lat, self._start_lon, self._end_lat, self._end_lon):
            spin.valueChanged.connect(self._update_distance)

        # ── Buttons ───────────────────────────────────────────────────
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        ok_label = "Save" if self._existing_segment else "Insert"
        btns.button(QDialogButtonBox.StandardButton.Ok).setText(ok_label)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _prefill_segment(self, segment: ConnectingSegment, segment_index: int) -> None:
        """Pre-fill all fields from an existing segment (edit mode)."""
        # Select the correct type button
        type_key = segment.segment_type
        for i, (key, _, _) in enumerate(_TRANSPORT_ICONS):
            if key == type_key:
                self._type_buttons[i].setChecked(True)
                break

        # Set position combo to the item *after* the segment's position
        # (segment is at segment_index; "after item before it" = segment_index)
        target_data = segment_index  # insertion point that equals the segment's own index
        for i in range(self._position_combo.count()):
            if self._position_combo.itemData(i) == target_data:
                self._position_combo.blockSignals(True)
                self._position_combo.setCurrentIndex(i)
                self._position_combo.blockSignals(False)
                self._insert_index = target_data
                break

        # Fill coordinates
        self._start_lat.setValue(segment.start.lat)
        self._start_lon.setValue(segment.start.lon)
        self._end_lat.setValue(segment.end.lat)
        self._end_lon.setValue(segment.end.lon)

        # Label
        self._label_edit.setText(segment.label)

        self._update_distance()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _populate_position_combo(self) -> None:
        self._position_combo.clear()
        self._position_combo.addItem("At beginning", 0)
        for i, item in enumerate(self._project.items):
            label = self._item_label(item)
            self._position_combo.addItem(f"After: {label}", i + 1)

    def _item_label(self, item: ProjectItem) -> str:
        if item.item_type == "activity":
            act = self._act_map.get(item.activity_id)
            if act:
                date_str = act.start_date.strftime("%Y-%m-%d") if act.start_date else "?"
                return f"{act.name} ({date_str})"
        if item.item_type == "segment" and item.segment:
            return item.segment.label or f"{item.segment.segment_type.capitalize()} segment"
        return "item"

    def _on_position_changed(self, combo_index: int) -> None:
        self._insert_index = self._position_combo.itemData(combo_index) or 0
        prev_act, next_act = self._adjacent_activities(self._insert_index)

        if prev_act:
            coords = prev_act.end_latlng or prev_act.start_latlng
            if coords:
                self._start_lat.setValue(coords[0])
                self._start_lon.setValue(coords[1])

        if next_act:
            coords = next_act.start_latlng
            if coords:
                self._end_lat.setValue(coords[0])
                self._end_lon.setValue(coords[1])

        self._update_distance()

    def _adjacent_activities(
        self, insert_index: int
    ) -> Tuple[Optional[Activity], Optional[Activity]]:
        """Return the activity immediately before and after *insert_index*."""
        prev_act: Optional[Activity] = None
        next_act: Optional[Activity] = None
        items = self._project.items
        for i in range(insert_index - 1, -1, -1):
            it = items[i]
            if it.item_type == "activity":
                prev_act = self._act_map.get(it.activity_id)
                if prev_act:
                    break
        for i in range(insert_index, len(items)):
            it = items[i]
            if it.item_type == "activity":
                next_act = self._act_map.get(it.activity_id)
                if next_act:
                    break
        return prev_act, next_act

    def _selected_type_index(self) -> int:
        return self._type_group.checkedId()

    def _on_type_toggled(self, btn: QPushButton, checked: bool) -> None:
        btn.setStyleSheet(_BTN_STYLE_CHECKED if checked else _BTN_STYLE_NORMAL)

    def _update_distance(self) -> None:
        try:
            d = haversine_km(
                self._start_lat.value(), self._start_lon.value(),
                self._end_lat.value(),   self._end_lon.value(),
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
