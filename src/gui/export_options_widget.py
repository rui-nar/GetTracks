"""Widget for configuring GPX export options."""

from PyQt6.QtWidgets import QWidget, QHBoxLayout, QCheckBox, QLabel, QFrame
from PyQt6.QtCore import pyqtSignal

from src.gpx.processor import ExportOptions


class ExportOptionsWidget(QWidget):
    """Compact row of checkboxes that control how a GPX is written.

    Emits ``options_changed`` whenever the user toggles a checkbox, passing the
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

        layout.addStretch()

        self._concatenate.toggled.connect(self._emit_options)
        self._include_time.toggled.connect(self._emit_options)
        self._include_elevation.toggled.connect(self._emit_options)

    def _emit_options(self):
        self.options_changed.emit(self.current_options())

    def current_options(self) -> ExportOptions:
        return ExportOptions(
            concatenate=self._concatenate.isChecked(),
            include_time=self._include_time.isChecked(),
            include_elevation=self._include_elevation.isChecked(),
        )
