"""Detail panel for a Polarsteps waypoint — shown in the activity details area."""

from __future__ import annotations

from typing import List, Optional

from PyQt6.QtCore import Qt, QSize, QThread, pyqtSignal
from PyQt6.QtGui import QCursor, QFont, QPixmap
from PyQt6.QtWidgets import (
    QHBoxLayout, QLabel, QScrollArea, QSizePolicy,
    QVBoxLayout, QWidget,
)

from src.models.waypoint import StepPhoto, TripStep


# ---------------------------------------------------------------------------
# Thumbnail loader
# ---------------------------------------------------------------------------

class _ThumbnailLoader(QThread):
    loaded = pyqtSignal(int, object)   # index, bytes | None

    def __init__(self, photos: List[StepPhoto], headers: dict) -> None:
        super().__init__()
        self._photos = photos
        self._headers = headers

    def run(self) -> None:
        import ssl
        import urllib.request
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        for i, photo in enumerate(self._photos):
            url = photo.thumb_url or photo.url  # small thumb for panel strip
            if not url:
                self.loaded.emit(i, None)
                continue
            try:
                req = urllib.request.Request(url, headers=self._headers)
                with urllib.request.urlopen(req, timeout=10, context=ctx) as resp:
                    data = resp.read()
                self.loaded.emit(i, data)  # emit bytes; QPixmap created on main thread
            except Exception:
                self.loaded.emit(i, None)


# ---------------------------------------------------------------------------
# Clickable thumbnail label
# ---------------------------------------------------------------------------

class _ThumbLabel(QLabel):
    clicked = pyqtSignal(int)  # photo index

    def __init__(self, index: int) -> None:
        super().__init__()
        self._index = index
        self.setFixedSize(QSize(90, 90))
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet(
            "background: #ddd; border-radius: 4px; border: 2px solid transparent;"
        )
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._index)

    def enterEvent(self, event) -> None:
        self.setStyleSheet(
            "background: #ddd; border-radius: 4px; border: 2px solid #FF8F00;"
        )

    def leaveEvent(self, event) -> None:
        self.setStyleSheet(
            "background: #ddd; border-radius: 4px; border: 2px solid transparent;"
        )


# ---------------------------------------------------------------------------
# Waypoint Panel
# ---------------------------------------------------------------------------

class WaypointPanel(QWidget):
    """Shows a TripStep's name, date, description, and clickable photo thumbnails."""

    def __init__(self, parent: Optional[QWidget] = None, request_headers: Optional[dict] = None) -> None:
        super().__init__(parent)
        self._loader: Optional[_ThumbnailLoader] = None
        self._thumb_labels: List[_ThumbLabel] = []
        self._current_step: Optional[TripStep] = None
        self._request_headers: dict = request_headers or {}
        self._build_ui()

    def set_request_headers(self, headers: dict) -> None:
        self._request_headers = headers

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(6)
        root.setContentsMargins(8, 8, 8, 8)

        # Header
        self._title_label = QLabel()
        font = QFont()
        font.setBold(True)
        font.setPointSize(11)
        self._title_label.setFont(font)
        self._title_label.setWordWrap(True)
        root.addWidget(self._title_label)

        self._meta_label = QLabel()
        self._meta_label.setStyleSheet("color: #666;")
        root.addWidget(self._meta_label)

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

        # Photo strip (horizontal scroll, clickable thumbnails)
        photo_scroll = QScrollArea()
        photo_scroll.setWidgetResizable(True)
        photo_scroll.setFixedHeight(110)
        photo_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        photo_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        photo_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self._photo_container = QWidget()
        self._photo_layout = QHBoxLayout(self._photo_container)
        self._photo_layout.setContentsMargins(0, 0, 0, 0)
        self._photo_layout.setSpacing(6)
        self._photo_layout.addStretch()
        photo_scroll.setWidget(self._photo_container)
        root.addWidget(photo_scroll)
        self._photo_scroll = photo_scroll

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_step(self, step: TripStep) -> None:
        self._current_step = step
        self._title_label.setText(f"{step.name}  —  {step.trip_name}")
        date_str = step.date.strftime("%Y-%m-%d %H:%M")
        photos_hint = f"  ·  {len(step.photos)} photo{'s' if len(step.photos) != 1 else ''}" if step.photos else ""
        self._meta_label.setText(f"{date_str}{photos_hint}")
        self._desc_label.setText(step.description or "(no description)")

        # Rebuild photo strip
        while self._photo_layout.count():
            item = self._photo_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._thumb_labels.clear()

        if not step.photos:
            self._photo_scroll.setVisible(False)
        else:
            self._photo_scroll.setVisible(True)
            for i, _ in enumerate(step.photos):
                lbl = _ThumbLabel(i)
                lbl.setText("…")
                lbl.clicked.connect(self._on_thumb_clicked)
                self._photo_layout.addWidget(lbl)
                self._thumb_labels.append(lbl)
            self._photo_layout.addStretch()

            if self._loader and self._loader.isRunning():
                self._loader.terminate()
            self._loader = _ThumbnailLoader(step.photos, self._request_headers)
            self._loader.loaded.connect(self._on_thumb_loaded)
            self._loader.start()

    def clear(self) -> None:
        self._current_step = None
        self._title_label.setText("")
        self._meta_label.setText("")
        self._desc_label.setText("")
        while self._photo_layout.count():
            item = self._photo_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._thumb_labels.clear()

    # ------------------------------------------------------------------
    # Handlers
    # ------------------------------------------------------------------

    def _on_thumb_loaded(self, index: int, data) -> None:
        if index >= len(self._thumb_labels):
            return
        lbl = self._thumb_labels[index]
        if data:
            px = QPixmap()
            px.loadFromData(data)
            if not px.isNull():
                lbl.setPixmap(px.scaled(
                    86, 86,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                ))
                return
        lbl.setText("?")

    def _on_thumb_clicked(self, index: int) -> None:
        if self._current_step is None or not self._current_step.photos:
            return
        from src.gui.photo_viewer_dialog import PhotoViewerDialog
        dlg = PhotoViewerDialog(
            self._current_step.photos, start_index=index,
            parent=self, request_headers=self._request_headers,
        )
        dlg.exec()
