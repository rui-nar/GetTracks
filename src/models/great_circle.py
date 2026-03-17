"""Great-circle path computation using SLERP on unit ECEF vectors."""

from __future__ import annotations

import math
from typing import List, Tuple


def great_circle_points(
    lat1_deg: float,
    lon1_deg: float,
    lat2_deg: float,
    lon2_deg: float,
    n_points: int = 50,
) -> List[Tuple[float, float]]:
    """Return *n_points* (lat, lon) tuples along the great-circle arc.

    Algorithm: SLERP (spherical linear interpolation) on unit ECEF vectors.

    1. Convert both endpoints to unit 3-vectors.
    2. Compute angular separation Ω = arccos(v1 · v2).
    3. For t ∈ [0, 1]: v(t) = (sin((1-t)Ω)·v1 + sin(t·Ω)·v2) / sin(Ω)
    4. Convert each v(t) back to (lat, lon).

    Edge cases:
    - Coincident points (Ω ≈ 0): returns [start, end] (2-point degenerate arc).
    - Antipodal points (Ω ≈ π): great circle is not unique; returns [start, end].
    """
    if n_points < 2:
        raise ValueError("n_points must be >= 2")

    def to_ecef(lat_d: float, lon_d: float) -> Tuple[float, float, float]:
        lat = math.radians(lat_d)
        lon = math.radians(lon_d)
        return (
            math.cos(lat) * math.cos(lon),
            math.cos(lat) * math.sin(lon),
            math.sin(lat),
        )

    def to_latlng(x: float, y: float, z: float) -> Tuple[float, float]:
        lat = math.degrees(math.asin(max(-1.0, min(1.0, z))))
        lon = math.degrees(math.atan2(y, x))
        return lat, lon

    v1 = to_ecef(lat1_deg, lon1_deg)
    v2 = to_ecef(lat2_deg, lon2_deg)

    dot = sum(a * b for a, b in zip(v1, v2))
    dot = max(-1.0, min(1.0, dot))
    omega = math.acos(dot)

    # Degenerate cases — return straight two-point "arc"
    if omega < 1e-10 or abs(omega - math.pi) < 1e-10:
        return [(lat1_deg, lon1_deg), (lat2_deg, lon2_deg)]

    sin_omega = math.sin(omega)
    points: List[Tuple[float, float]] = []
    for i in range(n_points):
        t = i / (n_points - 1)
        k1 = math.sin((1.0 - t) * omega) / sin_omega
        k2 = math.sin(t * omega) / sin_omega
        x = k1 * v1[0] + k2 * v2[0]
        y = k1 * v1[1] + k2 * v2[1]
        z = k1 * v1[2] + k2 * v2[2]
        points.append(to_latlng(x, y, z))
    return points


def haversine_km(
    lat1_deg: float,
    lon1_deg: float,
    lat2_deg: float,
    lon2_deg: float,
) -> float:
    """Great-circle distance in kilometres (Haversine formula)."""
    R = 6371.0
    phi1 = math.radians(lat1_deg)
    phi2 = math.radians(lat2_deg)
    dphi = math.radians(lat2_deg - lat1_deg)
    dlam = math.radians(lon2_deg - lon1_deg)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return 2.0 * R * math.asin(math.sqrt(a))
