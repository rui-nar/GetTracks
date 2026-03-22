"""AnimationCanvas — MapCanvas subclass with animated overlay layers.

Performance strategy
--------------------
``lat_lon_to_world_px`` involves trig (log/tan/cos) and is expensive when
called thousands of times per frame.  We separate the work into two phases:

Phase 1 — world-space pre-computation (once per zoom level):
    For every polyline point compute ``(wx, wy) = lat_lon_to_world_px(lat, lon, z)``
    and store the result.  This is triggered only when the tile zoom changes.

Phase 2 — screen-space transform (every frame, O(N) arithmetic only):
    ``sx = (wx - cx) * s + W / 2``
    ``sy = (wy - cy) * s + H / 2``
    No trig involved.

The future trail has been removed from the overlay.  The background route
polylines (drawn at 50 % opacity) already make the full route visible; the
18 %-opacity trail on top added negligible value but cost O(N×trig) per frame.
"""

from __future__ import annotations

import math
from typing import List, Optional, Tuple

import numpy as np
from PyQt6.QtCore import Qt, QPointF, QRectF, QSize
from PyQt6.QtGui import QColor, QImage, QPainter, QPen, QPolygonF

from src.visualization.map_canvas import MapCanvas, Polyline
from src.visualization.map_projection import lat_lon_to_world_px, TILE_SIZE
from src.visualization.transport_icons import draw_transport_icon, draw_activity_icon
from src.animation.animation_state import AnimationState, AnimationSegment


_ICON_SIZE = 36.0   # pixels for the moving icon


