"""Full-screen photo viewer with previous/next navigation."""

from __future__ import annotations

import urllib.request
from typing import List, Optional

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QKeySequence, QPixmap, QShortcut
from PyQt6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QPushButton,
    QSizePolicy, QVBoxLayout, QWidget,
)

from src.models.waypoint import StepPhoto


class _FullResLoader(QThread):
    loaded = pyqtSignal(object)  # QPixmap | None

    def __init__(self, url: str) -> None:
        super().__init__()
        self._url = url

    def run(self) -> None:
        try:
            with urllib.request.urlopen(self._url, timeout=20) as resp:
                data = resp.read()
            px = QPixmap()
            px.loadFromData(data)
            self.loaded.emit(px if not px.isNull() else None)
        except Exception:
            self.loaded.emit(None)


class PhotoViewerDialog(QDialog):
    """Modal dialog that shows a photo at full size with prev/next navigation."""

    def __init__(
        self,
        photos: List[StepPhoto],
        start_index: int = 0,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._photos = photos
        self._index = max(0, min(start_index, len(photos) - 1))
        self._loader: Optional[_FullResLoader] = None

        self.setWindowTitle("Photo")
        self.setModal(True)
        self.resize(900, 700)
        self._build_ui()
        self._load_current()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        # Photo display area
        self._photo_label = QLabel()
        self._photo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._photo_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self._photo_label.setStyleSheet("background: #111;")
        self._photo_label.setText("Loading…")
        self._photo_label.setStyleSheet(
            "background: #111; color: #aaa; font-size: 14px;"
        )
        root.addWidget(self._photo_label, stretch=1)

        # Caption
        self._caption_label = QLabel()
        self._caption_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._caption_label.setWordWrap(True)
        self._caption_label.setStyleSheet("color: #555; font-style: italic;")
        root.addWidget(self._caption_label)

        # Nav row
        nav = QHBoxLayout()
        self._prev_btn = QPushButton("◀  Previous")
        self._prev_btn.setFixedWidth(120)
        self._prev_btn.clicked.connect(self._go_prev)
        nav.addWidget(self._prev_btn)

        nav.addStretch()

        self._counter_label = QLabel()
        self._counter_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        nav.addWidget(self._counter_label)

        nav.addStretch()

        self._next_btn = QPushButton("Next  ▶")
        self._next_btn.setFixedWidth(120)
        self._next_btn.clicked.connect(self._go_next)
        nav.addWidget(self._next_btn)

        root.addLayout(nav)

        # Keyboard shortcuts
        QShortcut(QKeySequence(Qt.Key.Key_Left),  self, self._go_prev)
        QShortcut(QKeySequence(Qt.Key.Key_Right), self, self._go_next)
        QShortcut(QKeySequence(Qt.Key.Key_Escape), self, self.reject)

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def _go_prev(self) -> None:
        if self._index > 0:
            self._index -= 1
            self._load_current()

    def _go_next(self) -> None:
        if self._index < len(self._photos) - 1:
            self._index += 1
            self._load_current()

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def _load_current(self) -> None:
        photo = self._photos[self._index]
        n = len(self._photos)

        self._counter_label.setText(f"{self._index + 1} / {n}")
        self._prev_btn.setEnabled(self._index > 0)
        self._next_btn.setEnabled(self._index < n - 1)

        caption = photo.caption or ""
        self._caption_label.setText(caption)
        self._caption_label.setVisible(bool(caption))

        self._photo_label.setPixmap(QPixmap())
        self._photo_label.setText("Loading…")

        if self._loader and self._loader.isRunning():
            self._loader.terminate()
            self._loader.wait()

        url = photo.url or photo.thumb_url
        if not url:
            self._photo_label.setText("No image available")
            return

        self._loader = _FullResLoader(url)
        self._loader.loaded.connect(self._on_loaded)
        self._loader.start()

    def _on_loaded(self, px: Optional[QPixmap]) -> None:
        if px is None:
            self._photo_label.setText("Failed to load image")
            return
        self._current_pixmap = px
        self._update_scaled()

    def _update_scaled(self) -> None:
        if not hasattr(self, "_current_pixmap") or self._current_pixmap is None:
            return
        self._photo_label.setText("")
        size = self._photo_label.size()
        scaled = self._current_pixmap.scaled(
            size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._photo_label.setPixmap(scaled)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._update_scaled()
