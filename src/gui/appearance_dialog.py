"""Appearance settings dialog — tile provider, element sizes and colours."""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QColorDialog, QDialog, QDialogButtonBox, QFormLayout,
    QGroupBox, QHBoxLayout, QLabel, QPushButton, QSlider,
    QComboBox, QVBoxLayout, QWidget,
)


# Tile provider display names (must match keys in map_widget._TILE_OPTIONS)
_TILE_OPTIONS = {
    "OpenStreetMap":    "OpenStreetMap",
    "CartoDB Positron": "CartoDB Positron",
    "CartoDB Dark":     "CartoDB Dark",
}


class AppearanceDialog(QDialog):
    """Modal dialog for map appearance preferences."""

    def __init__(self, map_widget, config, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._map_widget = map_widget
        self._config = config
        self.setWindowTitle("Appearance")
        self.setModal(True)
        self.setMinimumWidth(380)

        # Snapshot originals for Cancel revert
        self._orig_tile     = map_widget.get_tile_provider()
        self._orig_tr_r     = map_widget.get_transport_radius()
        self._orig_tr_c     = map_widget.get_transport_color()
        self._orig_ci_r     = map_widget.get_circle_radius()
        self._orig_ci_c     = map_widget.get_circle_color()
        self._orig_wp_r     = map_widget.get_waypoint_radius()
        self._orig_wp_c     = map_widget.get_waypoint_color()

        # Working colour copies (QColor objects)
        self._tr_color  = QColor(self._orig_tr_c) if self._orig_tr_c else None
        self._ci_color  = QColor(self._orig_ci_c) if self._orig_ci_c else None
        self._wp_color  = QColor(self._orig_wp_c) if self._orig_wp_c else QColor("#FF8F00")

        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(12)
        root.setContentsMargins(12, 12, 12, 12)

        # --- Tiles ---
        tile_box = QGroupBox("Map Tiles")
        tile_form = QFormLayout(tile_box)
        tile_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self._tile_combo = QComboBox()
        for name in _TILE_OPTIONS:
            self._tile_combo.addItem(name)
        current_provider = self._map_widget.get_tile_provider()
        for display, key in _TILE_OPTIONS.items():
            if key == current_provider:
                self._tile_combo.setCurrentText(display)
                break
        self._tile_combo.currentTextChanged.connect(self._on_tile_changed)
        tile_form.addRow("Tile Provider:", self._tile_combo)
        root.addWidget(tile_box)

        # --- Transportation ---
        tr_box = QGroupBox("Transportation")
        tr_form = QFormLayout(tr_box)
        tr_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self._tr_slider = self._make_slider(4, 24, int(self._orig_tr_r))
        self._tr_slider.valueChanged.connect(
            lambda v: self._map_widget.set_transport_radius(float(v))
        )
        self._tr_color_btn = self._make_color_btn(
            self._tr_color or QColor("#8B4513"), nullable=True,
            null_label="Per type"
        )
        tr_form.addRow("Size:", self._tr_slider)
        tr_form.addRow("Color:", self._tr_color_btn)
        root.addWidget(tr_box)

        # --- Start & End Points ---
        ci_box = QGroupBox("Start & End Points")
        ci_form = QFormLayout(ci_box)
        ci_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self._ci_slider = self._make_slider(2, 14, int(self._orig_ci_r))
        self._ci_slider.valueChanged.connect(
            lambda v: self._map_widget.set_circle_radius(float(v))
        )
        self._ci_color_btn = self._make_color_btn(
            self._ci_color or QColor("#3388ff"), nullable=True,
            null_label="Per activity"
        )
        ci_form.addRow("Size:", self._ci_slider)
        ci_form.addRow("Color:", self._ci_color_btn)
        root.addWidget(ci_box)

        # --- Waypoints ---
        wp_box = QGroupBox("Waypoints")
        wp_form = QFormLayout(wp_box)
        wp_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self._wp_slider = self._make_slider(4, 24, int(self._orig_wp_r))
        self._wp_slider.valueChanged.connect(
            lambda v: self._map_widget.set_waypoint_radius(float(v))
        )
        self._wp_color_btn = self._make_color_btn(self._wp_color, nullable=False)
        wp_form.addRow("Size:", self._wp_slider)
        wp_form.addRow("Color:", self._wp_color_btn)
        root.addWidget(wp_box)

        # --- Buttons ---
        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel |
            QDialogButtonBox.StandardButton.Ok
        )
        btn_box.button(QDialogButtonBox.StandardButton.Ok).setText("Apply")
        btn_box.accepted.connect(self._apply)
        btn_box.rejected.connect(self._cancel)
        root.addWidget(btn_box)

    # ------------------------------------------------------------------
    # Widget helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _make_slider(min_v: int, max_v: int, value: int) -> QSlider:
        s = QSlider(Qt.Orientation.Horizontal)
        s.setRange(min_v, max_v)
        s.setValue(value)
        return s

    def _make_color_btn(
        self, color: Optional[QColor], nullable: bool, null_label: str = "Default"
    ) -> QWidget:
        """
        Returns a QWidget with a colour swatch button and optional Reset link.
        For nullable colours, a "Reset to default" label is shown when a colour
        override is active.
        """
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        swatch = QPushButton()
        swatch.setFixedSize(40, 24)
        swatch.setToolTip("Click to change colour")

        def _refresh_swatch(c: Optional[QColor]) -> None:
            if c:
                swatch.setStyleSheet(
                    f"background-color: {c.name()}; border: 1px solid #999; border-radius: 3px;"
                )
                swatch.setText("")
            else:
                swatch.setStyleSheet(
                    "background-color: #e8e8e8; border: 1px solid #999; border-radius: 3px;"
                    "color: #666; font-size: 9px;"
                )
                swatch.setText(null_label)

        _refresh_swatch(color if nullable else color)

        layout.addWidget(swatch)

        if nullable:
            reset_lbl = QLabel('<a href="#">Reset</a>')
            reset_lbl.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextBrowserInteraction
            )
            reset_lbl.setOpenExternalLinks(False)
            layout.addWidget(reset_lbl)

        layout.addStretch()

        # Store references on the container for later retrieval
        container._swatch = swatch           # type: ignore[attr-defined]
        container._color: Optional[QColor] = color  # type: ignore[attr-defined]
        container._nullable = nullable       # type: ignore[attr-defined]
        container._null_label = null_label   # type: ignore[attr-defined]
        container._refresh_swatch = _refresh_swatch  # type: ignore[attr-defined]

        def _on_swatch_clicked() -> None:
            initial = container._color or QColor("#888888")  # type: ignore[attr-defined]
            chosen = QColorDialog.getColor(initial, self, "Select Colour")
            if chosen.isValid():
                container._color = chosen   # type: ignore[attr-defined]
                _refresh_swatch(chosen)
                self._live_apply_color(container)

        swatch.clicked.connect(_on_swatch_clicked)

        if nullable:
            def _on_reset() -> None:
                container._color = None  # type: ignore[attr-defined]
                _refresh_swatch(None)
                self._live_apply_color(container)
            reset_lbl.linkActivated.connect(lambda _: _on_reset())  # type: ignore[union-attr]

        return container

    # ------------------------------------------------------------------
    # Live apply helpers
    # ------------------------------------------------------------------

    def _on_tile_changed(self, display_name: str) -> None:
        provider = _TILE_OPTIONS.get(display_name)
        if provider:
            self._map_widget.set_tile_provider(provider)

    def _live_apply_color(self, btn_widget: QWidget) -> None:
        c = btn_widget._color  # type: ignore[attr-defined]
        if btn_widget is self._tr_color_btn:
            self._map_widget.set_transport_color(c)
        elif btn_widget is self._ci_color_btn:
            self._map_widget.set_circle_color(c)
        elif btn_widget is self._wp_color_btn:
            self._map_widget.set_waypoint_color(c)

    # ------------------------------------------------------------------
    # Accept / Cancel
    # ------------------------------------------------------------------

    def _apply(self) -> None:
        tr_c = self._tr_color_btn._color  # type: ignore[attr-defined]
        ci_c = self._ci_color_btn._color  # type: ignore[attr-defined]
        wp_c = self._wp_color_btn._color  # type: ignore[attr-defined]

        d = {
            "tile_provider":    self._map_widget.get_tile_provider(),
            "transport_radius": float(self._tr_slider.value()),
            "transport_color":  tr_c.name() if tr_c else None,
            "circle_radius":    float(self._ci_slider.value()),
            "circle_color":     ci_c.name() if ci_c else None,
            "waypoint_radius":  float(self._wp_slider.value()),
            "waypoint_color":   (wp_c.name() if wp_c else "#FF8F00"),
        }
        self._config.save_appearance_settings(d)
        self.accept()

    def _cancel(self) -> None:
        # Revert all live changes
        self._map_widget.set_tile_provider(self._orig_tile)
        self._map_widget.set_transport_radius(self._orig_tr_r)
        self._map_widget.set_transport_color(self._orig_tr_c)
        self._map_widget.set_circle_radius(self._orig_ci_r)
        self._map_widget.set_circle_color(self._orig_ci_c)
        self._map_widget.set_waypoint_radius(self._orig_wp_r)
        self._map_widget.set_waypoint_color(self._orig_wp_c)
        self.reject()
