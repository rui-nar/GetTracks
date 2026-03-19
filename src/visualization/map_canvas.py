"""Native Qt slippy-map canvas — replaces QWebEngineView + Folium.

Rendering layers (bottom to top):
  1. Tile grid  — fetched asynchronously, painted from cache
  2. Polylines  — GPS tracks
  3. Markers    — start-point circles
  4. Attribution — OSM copyright notice (required by usage policy)

Mouse/touch events:
  - 1-finger drag  → pan
  - 2-finger pinch → smooth fractional zoom centred on pinch midpoint
  - Scroll wheel   → zoom centred on cursor (trackpad / mouse wheel)
  - Double-click   → zoom in one level centred on click point

Fractional zoom: _zoom_f is a float; tiles are fetched at
int(_zoom_f) and drawn scaled by 2^(_zoom_f - int(_zoom_f)) so
transitions between integer levels are visually smooth.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from PyQt6.QtCore import Qt, QEvent, QLineF, QPoint, QPointF, pyqtSignal
from PyQt6.QtGui import (
    QColor, QFont, QPainter, QPen, QPixmap,
    QMouseEvent, QWheelEvent, QPaintEvent, QResizeEvent,
)
from PyQt6.QtWidgets import QWidget, QSizePolicy

from src.visualization.transport_icons import draw_transport_icon, draw_waypoint_icon
from src.visualization.map_projection import (
    MIN_ZOOM, MAX_ZOOM, TILE_SIZE,
    lat_lon_to_world_px, world_px_to_lat_lon, tile_to_world_px,
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
    dash_pattern: Optional[List[float]] = None   # e.g. [6.0, 6.0] for equal dash-gap


@dataclass
class Marker:
    lat: float
    lon: float
    color: QColor = field(default_factory=lambda: QColor("#3388ff"))
    radius: float = 6.0
    tooltip: str = ""
    icon: str = ""   # Unicode emoji — renders as a badge instead of a plain circle
    marker_type: str = "activity"   # "activity" | "waypoint"
    waypoint_id: Optional[int] = None


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PLACEHOLDER_COLOR = QColor(220, 220, 220)
_GRID_COLOR        = QColor(200, 200, 200)
_ATTRIBUTION_TEXT  = "© OpenStreetMap contributors"
_ATTRIBUTION_BG    = QColor(255, 255, 255, 180)


def _dist(p1: QPointF, p2: QPointF) -> float:
    return QLineF(p1, p2).length()


class MapCanvas(QWidget):
    """Pure-Qt interactive slippy-map canvas with fractional zoom."""

    view_changed      = pyqtSignal(float, float, int)   # lat, lon, zoom
    marker_clicked    = pyqtSignal(object)              # Marker
    waypoint_hovered  = pyqtSignal(object)              # Marker | None

    def __init__(
        self,
        mem_cache: Optional[MemoryTileCache] = None,
        disk_cache: Optional[DiskTileCache] = None,
        provider: str = "OpenStreetMap",
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setMinimumSize(200, 150)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)
        self.setAttribute(Qt.WidgetAttribute.WA_AcceptTouchEvents)
        self.setMouseTracking(True)

        # Fractional zoom — rendering uses this; tile fetching uses int(_zoom_f)
        self._zoom_f: float = 2.0
        self._center_lat: float = 20.0
        self._center_lon: float = 0.0

        # Overlays
        self._polylines: List[Polyline] = []
        self._markers:   List[Marker]   = []
        # Hit areas updated on each render: (screen_pos, Marker)
        self._marker_hit_areas: List[Tuple[QPointF, Marker]] = []
        self._hovered_waypoint: Optional[Marker] = None

        # Configurable sizes and colours (changed via Appearance dialog)
        self._circle_radius:    float = 6.0    # plain start/end dots
        self._transport_radius: float = 10.0   # transport icon badges
        self._waypoint_radius:  float = 10.0   # waypoint camera pins
        # Optional colour overrides (None = use per-marker colour)
        self._circle_color:    Optional["QColor"] = None
        self._transport_color: Optional["QColor"] = None
        self._waypoint_color:  Optional["QColor"] = None   # None → default amber

        # Tile pixmap cache  (tile_zoom, tx, ty) → QPixmap
        self._pixmap_cache: dict[Tuple[int, int, int], QPixmap] = {}
        self._prev_tile_zoom: int = self._tile_zoom

        # Network provider
        _mem = mem_cache or MemoryTileCache(max_size=512)
        self._provider = TileProvider(_mem, disk_cache, provider, parent=self)
        self._provider.tile_ready.connect(self._on_tile_ready)

        # Mouse pan
        self._drag_start: Optional[QPoint] = None
        self._drag_center_wx: float = 0.0
        self._drag_center_wy: float = 0.0

        # Touch state
        self._touch_pan_pos: Optional[QPointF] = None
        self._touch_count: int = 0
        # Pinch: stored in lat/lon so the anchor point survives tile_zoom changes
        self._pinch_anchor_lat: float = 0.0
        self._pinch_anchor_lon: float = 0.0
        self._pinch_anchor_sx:  float = 0.0   # screen position of anchor
        self._pinch_anchor_sy:  float = 0.0
        self._pinch_start_dist: float = 0.0
        self._pinch_start_zoom: float = 0.0

    # ------------------------------------------------------------------
    # Fractional zoom helpers
    # ------------------------------------------------------------------

    @property
    def _tile_zoom(self) -> int:
        """Integer zoom level used for tile fetching (floor of _zoom_f)."""
        return max(MIN_ZOOM, min(MAX_ZOOM, int(self._zoom_f)))

    @property
    def _scale(self) -> float:
        """Render scale factor: how many screen pixels per world pixel."""
        return 2.0 ** (self._zoom_f - self._tile_zoom)

    def _center_world_px(self) -> Tuple[float, float]:
        return lat_lon_to_world_px(self._center_lat, self._center_lon, self._tile_zoom)

    def _screen_to_world(self, sx: float, sy: float) -> Tuple[float, float]:
        """Screen px → world px at current tile_zoom, respecting fractional scale."""
        cx, cy = self._center_world_px()
        s = self._scale
        return (sx - self.width()  / 2.0) / s + cx, \
               (sy - self.height() / 2.0) / s + cy

    def _world_to_screen(self, wx: float, wy: float) -> Tuple[float, float]:
        """World px at tile_zoom → screen px."""
        cx, cy = self._center_world_px()
        s = self._scale
        return (wx - cx) * s + self.width()  / 2.0, \
               (wy - cy) * s + self.height() / 2.0

    def _screen_to_latlng(self, sx: float, sy: float) -> Tuple[float, float]:
        wx, wy = self._screen_to_world(sx, sy)
        return world_px_to_lat_lon(wx, wy, self._tile_zoom)

    def _set_center_keeping_anchor(
        self, anchor_lat: float, anchor_lon: float,
        anchor_sx: float, anchor_sy: float,
    ) -> None:
        """Adjust center so (anchor_lat, anchor_lon) stays at screen (anchor_sx, anchor_sy)."""
        tz = self._tile_zoom
        s  = self._scale
        W, H = self.width(), self.height()
        wx, wy = lat_lon_to_world_px(anchor_lat, anchor_lon, tz)
        new_cx = wx - (anchor_sx - W / 2.0) / s
        new_cy = wy - (anchor_sy - H / 2.0) / s
        self._set_center_from_world_px(new_cx, new_cy)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_view(self, lat: float, lon: float, zoom: int) -> None:
        self._zoom_f = float(max(MIN_ZOOM, min(MAX_ZOOM, zoom)))
        self._center_lat = lat
        self._center_lon = lon
        self._pixmap_cache.clear()
        self._prev_tile_zoom = self._tile_zoom
        self.update()
        self.view_changed.emit(lat, lon, self._tile_zoom)

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

    def set_circle_radius(self, r: float) -> None:
        self._circle_radius = max(1.0, r)
        self.update()

    def set_circle_color(self, c: Optional["QColor"]) -> None:
        self._circle_color = c
        self.update()

    def set_transport_radius(self, r: float) -> None:
        self._transport_radius = max(3.0, r)
        self.update()

    def set_transport_color(self, c: Optional["QColor"]) -> None:
        self._transport_color = c
        self.update()

    def set_waypoint_radius(self, r: float) -> None:
        self._waypoint_radius = max(3.0, r)
        self.update()

    def set_waypoint_color(self, c: Optional["QColor"]) -> None:
        self._waypoint_color = c
        self.update()

    # backwards-compat alias
    def set_icon_radius(self, r: float) -> None:
        self.set_transport_radius(r)

    def set_provider(self, provider: str) -> None:
        self._provider.set_provider(provider)
        self._pixmap_cache.clear()
        self.update()

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
    # Paint / resize
    # ------------------------------------------------------------------

    def paintEvent(self, _: QPaintEvent) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self._draw_tiles(p)
        self._draw_polylines(p)
        self._draw_markers(p)
        self._draw_attribution(p)

    def resizeEvent(self, _: QResizeEvent) -> None:  # noqa: N802
        self._pixmap_cache.clear()
        self.update()

    # ------------------------------------------------------------------
    # Touch events
    # ------------------------------------------------------------------

    def event(self, ev: QEvent) -> bool:  # noqa: N802
        t = ev.type()
        if t in (QEvent.Type.TouchBegin,
                 QEvent.Type.TouchUpdate,
                 QEvent.Type.TouchEnd,
                 QEvent.Type.TouchCancel):
            ev.accept()
            self._handle_touch(ev)
            return True
        return super().event(ev)

    def _handle_touch(self, ev: QEvent) -> None:
        pts = ev.points()
        n = len(pts)
        self._touch_count = n
        t = ev.type()

        # ---- Two-finger pinch: smooth fractional zoom -------------------
        if n >= 2:
            p0, p1 = pts[0], pts[1]
            cur0, cur1 = p0.position(), p1.position()
            mid = QPointF((cur0.x() + cur1.x()) / 2,
                          (cur0.y() + cur1.y()) / 2)
            current_dist = _dist(cur0, cur1)

            if t == QEvent.Type.TouchBegin or self._pinch_start_dist == 0.0:
                self._pinch_start_dist = max(current_dist, 1.0)
                self._pinch_start_zoom = self._zoom_f
                # Anchor = geographic point under pinch midpoint
                self._pinch_anchor_lat, self._pinch_anchor_lon = \
                    self._screen_to_latlng(mid.x(), mid.y())
                self._pinch_anchor_sx = mid.x()
                self._pinch_anchor_sy = mid.y()
                self._touch_pan_pos = None
                return

            if current_dist < 1.0:
                return

            # Continuous fractional zoom — no rounding → smooth visual
            scale = current_dist / self._pinch_start_dist
            new_zoom_f = self._pinch_start_zoom + math.log2(scale)
            new_zoom_f = max(float(MIN_ZOOM), min(float(MAX_ZOOM), new_zoom_f))

            old_tile_zoom = self._tile_zoom
            self._zoom_f = new_zoom_f
            if self._tile_zoom != old_tile_zoom:
                self._pixmap_cache.clear()
                self._prev_tile_zoom = self._tile_zoom

            # Keep the anchor point fixed on screen
            self._set_center_keeping_anchor(
                self._pinch_anchor_lat, self._pinch_anchor_lon,
                self._pinch_anchor_sx, self._pinch_anchor_sy,
            )
            self.update()

            if t in (QEvent.Type.TouchEnd, QEvent.Type.TouchCancel):
                self._pinch_start_dist = 0.0
            return

        # ---- One-finger pan --------------------------------------------
        if n == 1:
            self._pinch_start_dist = 0.0
            pos = pts[0].position()

            if t == QEvent.Type.TouchBegin or self._touch_pan_pos is None:
                self._touch_pan_pos = pos
                return

            if t in (QEvent.Type.TouchEnd, QEvent.Type.TouchCancel):
                self._touch_pan_pos = None
                return

            dx = pos.x() - self._touch_pan_pos.x()
            dy = pos.y() - self._touch_pan_pos.y()
            self._touch_pan_pos = pos
            s = self._scale
            cx, cy = self._center_world_px()
            self._set_center_from_world_px(cx - dx / s, cy - dy / s)
            self.update()

    # ------------------------------------------------------------------
    # Mouse events
    # ------------------------------------------------------------------

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._touch_count > 0:
            return
        if event.button() == Qt.MouseButton.LeftButton:
            click_pos = QPointF(event.pos())
            # Check for waypoint marker hit (20 px tolerance)
            for pos, marker in self._marker_hit_areas:
                if _dist(click_pos, pos) <= 20.0:
                    self.marker_clicked.emit(marker)
                    return
            self._drag_start = event.pos()
            cx, cy = self._center_world_px()
            self._drag_center_wx = cx
            self._drag_center_wy = cy
            self.setCursor(Qt.CursorShape.ClosedHandCursor)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        # Waypoint hover detection
        pos = QPointF(event.pos())
        hovered: Optional[Marker] = None
        for hit_pos, marker in self._marker_hit_areas:
            if _dist(pos, hit_pos) <= (self._waypoint_radius + 4.0):
                hovered = marker
                break
        if hovered is not self._hovered_waypoint:
            self._hovered_waypoint = hovered
            self.waypoint_hovered.emit(hovered)

        if self._touch_count > 0 or self._drag_start is None:
            return
        delta = event.pos() - self._drag_start
        s = self._scale
        self._set_center_from_world_px(
            self._drag_center_wx - delta.x() / s,
            self._drag_center_wy - delta.y() / s,
        )
        self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start = None
            self.setCursor(Qt.CursorShape.ArrowCursor)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._touch_count > 0:
            return
        if event.button() == Qt.MouseButton.LeftButton:
            sx, sy = float(event.pos().x()), float(event.pos().y())
            anchor_lat, anchor_lon = self._screen_to_latlng(sx, sy)
            old_tile_zoom = self._tile_zoom
            self._zoom_f = min(float(MAX_ZOOM), self._zoom_f + 1.0)
            if self._tile_zoom != old_tile_zoom:
                self._pixmap_cache.clear()
            self._set_center_keeping_anchor(anchor_lat, anchor_lon, sx, sy)
            self.update()

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802
        delta = event.angleDelta().y()
        if delta == 0:
            return
        sx, sy = event.position().x(), event.position().y()
        anchor_lat, anchor_lon = self._screen_to_latlng(sx, sy)

        old_tile_zoom = self._tile_zoom
        self._zoom_f = max(float(MIN_ZOOM), min(float(MAX_ZOOM),
                                                self._zoom_f + (1.0 if delta > 0 else -1.0)))
        if self._tile_zoom != old_tile_zoom:
            self._pixmap_cache.clear()

        self._set_center_keeping_anchor(anchor_lat, anchor_lon, sx, sy)
        self.update()
        self.view_changed.emit(self._center_lat, self._center_lon, self._tile_zoom)

    # ------------------------------------------------------------------
    # Tile slot
    # ------------------------------------------------------------------

    def _on_tile_ready(self, z: int, tx: int, ty: int, data: bytes) -> None:
        if z != self._tile_zoom:
            return
        pm = QPixmap()
        pm.loadFromData(data)
        if not pm.isNull():
            self._pixmap_cache[(z, tx, ty)] = pm
            self.update()

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------

    def _draw_tiles(self, p: QPainter) -> None:
        z = self._tile_zoom
        s = self._scale
        cx, cy = self._center_world_px()
        W, H = self.width(), self.height()

        # Tile screen size at fractional zoom
        tile_px = TILE_SIZE * s

        # Visible tile range in world-px space at tile_zoom
        half_w = W / (2.0 * s)
        half_h = H / (2.0 * s)
        tx_min = int((cx - half_w) / TILE_SIZE) - 1
        tx_max = int((cx + half_w) / TILE_SIZE) + 1
        ty_min = int((cy - half_h) / TILE_SIZE) - 1
        ty_max = int((cy + half_h) / TILE_SIZE) + 1

        n = 2 ** z
        tile_sz = int(math.ceil(tile_px)) + 1   # +1 closes sub-pixel gaps

        for tx in range(tx_min, tx_max + 1):
            for ty in range(ty_min, ty_max + 1):
                if ty < 0 or ty >= n:
                    continue
                tx_w = tx % n
                # Screen position of tile top-left
                sx = (tx * TILE_SIZE - cx) * s + W / 2.0
                sy = (ty * TILE_SIZE - cy) * s + H / 2.0

                key = (z, tx_w, ty)
                if key in self._pixmap_cache:
                    p.drawPixmap(int(sx), int(sy), tile_sz, tile_sz,
                                 self._pixmap_cache[key])
                else:
                    p.fillRect(int(sx), int(sy), tile_sz, tile_sz, _PLACEHOLDER_COLOR)
                    p.setPen(_GRID_COLOR)
                    p.drawRect(int(sx), int(sy), tile_sz, tile_sz)
                    self._provider.request_tile(z, tx_w, ty)

    def _draw_polylines(self, p: QPainter) -> None:
        if not self._polylines:
            return
        z  = self._tile_zoom
        s  = self._scale
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
            if poly.dash_pattern:
                pen.setStyle(Qt.PenStyle.CustomDashLine)
                pen.setDashPattern(poly.dash_pattern)
            p.setPen(pen)

            pts = []
            for lat, lon in poly.coords:
                wx, wy = lat_lon_to_world_px(lat, lon, z)
                sx = (wx - cx) * s + W / 2.0
                sy = (wy - cy) * s + H / 2.0
                pts.append(QPointF(sx, sy))

            for i in range(len(pts) - 1):
                p.drawLine(pts[i], pts[i + 1])

    def _draw_markers(self, p: QPainter) -> None:
        if not self._markers:
            return
        z  = self._tile_zoom
        s  = self._scale
        cx, cy = self._center_world_px()
        W, H = self.width(), self.height()

        hit_areas: List[Tuple[QPointF, Marker]] = []

        for m in self._markers:
            wx, wy = lat_lon_to_world_px(m.lat, m.lon, z)
            sx = (wx - cx) * s + W / 2.0
            sy = (wy - cy) * s + H / 2.0
            screen_pos = QPointF(sx, sy)

            if m.marker_type == "waypoint":
                badge_r = self._waypoint_radius + 2.0
                wp_color = self._waypoint_color or QColor("#FF8F00")
                p.setBrush(QColor("white"))
                p.setPen(QPen(wp_color, 2.5))
                p.drawEllipse(screen_pos, badge_r, badge_r)
                draw_waypoint_icon(p, sx, sy, badge_r * 1.55, wp_color)
                hit_areas.append((screen_pos, m))
            elif m.icon:
                badge_r = self._transport_radius
                icon_color = self._transport_color or m.color
                p.setBrush(QColor("white"))
                p.setPen(QPen(icon_color, 2.5))
                p.drawEllipse(screen_pos, badge_r, badge_r)
                draw_transport_icon(p, sx, sy, badge_r * 1.55, m.icon, icon_color)
            else:
                r = self._circle_radius
                dot_color = self._circle_color or m.color
                p.setBrush(dot_color)
                p.setPen(QPen(dot_color.lighter(150), 1))
                p.drawEllipse(screen_pos, r, r)

        self._marker_hit_areas = hit_areas
        p.setBrush(Qt.BrushStyle.NoBrush)

    def _draw_attribution(self, p: QPainter) -> None:
        font = QFont("Arial", 9)
        p.setFont(font)
        fm = p.fontMetrics()
        tw = fm.horizontalAdvance(_ATTRIBUTION_TEXT)
        th = fm.height()
        margin = 4
        x = self.width()  - tw - margin * 2
        y = self.height() - th - margin

        p.fillRect(x - margin, y - margin, tw + margin * 2, th + margin * 2,
                   _ATTRIBUTION_BG)
        p.setPen(QColor(60, 60, 60))
        p.drawText(x, y + fm.ascent(), _ATTRIBUTION_TEXT)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _set_center_from_world_px(self, wx: float, wy: float) -> None:
        n = (2 ** self._tile_zoom) * TILE_SIZE
        wx = max(0.0, min(n - 1.0, wx))
        wy = max(0.0, min(n - 1.0, wy))
        lat, lon = world_px_to_lat_lon(wx, wy, self._tile_zoom)
        self._center_lat = lat
        self._center_lon = lon
        self.view_changed.emit(lat, lon, self._tile_zoom)
