"""ElevationStrip — elevation profile chart with an animated playhead."""

from __future__ import annotations

from typing import List, Optional, TYPE_CHECKING

from PyQt6.QtCore import Qt, QRectF, QPointF, QSize
from PyQt6.QtGui import (
    QColor, QLinearGradient, QPainter, QPainterPath, QPen, QFont, QPixmap,
)
from PyQt6.QtWidgets import QSizePolicy, QWidget

if TYPE_CHECKING:
    from src.animation.animation_state import AnimationSegment


class ElevationStrip(QWidget):
    """Draws a combined elevation profile for all animation segments.

    The static profile (filled area + line + axis labels) is pre-rendered to
    an offscreen QPixmap whenever the data or widget size changes.  Each
    animation tick only blits that pixmap and redraws the single playhead line,
    reducing per-frame work from O(N) to O(1).

    Call ``set_segments(segments)`` to populate, then ``set_playhead(fraction)``
    on every animation tick to move the playhead line.
    """

    _BG        = QColor("#fafafa")
    _FILL_TOP  = QColor(100, 160, 220, 180)
    _FILL_BOT  = QColor(100, 160, 220, 30)
    _LINE      = QColor(60, 120, 200)
    _PLAYHEAD  = QColor(220, 50, 50)
    _TEXT      = QColor(80, 80, 80)
    _PADDING   = {"top": 10, "right": 8, "bottom": 20, "left": 46}

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(90)
        self.setMaximumHeight(120)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._distances_km: List[float] = []
        self._elevations_m: List[float] = []
        self._total_km: float = 0.0
        self._playhead: float = 0.0    # 0–1

        # Offscreen cache — rebuilt only when data or size changes.
        self._profile_cache: Optional[QPixmap] = None
        self._cache_size: QSize = QSize()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_segments(self, segments: "List[AnimationSegment]") -> None:
        """Build a combined elevation profile from the animation segments."""
        distances: List[float] = []
        elevations: List[float] = []
        offset_km = 0.0

        for seg in segments:
            elev_data: List[Optional[float]] = getattr(seg, "_elevations", [])
            if not elev_data or len(elev_data) != len(seg.coords):
                offset_km += seg.total_km
                continue

            for i, elev in enumerate(elev_data):
                if elev is None:
                    continue
                distances.append(offset_km + seg.cumulative_km[i])
                elevations.append(elev)

            offset_km += seg.total_km

        self._distances_km = distances
        self._elevations_m = elevations
        self._total_km = offset_km
        self._profile_cache = None   # invalidate — will be rebuilt on next paint
        self.update()

    def set_playhead(self, fraction: float) -> None:
        """Move the playhead to *fraction* ∈ [0, 1]."""
        self._playhead = max(0.0, min(1.0, fraction))
        self.update()

    def clear(self) -> None:
        self._distances_km = []
        self._elevations_m = []
        self._total_km = 0.0
        self._playhead = 0.0
        self._profile_cache = None
        self.update()

    def has_data(self) -> bool:
        return len(self._elevations_m) >= 2

    # ------------------------------------------------------------------
    # Resize — invalidate the cached profile
    # ------------------------------------------------------------------

    def resizeEvent(self, event) -> None:  # noqa: N802
        self._profile_cache = None
        super().resizeEvent(event)

    # ------------------------------------------------------------------
    # Paint — O(1) per frame: one pixmap blit + one line
    # ------------------------------------------------------------------

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        w, h = self.width(), self.height()

        # Ensure the static profile pixmap is up to date.
        current_size = QSize(w, h)
        if self._profile_cache is None or self._cache_size != current_size:
            self._rebuild_cache(current_size)

        # Blit the pre-rendered profile (O(1) GPU blit).
        painter.drawPixmap(0, 0, self._profile_cache)

        if not self.has_data():
            return

        # Draw only the playhead — the only thing that changes per frame.
        pd = self._PADDING
        chart_x = pd["left"]
        chart_y = pd["top"]
        chart_w = w - pd["left"] - pd["right"]
        chart_h = h - pd["top"] - pd["bottom"]
        if chart_w <= 0 or chart_h <= 0:
            return

        ph_x = chart_x + self._playhead * chart_w
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(self._PLAYHEAD, 1.5))
        painter.drawLine(QPointF(ph_x, chart_y), QPointF(ph_x, chart_y + chart_h))

    # ------------------------------------------------------------------
    # Cache rebuild — called once per data/size change, not per frame
    # ------------------------------------------------------------------

    def _rebuild_cache(self, size: QSize) -> None:
        """Render the static profile (everything except the playhead) to a QPixmap."""
        self._cache_size = size
        w, h = size.width(), size.height()
        pm = QPixmap(w, h)
        painter = QPainter(pm)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pd = self._PADDING

        painter.fillRect(0, 0, w, h, self._BG)

        chart_x = pd["left"]
        chart_y = pd["top"]
        chart_w = w - pd["left"] - pd["right"]
        chart_h = h - pd["top"] - pd["bottom"]

        if not self.has_data() or chart_w <= 0 or chart_h <= 0:
            painter.setPen(self._TEXT)
            painter.drawText(
                QRectF(0, 0, w, h),
                Qt.AlignmentFlag.AlignCenter,
                "No elevation data",
            )
            painter.end()
            self._profile_cache = pm
            return

        dists = self._distances_km
        elevs = self._elevations_m
        min_e = min(elevs)
        max_e = max(elevs)
        rng_e = max_e - min_e or 1.0
        max_d = dists[-1] if dists else 1.0

        def px(d, e):
            x = chart_x + (d / max_d) * chart_w
            y = chart_y + chart_h - ((e - min_e) / rng_e) * chart_h
            return x, y

        # Filled area
        path = QPainterPath()
        x0, y0 = px(dists[0], elevs[0])
        path.moveTo(x0, chart_y + chart_h)
        path.lineTo(x0, y0)
        for d, e in zip(dists[1:], elevs[1:]):
            xx, yy = px(d, e)
            path.lineTo(xx, yy)
        xl, yl = px(dists[-1], elevs[-1])
        path.lineTo(xl, chart_y + chart_h)
        path.closeSubpath()

        grad = QLinearGradient(0, chart_y, 0, chart_y + chart_h)
        grad.setColorAt(0, self._FILL_TOP)
        grad.setColorAt(1, self._FILL_BOT)
        painter.fillPath(path, grad)

        # Profile line
        painter.setPen(QPen(self._LINE, 1.5))
        for i in range(len(dists) - 1):
            x1, y1 = px(dists[i],     elevs[i])
            x2, y2 = px(dists[i + 1], elevs[i + 1])
            painter.drawLine(QPointF(x1, y1), QPointF(x2, y2))

        # Elevation axis labels
        font = QFont()
        font.setPointSize(8)
        painter.setFont(font)
        painter.setPen(self._TEXT)
        painter.drawText(2, chart_y + chart_h, f"{int(min_e)}m")
        painter.drawText(2, chart_y + 10,      f"{int(max_e)}m")

        painter.end()
        self._profile_cache = pm
