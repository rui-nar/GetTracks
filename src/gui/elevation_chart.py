"""QPainter-based elevation profile chart widget."""

import math
from typing import List
from PyQt6.QtWidgets import QWidget, QSizePolicy
from PyQt6.QtCore import Qt, QRectF, QPointF
from PyQt6.QtGui import (
    QPainter, QPainterPath, QColor, QLinearGradient,
    QPen, QFont, QFontMetrics,
)


class ElevationChart(QWidget):
    """Draws a filled elevation-vs-distance profile using QPainter.

    Call set_data(distances_km, elevations_m) to populate, or
    set_loading(True/False) to show a placeholder while data is being fetched.
    """

    _BG         = QColor("#fafafa")
    _FILL_TOP   = QColor(100, 160, 220, 180)
    _FILL_BOT   = QColor(100, 160, 220, 30)
    _LINE       = QColor(60, 120, 200)
    _GRID       = QColor(220, 220, 220)
    _TEXT       = QColor(80, 80, 80)
    _LOADING    = QColor(160, 160, 160)

    _PADDING = {"top": 18, "right": 12, "bottom": 28, "left": 52}

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(120)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._distances: List[float] = []
        self._elevations: List[float] = []
        self._loading = False
        self._activity_name = ""

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_data(self, distances_km: List[float], elevations_m: List[float],
                 activity_name: str = "") -> None:
        self._distances = distances_km
        self._elevations = elevations_m
        self._activity_name = activity_name
        self._loading = False
        self.update()

    def set_loading(self, loading: bool) -> None:
        self._loading = loading
        if loading:
            self._distances = []
            self._elevations = []
        self.update()

    def clear(self) -> None:
        self._distances = []
        self._elevations = []
        self._loading = False
        self._activity_name = ""
        self.update()

    # ------------------------------------------------------------------
    # Painting
    # ------------------------------------------------------------------

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        p = self._PADDING

        painter.fillRect(0, 0, w, h, self._BG)

        chart_x = p["left"]
        chart_y = p["top"]
        chart_w = w - p["left"] - p["right"]
        chart_h = h - p["top"] - p["bottom"]

        if chart_w <= 0 or chart_h <= 0:
            return

        if self._loading:
            self._draw_placeholder(painter, w, h, "Loading elevation…")
            return

        if not self._distances or not self._elevations:
            self._draw_placeholder(painter, w, h, "No elevation data")
            return

        elev_min = min(self._elevations)
        elev_max = max(self._elevations)
        elev_range = max(elev_max - elev_min, 1.0)
        dist_max = max(self._distances) or 1.0

        def to_px(dist: float, elev: float):
            x = chart_x + (dist / dist_max) * chart_w
            y = chart_y + chart_h - ((elev - elev_min) / elev_range) * chart_h
            return QPointF(x, y)

        font = QFont()
        font.setPointSize(8)
        painter.setFont(font)
        fm = QFontMetrics(font)

        # Horizontal grid lines + Y-axis labels (3 levels)
        painter.setPen(QPen(self._GRID, 1))
        for frac in (0.0, 0.5, 1.0):
            y = chart_y + chart_h * (1 - frac)
            painter.drawLine(int(chart_x), int(y), int(chart_x + chart_w), int(y))
        painter.setPen(QPen(self._TEXT))
        for frac in (0.0, 0.5, 1.0):
            elev_val = elev_min + frac * elev_range
            y = chart_y + chart_h * (1 - frac)
            label = f"{elev_val:,.0f}m"
            lw = fm.horizontalAdvance(label)
            painter.drawText(int(chart_x - lw - 4), int(y + 4), label)

        # X-axis ticks — dynamic "nice" step, always ~5 divisions
        x_step = self._nice_step(dist_max, target_divisions=5)
        tick_val = 0.0
        while tick_val <= dist_max + x_step * 0.01:
            x = chart_x + (min(tick_val, dist_max) / dist_max) * chart_w
            # Light vertical grid line
            painter.setPen(QPen(self._GRID, 1))
            painter.drawLine(int(x), int(chart_y), int(x), int(chart_y + chart_h))
            # Tick label
            painter.setPen(QPen(self._TEXT))
            label = f"{tick_val:.0f}" if tick_val == int(tick_val) else f"{tick_val:.1f}"
            lw = fm.horizontalAdvance(label)
            painter.drawText(int(x - lw / 2), int(chart_y + chart_h + 14), label)
            tick_val += x_step
        # Unit label at far right
        painter.drawText(int(chart_x + chart_w - fm.horizontalAdvance("km") + 2),
                         int(chart_y + chart_h + 14), "km")

        # Filled area path
        path = QPainterPath()
        first = to_px(self._distances[0], self._elevations[0])
        path.moveTo(first)
        for d, e in zip(self._distances[1:], self._elevations[1:]):
            path.lineTo(to_px(d, e))

        last_pt = to_px(self._distances[-1], self._elevations[-1])
        path.lineTo(QPointF(last_pt.x(), chart_y + chart_h))
        path.lineTo(QPointF(first.x(), chart_y + chart_h))
        path.closeSubpath()

        grad = QLinearGradient(0, chart_y, 0, chart_y + chart_h)
        grad.setColorAt(0, self._FILL_TOP)
        grad.setColorAt(1, self._FILL_BOT)
        painter.setBrush(grad)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawPath(path)

        # Line on top
        line_path = QPainterPath()
        line_path.moveTo(to_px(self._distances[0], self._elevations[0]))
        for d, e in zip(self._distances[1:], self._elevations[1:]):
            line_path.lineTo(to_px(d, e))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(self._LINE, 1.5))
        painter.drawPath(line_path)

        # Activity name + elevation gain label (top-left)
        if self._activity_name:
            painter.setPen(QPen(self._TEXT))
            font.setPointSize(8)
            painter.setFont(font)
            gain = max(0.0, sum(
                max(0, self._elevations[i] - self._elevations[i - 1])
                for i in range(1, len(self._elevations))
            ))
            info = f"↑ {gain:.0f} m  ·  {elev_min:.0f}–{elev_max:.0f} m"
            painter.drawText(int(chart_x + 4), int(chart_y + 12), info)

    @staticmethod
    def _nice_step(total: float, target_divisions: int = 5) -> float:
        """Return a "nice" axis step such that total / step ≈ target_divisions."""
        raw = total / target_divisions
        mag = 10 ** math.floor(math.log10(raw)) if raw > 0 else 1
        for candidate in (1, 2, 2.5, 5, 10):
            step = candidate * mag
            if total / step <= target_divisions + 1:
                return step
        return 10 * mag

    def _draw_placeholder(self, painter: QPainter, w: int, h: int, text: str) -> None:
        painter.setPen(QPen(self._LOADING))
        font = QFont()
        font.setPointSize(9)
        painter.setFont(font)
        painter.drawText(QRectF(0, 0, w, h), Qt.AlignmentFlag.AlignCenter, text)
