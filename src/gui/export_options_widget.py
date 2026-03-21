"""Widget for configuring GPX export options."""

from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QCheckBox, QLabel, QFrame, QComboBox,
)
from PyQt6.QtCore import pyqtSignal

from src.gpx.processor import ExportOptions


class ExportOptionsWidget(QWidget):
    """Compact row of checkboxes that control how a GPX is written.

    Emits ``options_changed`` whenever the user toggles a control, passing the
    current :class:`ExportOptions` value.
    """

    options_changed = pyqtSignal(object)  # ExportOptions

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        label = QLabel("Export options:")
        layout.addWidget(label)

        self._concatenate = QCheckBox("Merge into single track")
        self._concatenate.setToolTip(
            "When checked, all selected activities are merged into one continuous GPX track.\n"
            "When unchecked, each activity is written as a separate track."
        )
        layout.addWidget(self._concatenate)

        sep1 = QFrame()
        sep1.setFrameShape(QFrame.Shape.VLine)
        sep1.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(sep1)

        self._include_time = QCheckBox("Timestamps")
        self._include_time.setChecked(True)
        self._include_time.setToolTip(
            "Include per-point elapsed time in the exported GPX.\n"
            "Uncheck for a GPS-only export (lat/lon/elevation)."
        )
        layout.addWidget(self._include_time)

        self._include_elevation = QCheckBox("Elevation")
        self._include_elevation.setChecked(True)
        self._include_elevation.setToolTip(
            "Include per-point elevation in the exported GPX.\n"
            "Uncheck to export lat/lon only."
        )
        layout.addWidget(self._include_elevation)

        # --- Waypoints section (hidden until project has waypoints) ---
        self._sep_wpt = QFrame()
        self._sep_wpt.setFrameShape(QFrame.Shape.VLine)
        self._sep_wpt.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(self._sep_wpt)

        self._include_waypoints = QCheckBox("Polarsteps waypoints")
        self._include_waypoints.setChecked(True)
        self._include_waypoints.setToolTip(
            "Include Polarsteps trip steps as <wpt> elements in the exported GPX."
        )
        layout.addWidget(self._include_waypoints)

        self._photo_mode_combo = QComboBox()
        self._photo_mode_combo.addItem("CDN photo links", "cdn")
        self._photo_mode_combo.addItem("Download photos (zip)", "local")
        self._photo_mode_combo.setToolTip(
            "CDN links: embed public Polarsteps thumbnail URLs in the GPX (fast, online only).\n"
            "Download photos: fetch thumbnails and bundle them with the GPX in a .zip archive."
        )
        layout.addWidget(self._photo_mode_combo)

        # Hidden by default — shown by set_has_waypoints(True)
        self._sep_wpt.setVisible(False)
        self._include_waypoints.setVisible(False)
        self._photo_mode_combo.setVisible(False)

        layout.addStretch()

        self._concatenate.toggled.connect(self._emit_options)
        self._include_time.toggled.connect(self._emit_options)
        self._include_elevation.toggled.connect(self._emit_options)
        self._include_waypoints.toggled.connect(self._on_waypoints_toggled)
        self._photo_mode_combo.currentIndexChanged.connect(self._emit_options)

    def set_has_waypoints(self, has: bool) -> None:
        """Show or hide the waypoints section based on project state."""
        self._sep_wpt.setVisible(has)
        self._include_waypoints.setVisible(has)
        self._photo_mode_combo.setVisible(has and self._include_waypoints.isChecked())

    def _on_waypoints_toggled(self, checked: bool) -> None:
        self._photo_mode_combo.setVisible(
            checked and self._include_waypoints.isVisible()
        )
        self._emit_options()

    def _emit_options(self):
        self.options_changed.emit(self.current_options())

    def current_options(self) -> ExportOptions:
        return ExportOptions(
            concatenate=self._concatenate.isChecked(),
            include_time=self._include_time.isChecked(),
            include_elevation=self._include_elevation.isChecked(),
            include_waypoints=(
                self._include_waypoints.isVisible()
                and self._include_waypoints.isChecked()
            ),
            waypoint_photos=self._photo_mode_combo.currentData() or "cdn",
        )