class AnimationCanvas(MapCanvas):
    """MapCanvas with animated overlay."""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._anim_state: Optional[AnimationState] = None
        self._camera_mode: str = "follow"    # "follow" | "overview"
        self._follow_zoom: int = 12

        # World-space coord cache for polylines.
        # _wc[i] = numpy array of shape (N, 2) — columns are (wx, wy).
        # Recomputed only when the tile zoom level changes (rare).
        self._wc: List[np.ndarray] = []
        self._wc_zoom: int = -1

        # Opaque paint: we fill every pixel, skip the implicit background clear.
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_animation_state(self, state: Optional[AnimationState]) -> None:
        self._anim_state = state
        self.update()

    def set_camera_mode(self, mode: str) -> None:
        """mode: "follow" or "overview"."""
        self._camera_mode = mode

    def follow_current_position(self) -> None:
        """Pan the map to keep the moving icon centred (Follow mode).

        Does NOT call set_view() — that clears the tile cache every call,
        which is catastrophic at 30 fps.
        """
        if self._anim_state is None:
            return
        self._center_lat = self._anim_state.current_lat
        self._center_lon = self._anim_state.current_lon
        self._zoom_f = float(self._follow_zoom)
        self.update()

    # Invalidate world-coord cache when polylines change.
    def add_polyline(self, polyline: Polyline) -> None:
        super().add_polyline(polyline)
        self._wc_zoom = -1

    def clear_overlays(self) -> None:
        super().clear_overlays()
        self._wc_zoom = -1

    def get_canvas_config(self) -> dict:
        return {
            "zoom_f":       self._zoom_f,
            "center_lat":   self._center_lat,
            "center_lon":   self._center_lon,
            "tile_zoom":    self._tile_zoom,
            "scale":        self._scale,
            "polylines":    list(self._polylines),
            "pixmap_cache": dict(self._pixmap_cache),
        }

    # ------------------------------------------------------------------
    # Paint
    # ------------------------------------------------------------------

    def paintEvent(self, event) -> None:  # noqa: N802
        W, H = self.width(), self.height()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        if self._anim_state is not None:
            # ── Animation fast path ────────────────────────────────────
            # 1. Tiles — O(K) pixmap blits from the in-memory tile cache.
            #    No world-coord math; tiles are already cached QPixmaps.
            self._draw_tiles(p)

            # 2. Route polylines — O(N) arithmetic only (trig pre-computed).
            self._draw_polylines_fast(p, W, H)

            # 3. Attribution overlay
            self._draw_attribution(p)

            # 4. Moving icon (trivial)
            self._draw_animation_overlay(p, W, H)
        else:
            # ── Static view — normal full render ──────────────────────
            self._draw_tiles(p)
            self._draw_polylines(p)
            self._draw_markers(p)
            self._draw_attribution(p)

        p.end()

    # ------------------------------------------------------------------
    # Fast polyline rendering (animation only)
    # ------------------------------------------------------------------

    def _ensure_wc(self) -> None:
        """Pre-compute world-space (wx, wy) for every polyline point.

        Stored as numpy float64 arrays of shape (N, 2) so the per-frame
        screen transform can be done with vectorised numpy arithmetic.
        Only runs when the tile zoom changes — typically never during a
        single animation session.
        """
        z = self._tile_zoom
        if self._wc_zoom == z:
            return
        self._wc = [
            np.array(
                [lat_lon_to_world_px(lat, lon, z) for lat, lon in poly.coords],
                dtype=np.float64,
            )
            for poly in self._polylines
        ]
        self._wc_zoom = z

    def _draw_polylines_fast(self, p: QPainter, W: int, H: int) -> None:
        """Draw polylines — vectorised numpy screen transform, zero QPointF allocation."""
        if not self._polylines:
            return
        self._ensure_wc()
        s  = self._scale
        cx, cy = lat_lon_to_world_px(self._center_lat, self._center_lon, self._tile_zoom)
        hw, hh = W / 2.0, H / 2.0

        for poly, wc in zip(self._polylines, self._wc):
            if wc.shape[0] < 2:
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

            # Vectorised screen transform — one numpy C-kernel call, no Python loop.
            sx = (wc[:, 0] - cx) * s + hw
            sy = (wc[:, 1] - cy) * s + hh

            # Vectorised 1-pixel decimation — keep points that differ by ≥1px
            # from their predecessor.  Always keep first and last so the line
            # draws correctly even when the entire route is compressed to <1px
            # per segment (e.g. low zoom in overview mode).
            keep = np.empty(len(sx), dtype=bool)
            keep[0]  = True
            keep[-1] = True
            if len(sx) > 2:
                # keep[i] = True if point i differs ≥1px from point i-1
                keep[1:-1] = (
                    (np.abs(sx[1:-1] - sx[:-2]) >= 1.0) |
                    (np.abs(sy[1:-1] - sy[:-2]) >= 1.0)
                )
            xs = sx[keep]
            ys = sy[keep]
            if len(xs) < 2:
                continue

            p.drawPolyline(QPolygonF([QPointF(x, y) for x, y in zip(xs.tolist(), ys.tolist())]))

    # ------------------------------------------------------------------
    # Off-screen render (called on main thread for export)
    # ------------------------------------------------------------------

    def render_to_image(self, size: QSize, state: AnimationState) -> QImage:
        """Render a single animation frame into a QImage (main thread only)."""
        W, H = size.width(), size.height()
        img = QImage(W, H, QImage.Format.Format_RGB32)
        img.fill(QColor("#f8f8f8"))

        p = QPainter(img)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        z  = self._tile_zoom
        s  = self._scale
        cx, cy = lat_lon_to_world_px(self._center_lat, self._center_lon, z)

        self._draw_tiles_to(p, W, H, z, s, cx, cy)
        self._draw_polylines_to(p, W, H, z, s, cx, cy, self._polylines)

        old_state = self._anim_state
        self._anim_state = state
        self._draw_animation_overlay(p, W, H, z=z, s=s, cx=cx, cy=cy)
        self._anim_state = old_state

        p.end()
        return img

    # ------------------------------------------------------------------
    # Overlay — icon only (no future trail)
    # ------------------------------------------------------------------

    def _draw_animation_overlay(
        self,
        p: QPainter,
        W: Optional[int] = None,
        H: Optional[int] = None,
        *,
        z: Optional[int] = None,
        s: Optional[float] = None,
        cx: Optional[float] = None,
        cy: Optional[float] = None,
    ) -> None:
        state = self._anim_state
        if state is None or not state.segments:
            return

        if W is None: W = self.width()
        if H is None: H = self.height()
        if z is None: z = self._tile_zoom
        if s is None: s = self._scale
        if cx is None or cy is None:
            cx, cy = lat_lon_to_world_px(self._center_lat, self._center_lon, z)

        si  = state.segment_index
        seg = state.segments[si]

        # Icon position
        wx, wy = lat_lon_to_world_px(state.current_lat, state.current_lon, z)
        sx = (wx - cx) * s + W / 2.0
        sy = (wy - cy) * s + H / 2.0

        icon_color = QColor(*seg.color)

        p.save()
        halo_r = _ICON_SIZE * 0.65
        p.setBrush(QColor(255, 255, 255, 200))
        p.setPen(QPen(icon_color, 2.5))
        p.drawEllipse(int(sx - halo_r), int(sy - halo_r),
                      int(halo_r * 2), int(halo_r * 2))
        p.translate(sx, sy)
        _draw_icon(p, seg.icon_type, _ICON_SIZE, icon_color)
        p.restore()

    # ------------------------------------------------------------------
    # Parameterised helpers for export
    # ------------------------------------------------------------------

    def _draw_tiles_to(
        self, p: QPainter, W: int, H: int,
        z: int, s: float, cx: float, cy: float,
    ) -> None:
        tile_px = TILE_SIZE * s
        half_w  = W / (2.0 * s)
        half_h  = H / (2.0 * s)
        tx_min = int((cx - half_w) / TILE_SIZE) - 1
        tx_max = int((cx + half_w) / TILE_SIZE) + 1
        ty_min = int((cy - half_h) / TILE_SIZE) - 1
        ty_max = int((cy + half_h) / TILE_SIZE) + 1
        n = 2 ** z
        tile_sz = int(math.ceil(tile_px)) + 1

        from PyQt6.QtGui import QPixmap as _QP
        from src.visualization.map_canvas import _PLACEHOLDER_COLOR, _GRID_COLOR
        for tx in range(tx_min, tx_max + 1):
            for ty in range(ty_min, ty_max + 1):
                if ty < 0 or ty >= n:
                    continue
                tx_w = tx % n
                _sx = (tx * TILE_SIZE - cx) * s + W / 2.0
                _sy = (ty * TILE_SIZE - cy) * s + H / 2.0
                key = (z, tx_w, ty)
                if key in self._pixmap_cache:
                    p.drawPixmap(int(_sx), int(_sy), tile_sz, tile_sz,
                                 self._pixmap_cache[key])
                else:
                    p.fillRect(int(_sx), int(_sy), tile_sz, tile_sz, _PLACEHOLDER_COLOR)
                    p.setPen(_GRID_COLOR)
                    p.drawRect(int(_sx), int(_sy), tile_sz, tile_sz)

    def _draw_polylines_to(
        self, p: QPainter, W: int, H: int,
        z: int, s: float, cx: float, cy: float,
        polylines,
    ) -> None:
        hw, hh = W / 2.0, H / 2.0
        for poly in polylines:
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
            pts = QPolygonF([
                QPointF((wx - cx) * s + hw, (wy - cy) * s + hh)
                for lat, lon in poly.coords
                for wx, wy in (lat_lon_to_world_px(lat, lon, z),)
            ])
            p.drawPolyline(pts)

    @staticmethod
    def _center_world_px_for(lat: float, lon: float, z: int) -> Tuple[float, float]:
        return lat_lon_to_world_px(lat, lon, z)


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def _draw_icon(p: QPainter, icon_type: str, size: float, color: QColor) -> None:
    """Draw the appropriate icon centred at the painter origin."""
    half = size / 2.0
    rect = QRectF(-half, -half, size, size)

    from src.visualization.transport_icons import _TRANSPORT_DRAW, _ACTIVITY_DRAW
    if icon_type in _TRANSPORT_DRAW:
        _TRANSPORT_DRAW[icon_type](p, rect, color)
    elif icon_type in _ACTIVITY_DRAW:
        _ACTIVITY_DRAW[icon_type](p, rect, color)
    else:
        p.setBrush(color)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(rect)
