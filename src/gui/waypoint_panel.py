"""Right-panel widget shown when a Polarsteps waypoint is selected."""

from __future__ import annotations

from typing import Optional

from PyQt6.QtCore import Qt, QSize, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QPixmap
from PyQt6.QtWidgets import (
    QHBoxLayout, QLabel, QScrollArea, QSizePolicy,
    QVBoxLayout, QWidget,
)

from src.models.waypoint import TripStep


# ---------------------------------------------------------------------------
# Thumbnail loader (background thread)
# ---------------------------------------------------------------------------

class _ThumbnailLoader(QThread):
    loaded = pyqtSignal(int, object)   # photo_index, QPixmap | None

    def __init__(self, photos) -> None:
        super().__init__()
        self._photos = photos

    def run(self) -> None:
        import urllib.request
        for i, photo in enumerate(self._photos):
            url = photo.thumb_url or photo.url
            if not url:
                self.loaded.emit(i, None)
                continue
            try:
                with urllib.request.urlopen(url, timeout=10) as resp:
                    data = resp.read()
                px = QPixmap()
                px.loadFromData(data)
                self.loaded.emit(i, px if not px.isNull() else None)
            except Exception:
                self.loaded.emit(i, None)


# ---------------------------------------------------------------------------
# Waypoint Panel
# ---------------------------------------------------------------------------

class WaypointPanel(QWidget):
    """Shows a TripStep's name, date, description text, and photo thumbnails."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._loader: Optional[_ThumbnailLoader] = None
        self._thumb_labels: list[QLabel] = []
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(6)
        root.setContentsMargins(8, 8, 8, 8)

        # Header: name + date
        self._title_label = QLabel()
        font = QFont()
        font.setBold(True)
        font.setPointSize(11)
        self._title_label.setFont(font)
        self._title_label.setWordWrap(True)
        root.addWidget(self._title_label)

        self._date_label = QLabel()
        self._date_label.setStyleSheet("color: #666;")
        root.addWidget(self._date_label)

        # Separator
        sep = QWidget()
        sep.setFixedHeight(1)
        sep.setStyleSheet("background: #ccc;")
        root.addWidget(sep)

        # Description (scrollable)
        desc_scroll = QScrollArea()
        desc_scroll.setWidgetResizable(True)
        desc_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self._desc_label = QLabel()
        self._desc_label.setWordWrap(True)
        self._desc_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self._desc_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        desc_scroll.setWidget(self._desc_label)
        root.addWidget(desc_scroll, stretch=1)

        # Photo strip (horizontal scroll)
        photo_scroll = QScrollArea()
        photo_scroll.setWidgetResizable(True)
        photo_scroll.setFixedHeight(100)
        photo_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        photo_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        photo_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self._photo_container = QWidget()
        self._photo_layout = QHBoxLayout(self._photo_container)
        self._photo_layout.setContentsMargins(0, 0, 0, 0)
        self._photo_layout.setSpacing(4)
        self._photo_layout.addStretch()
        photo_scroll.setWidget(self._photo_container)
        root.addWidget(photo_scroll)
        self._photo_scroll = photo_scroll

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_step(self, step: TripStep) -> None:
        """Populate the panel with a TripStep's data."""
        self._title_label.setText(f"{step.name}  —  {step.trip_name}")
        self._date_label.setText(step.date.strftime("%Y-%m-%d %H:%M"))
        self._desc_label.setText(step.description or "(no description)")

        # Clear photo strip
        for lbl in self._thumb_labels:
            self._photo_layout.removeWidget(lbl)
            lbl.deleteLater()
        self._thumb_labels.clear()
        # Remove old stretch
        while self._photo_layout.count():
            item = self._photo_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not step.photos:
            self._photo_scroll.setVisible(False)
            return

        self._photo_scroll.setVisible(True)
        for _ in step.photos:
            lbl = QLabel("…")
            lbl.setFixedSize(QSize(80, 80))
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet("background: #eee; border-radius: 4px;")
            self._photo_layout.addWidget(lbl)
            self._thumb_labels.append(lbl)
        self._photo_layout.addStretch()

        # Load thumbnails in background
        if self._loader and self._loader.isRunning():
            self._loader.terminate()
        self._loader = _ThumbnailLoader(step.photos)
        self._loader.loaded.connect(self._on_thumb_loaded)
        self._loader.start()

    def clear(self) -> None:
        self._title_label.setText("")
        self._date_label.setText("")
        self._desc_label.setText("")
        for lbl in self._thumb_labels:
            lbl.deleteLater()
        self._thumb_labels.clear()

    # ------------------------------------------------------------------
    # Handlers
    # ------------------------------------------------------------------

    def _on_thumb_loaded(self, index: int, pixmap: Optional[QPixmap]) -> None:
        if index >= len(self._thumb_labels):
            return
        lbl = self._thumb_labels[index]
        if pixmap and not pixmap.isNull():
            lbl.setPixmap(pixmap.scaled(80, 80, Qt.AspectRatioMode.KeepAspectRatio,
                                        Qt.TransformationMode.SmoothTransformation))
            lbl.setStyleSheet("border-radius: 4px;")
        else:
            lbl.setText("?")
