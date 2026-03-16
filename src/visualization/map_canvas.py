"""Native Qt slippy-map canvas — replaces QWebEngineView + Folium.

Rendering layers (bottom to top):
  1. Tile grid  — fetched asynchronously, painted from cache
  2. Polylines  — GPS tracks
  3. Markers    — start-point circles
  4. Attribution — OSM copyright notice (required by usage policy)

Mouse events:
  - Left-drag   → pan
  - Scroll wheel → zoom (centred on cursor)
  - Double-click → zoom in one level, centred on click point

Public API mirrors the old Folium-based MapWidget so ``map_widget.py``
can swap it in transparently.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from PyQt6.QtCore import Qt, QPoint, QPointF, pyqtSignal
from PyQt6.QtGui import (
    QColor, QFont, QPainter, QPen, QPixmap,
    QMouseEvent, QWheelEvent, QPaintEvent, QResizeEvent,
)
from PyQt6.QtWidgets import QWidget

from src.visualization.map_projection import (
    MIN_ZOOM, MAX_ZOOM, TILE_SIZE,
    lat_lon_to_world_px, lat_lon_to_tile, tile_to_world_px,
    world_px_to_screen, screen_to_world_px,
    fit_bounds_center, fit_bounds_zoom,
)
from src.visualization.tile_provider import TileProvider
from src.visualization.tile_cache import MemoryTileCache, DiskTileCache


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class Polyline:
    coords: List[Tuple[float, float]]   # [(lat, lon), …]
    color: QColor = field(default_factory=lambda: QColor("#3388ff"))
    weight: float = 3.0
    opacity: float = 0.8
    tooltip: str = ""


@dataclass
class Marker:
    lat: float
    lon: float
    color: QColor = field(default_factory=lambda: QColor("#3388ff"))
    radius: float = 6.0
    tooltip: str = ""


# ---------------------------------------------------------------------------
# Placeholder tile color
# ---------------------------------------------------------------------------

_PLACEHOLDER_COLOR = QColor(220, 220, 220)
_GRID_COLOR        = QColor(200, 200, 200)
_ATTRIBUTION_TEXT  = "© OpenStreetMap contributors"
_ATTRIBUTION_BG    = QColor(255, 255, 255, 180)


class MapCanvas(QWidget):
    """Pure-Qt interactive slippy-map canvas.

    Args:
        mem_cache:  Shared ``MemoryTileCache``.
        disk_cache: Optional ``DiskTileCache`` for persistence.
        provider:   TileProvider name or URL template.
    """

    # Emitted whenever the view changes (zoom/pan) — useful for status bars
    view_changed = pyqtSignal(float, float, int)   # lat, lon, zoom

    def __init__(
        self,
        mem_cache: Optional[MemoryTileCache] = None,
        disk_cache: Optional[DiskTileCache] = None,
        provider: str = "OpenStreetMap",
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setMinimumSize(200, 150)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)
        self.setMouseTracking(True)

        # View state
        self._zoom: int = 2
        self._center_lat: float = 20.0
        self._center_lon: float = 0.0

        # Overlays
        self._polylines: List[Polyline] = []
        self._markers:   List[Marker]   = []

        # Tile pixmap cache (decoded QPixmap, keyed by (z,tx,ty))
        self._pixmap_cache: dict[Tuple[int, int, int], QPixmap] = {}

        # Network provider
        _mem  = mem_cache  or MemoryTileCache(max_size=512)
        _disk = disk_cache
        self._provider = TileProvider(_mem, _disk, provider, parent=self)
        self._provider.tile_ready.connect(self._on_tile_ready)

        # Pan state
        self._drag_start: Optional[QPoint] = None
        self._drag_center_wx: float = 0.0
        self._drag_center_wy: float = 0.0

    # ------------------------------------------------------------------
    # Public API — view control
    # ------------------------------------------------------------------

    def set_view(self, lat: float, lon: float, zoom: int) -> None:
        self._zoom = max(MIN_ZOOM, min(MAX_ZOOM, zoom))
        self._center_lat = lat
        self._center_lon = lon
        self._pixmap_cache.clear()
        self.update()
        self.view_changed.emit(lat, lon, self._zoom)

    def fit_bounds(
        self,
        min_lat: float, max_lat: float,
        min_lon: float, max_lon: float,
    ) -> None:
        lat, lon = fit_bounds_center(min_lat, max_lat, min_lon, max_lon)
        zoom = fit_bounds_zoom(
            min_lat, max_lat, min_lon, max_lon,
            self.width(), self.height(),
        )
        self.set_view(lat, lon, zoom)

    def set_provider(self, provider: str) -> None:
        self._provider.set_provider(provider)
        self._pixmap_cache.clear()
        self.update()

    # ------------------------------------------------------------------
    # Overlay management
    # ------------------------------------------------------------------

    def clear_overlays(self) -> None:
        self._polylines.clear()
        self._markers.clear()
        self.update()

    def add_polyline(self, polyline: Polyline) -> None:
        self._polylines.append(polyline)
        self.update()

    def add_marker(self, marker: Marker) -> None:
        self._markers.append(marker)
        self.update()

    # ------------------------------------------------------------------
    # Qt event handlers
    # ------------------------------------------------------------------

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        self._draw_tiles(p)
        self._draw_polylines(p)
        self._draw_markers(p)
        self._draw_attribution(p)

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        self._pixmap_cache.clear()
        self.update()

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start = event.pos()
            cx, cy = self._center_world_px()
            self._drag_center_wx = cx
            self._drag_center_wy = cy
            self.setCursor(Qt.CursorShape.ClosedHandCursor)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._drag_start is not None:
            delta = event.pos() - self._drag_start
            new_wx = self._drag_center_wx - delta.x()
            new_wy = self._drag_center_wy - delta.y()
            self._set_center_from_world_px(new_wx, new_wy)
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start = None
            self.setCursor(Qt.CursorShape.ArrowCursor)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            # Zoom in, centering on the clicked point
            sx, sy = event.pos().x(), event.pos().y()
            cx, cy = self._center_world_px()
            wx, wy = screen_to_world_px(sx, sy, cx, cy, self.width(), self.height())
            # Scale world coords to new zoom
            new_zoom = min(self._zoom + 1, MAX_ZOOM)
            scale = 2 ** (new_zoom - self._zoom)
            self._zoom = new_zoom
            self._set_center_from_world_px(wx * scale, wy * scale)
            self._pixmap_cache.clear()
            self.update()

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802
        delta = event.angleDelta().y()
        if delta == 0:
            return
        sx, sy = event.position().x(), event.position().y()
        cx, cy = self._center_world_px()
        wx, wy = screen_to_world_px(sx, sy, cx, cy, self.width(), self.height())

        old_zoom = self._zoom
        if delta > 0:
            self._zoom = min(self._zoom + 1, MAX_ZOOM)
        else:
            self._zoom = max(self._zoom - 1, MIN_ZOOM)

        if self._zoom == old_zoom:
            return

        scale = 2 ** (self._zoom - old_zoom)
        # Keep the point under the cursor stationary
        new_cx = wx * scale - (sx - self.width()  / 2.0)
        new_cy = wy * scale - (sy - self.height() / 2.0)
        self._set_center_from_world_px(new_cx, new_cy)
        self._pixmap_cache.clear()
        self.update()
        self.view_changed.emit(self._center_lat, self._center_lon, self._zoom)

    # ------------------------------------------------------------------
    # Tile slot
    # ------------------------------------------------------------------

    def _on_tile_ready(self, z: int, tx: int, ty: int, data: bytes) -> None:
        if z != self._zoom:
            return  # stale
        pm = QPixmap()
        pm.loadFromData(data)
        if not pm.isNull():
            self._pixmap_cache[(z, tx, ty)] = pm
            self.update()

    # ------------------------------------------------------------------
    # Drawing helpers
    # ------------------------------------------------------------------

    def _draw_tiles(self, p: QPainter) -> None:
        z = self._zoom
        cx, cy = self._center_world_px()
        W, H = self.width(), self.height()

        # Range of tiles visible in the viewport
        world_size = (2 ** z) * TILE_SIZE
        half_w, half_h = W / 2.0, H / 2.0

        tx_min = int((cx - half_w) / TILE_SIZE)
        tx_max = int((cx + half_w) / TILE_SIZE)
        ty_min = int((cy - half_h) / TILE_SIZE)
        ty_max = int((cy + half_h) / TILE_SIZE)

        n = 2 ** z
        for tx in range(tx_min, tx_max + 1):
            for ty in range(ty_min, ty_max + 1):
                if ty < 0 or ty >= n:
                    continue
                tx_wrapped = tx % n   # wrap horizontally

                twx, twy = tile_to_world_px(tx, ty)
                sx, sy = world_px_to_screen(twx, twy, cx, cy, W, H)

                key = (z, tx_wrapped, ty)
                if key in self._pixmap_cache:
                    p.drawPixmap(int(sx), int(sy), self._pixmap_cache[key])
                else:
                    # Placeholder
                    p.fillRect(int(sx), int(sy), TILE_SIZE, TILE_SIZE, _PLACEHOLDER_COLOR)
                    p.setPen(_GRID_COLOR)
                    p.drawRect(int(sx), int(sy), TILE_SIZE, TILE_SIZE)
                    self._provider.request_tile(z, tx_wrapped, ty)

    def _draw_polylines(self, p: QPainter) -> None:
        if not self._polylines:
            return
        z = self._zoom
        cx, cy = self._center_world_px()
        W, H = self.width(), self.height()

        for poly in self._polylines:
            if len(poly.coords) < 2:
                continue
            color = QColor(poly.color)
            color.setAlphaF(poly.opacity)
            pen = QPen(color, poly.weight)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            p.setPen(pen)

            pts = []
            for lat, lon in poly.coords:
                wx, wy = lat_lon_to_world_px(lat, lon, z)
                sx, sy = world_px_to_screen(wx, wy, cx, cy, W, H)
                pts.append(QPointF(sx, sy))

            for i in range(len(pts) - 1):
                p.drawLine(pts[i], pts[i + 1])

    def _draw_markers(self, p: QPainter) -> None:
        if not self._markers:
            return
        z = self._zoom
        cx, cy = self._center_world_px()
        W, H = self.width(), self.height()

        for m in self._markers:
            wx, wy = lat_lon_to_world_px(m.lat, m.lon, z)
            sx, sy = world_px_to_screen(wx, wy, cx, cy, W, H)
            p.setBrush(m.color)
            p.setPen(QPen(m.color.lighter(150), 1))
            p.drawEllipse(QPointF(sx, sy), m.radius, m.radius)

        p.setBrush(Qt.BrushStyle.NoBrush)

    def _draw_attribution(self, p: QPainter) -> None:
        font = QFont("Arial", 9)
        p.setFont(font)
        fm = p.fontMetrics()
        text = _ATTRIBUTION_TEXT
        tw = fm.horizontalAdvance(text)
        th = fm.height()
        margin = 4
        x = self.width()  - tw - margin * 2
        y = self.height() - th - margin

        p.fillRect(x - margin, y - margin, tw + margin * 2, th + margin * 2,
                   _ATTRIBUTION_BG)
        p.setPen(QColor(60, 60, 60))
        p.drawText(x, y + fm.ascent(), text)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _center_world_px(self) -> Tuple[float, float]:
        return lat_lon_to_world_px(self._center_lat, self._center_lon, self._zoom)

    def _set_center_from_world_px(self, wx: float, wy: float) -> None:
        from src.visualization.map_projection import world_px_to_lat_lon
        n = (2 ** self._zoom) * TILE_SIZE
        # Clamp to world bounds
        wx = max(0.0, min(n - 1, wx))
        wy = max(0.0, min(n - 1, wy))
        lat, lon = world_px_to_lat_lon(wx, wy, self._zoom)
        self._center_lat = lat
        self._center_lon = lon
        self.view_changed.emit(lat, lon, self._zoom)
