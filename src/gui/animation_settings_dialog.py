"""Dialog for configuring animation segment speeds."""

from __future__ import annotations

from typing import Optional

from PyQt6.QtWidgets import (
    QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout,
    QLabel, QVBoxLayout, QWidget,
)
from PyQt6.QtCore import Qt

from src.config.settings import Config

# Labels and order for the UI
_TRANSPORT_LABELS = [
    ("flight", "Flight (km/h)"),
    ("train",  "Train (km/h)"),
    ("bus",    "Bus (km/h)"),
    ("boat",   "Boat (km/h)"),
]


class AnimationSettingsDialog(QDialog):
    """Let the user adjust the visual pacing speed for each connecting-segment type."""

    def __init__(self, config: Config, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._config = config
        self.setWindowTitle("Animation — Segment Speeds")
        self.setModal(True)
        self.setFixedWidth(340)
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)

        note = QLabel(
            "These speeds control how fast connecting segments (train, flight, etc.) "
            "advance through the animation relative to GPS activities.\n"
            "Lower values make segments appear slower and more comparable to rides/hikes."
        )
        note.setWordWrap(True)
        note.setAlignment(Qt.AlignmentFlag.AlignLeft)
        root.addWidget(note)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        current = self._config.get_animation_speeds()
        self._spinboxes: dict[str, QDoubleSpinBox] = {}

        for key, label in _TRANSPORT_LABELS:
            sb = QDoubleSpinBox()
            sb.setRange(1.0, 2000.0)
            sb.setSingleStep(5.0)
            sb.setDecimals(0)
            sb.setValue(current.get(key, 50.0))
            form.addRow(label + ":", sb)
            self._spinboxes[key] = sb

        root.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _on_accept(self) -> None:
        speeds = {key: sb.value() for key, sb in self._spinboxes.items()}
        self._config.save_animation_speeds(speeds)
        self.accept()
