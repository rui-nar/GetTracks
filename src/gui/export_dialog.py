"""ExportDialog — modal dialog for configuring and saving a GPX/zip export."""

from __future__ import annotations

import os
from typing import Optional, TYPE_CHECKING

from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QFileDialog, QFormLayout,
    QFrame, QHBoxLayout, QLabel, QLineEdit, QMessageBox,
    QPushButton, QVBoxLayout, QWidget,
)
from PyQt6.QtCore import Qt

from src.gpx.processor import ExportOptions

if TYPE_CHECKING:
    pass


class ExportDialog(QDialog):
    """Modal dialog that collects export options and an output file path."""

    def __init__(
        self,
        has_waypoints: bool = False,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Export GPX")
        self.setModal(True)
        self.setFixedWidth(460)

        self._has_waypoints = has_waypoints

        self._build_ui()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(10)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        # --- Track options ---
        self._concatenate = QCheckBox("Merge into single track")
        self._concatenate.setToolTip(
            "Merge all selected activities into one continuous GPX track."
        )
        form.addRow("Tracks:", self._concatenate)

        self._include_time = QCheckBox("Timestamps")
        self._include_time.setChecked(True)
        self._include_time.setToolTip("Include per-point elapsed time in the exported GPX.")
        form.addRow("", self._include_time)

        self._include_elevation = QCheckBox("Elevation")
        self._include_elevation.setChecked(True)
        self._include_elevation.setToolTip("Include per-point elevation in the exported GPX.")
        form.addRow("", self._include_elevation)

        root.addLayout(form)

        # --- Waypoints section (shown only when project has waypoints) ---
        self._wpt_sep = QFrame()
        self._wpt_sep.setFrameShape(QFrame.Shape.HLine)
        self._wpt_sep.setFrameShadow(QFrame.Shadow.Sunken)
        root.addWidget(self._wpt_sep)

        wpt_form = QFormLayout()
        wpt_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._include_waypoints = QCheckBox("Include Polarsteps waypoints")
        self._include_waypoints.setChecked(True)
        self._include_waypoints.setToolTip(
            "Include Polarsteps trip steps as <wpt> elements in the GPX."
        )
        wpt_form.addRow("Waypoints:", self._include_waypoints)

        self._photo_mode_combo = QComboBox()
        self._photo_mode_combo.addItem("CDN photo links (online only)", "cdn")
        self._photo_mode_combo.addItem("Download photos — save as .zip", "local")
        self._photo_mode_combo.setToolTip(
            "CDN links: embed public Polarsteps thumbnail URLs (fast, requires internet).\n"
            "Download photos: fetch thumbnails and bundle them in a .zip archive."
        )
        wpt_form.addRow("Photos:", self._photo_mode_combo)

        root.addLayout(wpt_form)

        # Connect to update path extension + visibility
        self._include_waypoints.toggled.connect(self._on_waypoints_toggled)
        self._photo_mode_combo.currentIndexChanged.connect(self._on_photo_mode_changed)

        # Show/hide the whole section
        self._wpt_sep.setVisible(self._has_waypoints)
        self._include_waypoints.setVisible(self._has_waypoints)
        self._photo_mode_combo.setVisible(self._has_waypoints)

        # --- Output path ---
        path_sep = QFrame()
        path_sep.setFrameShape(QFrame.Shape.HLine)
        path_sep.setFrameShadow(QFrame.Shadow.Sunken)
        root.addWidget(path_sep)

        path_label = QLabel("Save to:")
        root.addWidget(path_label)

        path_row = QHBoxLayout()
        self._path_edit = QLineEdit()
        self._path_edit.setPlaceholderText("Select output file…")
        path_row.addWidget(self._path_edit)
        browse_btn = QPushButton("Browse…")
        browse_btn.setFixedWidth(80)
        browse_btn.clicked.connect(self._on_browse)
        path_row.addWidget(browse_btn)
        root.addLayout(path_row)

        # --- Buttons ---
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)
        self._ok_btn = QPushButton("Export")
        self._ok_btn.setDefault(True)
        self._ok_btn.clicked.connect(self._on_ok)
        btn_row.addWidget(self._ok_btn)
        root.addLayout(btn_row)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _want_zip(self) -> bool:
        return (
            self._has_waypoints
            and self._include_waypoints.isChecked()
            and self._photo_mode_combo.currentData() == "local"
        )

    def _current_ext(self) -> str:
        return ".zip" if self._want_zip() else ".gpx"

    def _file_filter(self) -> str:
        return "Zip Archives (*.zip)" if self._want_zip() else "GPX Files (*.gpx)"

    # ------------------------------------------------------------------
    # Handlers
    # ------------------------------------------------------------------

    def _on_waypoints_toggled(self, checked: bool) -> None:
        self._photo_mode_combo.setVisible(checked and self._has_waypoints)
        self._sync_path_ext()

    def _on_photo_mode_changed(self, _: int) -> None:
        self._sync_path_ext()

    def _sync_path_ext(self) -> None:
        """Update the path extension when format changes."""
        path = self._path_edit.text()
        if path:
            base = os.path.splitext(path)[0]
            self._path_edit.setText(base + self._current_ext())

    def _on_browse(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Export", self._path_edit.text() or "", self._file_filter()
        )
        if path:
            ext = self._current_ext()
            if not path.lower().endswith(ext):
                path += ext
            self._path_edit.setText(path)

    def _on_ok(self) -> None:
        path = self._path_edit.text().strip()
        if not path:
            QMessageBox.warning(self, "No output file", "Please select an output file.")
            return
        self.accept()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def selected_path(self) -> str:
        path = self._path_edit.text().strip()
        ext = self._current_ext()
        if path and not path.lower().endswith(ext):
            path += ext
        return path

    def current_options(self) -> ExportOptions:
        return ExportOptions(
            concatenate=self._concatenate.isChecked(),
            include_time=self._include_time.isChecked(),
            include_elevation=self._include_elevation.isChecked(),
            include_waypoints=(
                self._has_waypoints and self._include_waypoints.isChecked()
            ),
            waypoint_photos=self._photo_mode_combo.currentData() or "cdn",
        )
