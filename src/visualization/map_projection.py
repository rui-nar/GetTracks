"""Web Mercator (EPSG:3857) projection math for slippy tile maps.

All functions are pure Python — no Qt imports — so they are fully testable
without a QApplication instance.
"""

import math
from typing import Tuple

TILE_SIZE: int = 256
MIN_ZOOM: int  = 0
MAX_ZOOM: int  = 19
MAX_LAT: float = 85.0511   # Web Mercator latitude limit


# ---------------------------------------------------------------------------
# Coordinate helpers
# ---------------------------------------------------------------------------

def clamp_lat(lat: float) -> float:
    """Clamp latitude to the Web Mercator valid range ±85.0511°."""
    return max(-MAX_LAT, min(MAX_LAT, lat))


def clamp_lon(lon: float) -> float:
    """Normalise longitude to [-180, 180).

    Both -180 and 180 represent the antimeridian; we keep -180 so that the
    world-pixel formula ``(lon + 180) / 360 * world_width`` produces 0 for
    the left edge rather than the full world width.
    """
    return (lon + 180.0) % 360.0 - 180.0


# ---------------------------------------------------------------------------
# World-pixel coordinates
# ---------------------------------------------------------------------------

def lat_lon_to_world_px(lat: float, lon: float, zoom: int) -> Tuple[float, float]:
    """Convert (lat, lon) to world-pixel coordinates at *zoom*.

    World-pixel (0,0) is the top-left of tile (0,0).  The world is
    ``2^zoom * TILE_SIZE`` pixels wide and tall.
    """
    lat = clamp_lat(lat)
    lon = clamp_lon(lon)

    n = (2 ** zoom) * TILE_SIZE
    wx = (lon + 180.0) / 360.0 * n

    lat_r = math.radians(lat)
    wy = (1.0 - math.log(math.tan(lat_r) + 1.0 / math.cos(lat_r)) / math.pi) / 2.0 * n

    return wx, wy


def world_px_to_lat_lon(wx: float, wy: float, zoom: int) -> Tuple[float, float]:
    """Inverse of :func:`lat_lon_to_world_px`."""
    n = (2 ** zoom) * TILE_SIZE
    lon = wx / n * 360.0 - 180.0
    lat = math.degrees(math.atan(math.sinh(math.pi * (1.0 - 2.0 * wy / n))))
    return lat, lon


# ---------------------------------------------------------------------------
# Tile coordinates
# ---------------------------------------------------------------------------

def lat_lon_to_tile(lat: float, lon: float, zoom: int) -> Tuple[int, int]:
    """Return the integer tile (tx, ty) containing (lat, lon) at *zoom*."""
    wx, wy = lat_lon_to_world_px(lat, lon, zoom)
    n = 2 ** zoom
    tx = max(0, min(n - 1, int(wx // TILE_SIZE)))
    ty = max(0, min(n - 1, int(wy // TILE_SIZE)))
    return tx, ty


def tile_to_world_px(tx: int, ty: int) -> Tuple[float, float]:
    """Return the world-pixel coordinate of the top-left corner of tile (tx, ty)."""
    return float(tx * TILE_SIZE), float(ty * TILE_SIZE)


# ---------------------------------------------------------------------------
# Screen-space conversion
# ---------------------------------------------------------------------------

def world_px_to_screen(
    wx: float, wy: float,
    center_wx: float, center_wy: float,
    viewport_w: int, viewport_h: int,
) -> Tuple[float, float]:
    """Convert world-pixel coords to screen-pixel coords given the viewport center."""
    sx = wx - center_wx + viewport_w / 2.0
    sy = wy - center_wy + viewport_h / 2.0
    return sx, sy


def screen_to_world_px(
    sx: float, sy: float,
    center_wx: float, center_wy: float,
    viewport_w: int, viewport_h: int,
) -> Tuple[float, float]:
    """Inverse of :func:`world_px_to_screen`."""
    wx = sx + center_wx - viewport_w / 2.0
    wy = sy + center_wy - viewport_h / 2.0
    return wx, wy


# ---------------------------------------------------------------------------
# fit_bounds
# ---------------------------------------------------------------------------

def fit_bounds_center(
    min_lat: float, max_lat: float,
    min_lon: float, max_lon: float,
) -> Tuple[float, float]:
    """Return the geographic centre of a bounding box.

    Handles the antimeridian case where ``max_lon - min_lon > 180``.
    """
    center_lat = (min_lat + max_lat) / 2.0

    if max_lon - min_lon > 180.0:
        # Bounds cross the antimeridian — shift into same hemisphere
        adj_min = min_lon if min_lon >= 0 else min_lon + 360.0
        adj_max = max_lon if max_lon >= 0 else max_lon + 360.0
        center_lon = ((adj_min + adj_max) / 2.0) % 360.0
        if center_lon > 180.0:
            center_lon -= 360.0
    else:
        center_lon = (min_lon + max_lon) / 2.0

    return center_lat, center_lon


def fit_bounds_zoom(
    min_lat: float, max_lat: float,
    min_lon: float, max_lon: float,
    viewport_w: int, viewport_h: int,
    padding: int = 40,
) -> int:
    """Return the highest zoom level where *bounds* fit in the viewport.

    Iterates from MAX_ZOOM downward and returns the first zoom where both
    horizontal and vertical extents fit within the padded viewport.
    """
    if viewport_w <= 0 or viewport_h <= 0:
        return 2

    crosses_antimeridian = (max_lon - min_lon) > 180.0

    for z in range(MAX_ZOOM, MIN_ZOOM - 1, -1):
        wx_min, wy_max = lat_lon_to_world_px(min_lat, min_lon, z)
        wx_max, wy_min = lat_lon_to_world_px(max_lat, max_lon, z)

        span_x = wx_max - wx_min
        if crosses_antimeridian:
            span_x += (2 ** z) * TILE_SIZE  # wrap-around span

        span_y = abs(wy_max - wy_min)

        if (span_x <= viewport_w - 2 * padding and
                span_y <= viewport_h - 2 * padding):
            return z

    return MIN_ZOOM
