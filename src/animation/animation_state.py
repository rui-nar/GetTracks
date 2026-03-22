"""Pure-Python animation state — no Qt dependency.

AnimationState drives the playhead through an ordered list of AnimationSegments
(GPS activities and connecting great-circle arcs).  The dialog and export
pipeline both advance the same state object; the export worker uses a deep copy.
"""

from __future__ import annotations

import bisect
import copy
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from src.models.project import Project
    from src.models.track import Track

from src.models.great_circle import great_circle_points, haversine_km


# ---------------------------------------------------------------------------
# Color tables (mirrors map_widget.py — kept here to avoid Qt imports)
# ---------------------------------------------------------------------------

_SEGMENT_COLORS: Dict[str, Tuple[int, int, int]] = {
    "train":  (139, 69,  19),
    "flight": (21,  101, 192),
    "boat":   (0,   131, 143),
    "bus":    (106, 27,  154),
}
_TYPE_COLORS: Dict[str, Tuple[int, int, int]] = {
    "run":    (51,  136, 255),
    "ride":   (224, 48,  48),
    "hike":   (34,  139, 34),
    "walk":   (153, 50,  204),
    "swim":   (255, 140, 0),
}
_DEFAULT_COLOR: Tuple[int, int, int] = (102, 102, 102)

# Visual pacing speeds for connecting segments (km/h of *animation* time).
# These are intentionally lower than real-world speeds so connecting legs
# don't appear to rocket across the screen compared to GPS activities.
_SEGMENT_SPEED_KMH: Dict[str, float] = {
    "flight": 250.0,   # real ~850 → visually too fast; compress significantly
    "train":   40.0,   # real ~120 → bring close to typical bike/hike pace
    "boat":    15.0,   # real  ~30 → slightly slower than walk
    "bus":     35.0,   # real  ~80 → roughly jog-pace visually
}


# ---------------------------------------------------------------------------
# AnimationSegment
# ---------------------------------------------------------------------------

@dataclass
class AnimationSegment:
    """Immutable description of one animated leg of the journey."""
    icon_type: str                          # "ride", "flight", "train", …
    color: Tuple[int, int, int]             # RGB — no QColor here
    coords: List[Tuple[float, float]]       # [(lat, lon), …]
    cumulative_km: List[float]              # prefix-sum haversine, len == len(coords)
    total_km: float
    timestamps: Optional[List[datetime]]    # None → distance-based pacing
    duration_seconds: float
    activity_id: Optional[int]             # None for connecting segments
    segment_id: Optional[str]             # None for activities
    label: str
    # Pre-computed float timestamps (seconds since epoch) — avoids O(N) datetime
    # conversion inside _interpolate on every animation frame.
    _timestamps_float: Optional[List[float]] = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if self.timestamps is not None and self._timestamps_float is None:
            self._timestamps_float = [ts.timestamp() for ts in self.timestamps]


# ---------------------------------------------------------------------------
# AnimationState
# ---------------------------------------------------------------------------

class AnimationState:
    """Mutable playhead state.  Thread-unsafe — advance only from one thread."""

    def __init__(self, segments: List[AnimationSegment]) -> None:
        self.segments = segments
        self.total_duration_seconds: float = sum(s.duration_seconds for s in segments)
        self.speed_multiplier: float = 3600.0   # 1 real-hour → 1 anim-second
        self.paused: bool = True
        self.elapsed_seconds: float = 0.0

        # Derived — updated by _update_position()
        self.segment_index: int = 0
        self.intra_t: float = 0.0
        self.current_lat: float = segments[0].coords[0][0] if segments else 0.0
        self.current_lon: float = segments[0].coords[0][1] if segments else 0.0
        self.current_bearing_deg: float = 0.0
        self.current_distance_km: float = 0.0   # cumulative km along the route

        # Precompute cumulative end-times for O(log n) segment lookup
        self._seg_end_times: List[float] = []
        acc = 0.0
        for seg in segments:
            acc += seg.duration_seconds
            self._seg_end_times.append(acc)

        # Precompute cumulative start-km for each segment
        self._seg_start_km: List[float] = []
        acc_km = 0.0
        for seg in segments:
            self._seg_start_km.append(acc_km)
            acc_km += seg.total_km
        self._total_km: float = acc_km

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def build_from_project(
        cls,
        project: "Project",
        tracks: Dict[int, "Track"],
        excluded_ids: Optional[Set] = None,
        segment_speeds: Optional[Dict[str, float]] = None,
    ) -> Optional["AnimationState"]:
        """Build an AnimationState from a project's ordered items.

        Args:
            project: The open project.
            tracks: Full-resolution tracks keyed by activity_id.
            excluded_ids: Set of activity_id (int) or segment.id (str) to skip.

        Returns:
            AnimationState, or None if no animatable segments were found.
        """
        excluded = excluded_ids or set()
        segments: List[AnimationSegment] = []

        for item in project.items:
            if item.item_type == "activity" and item.activity_id is not None:
                if item.activity_id in excluded:
                    continue
                seg = _build_activity_segment(
                    item.activity_id, project, tracks
                )
                if seg is not None:
                    segments.append(seg)

            elif item.item_type == "segment" and item.segment is not None:
                cs = item.segment
                if cs.id in excluded:
                    continue
                seg = _build_connecting_segment(cs, segment_speeds)
                if seg is not None:
                    segments.append(seg)

        if not segments:
            return None
        return cls(segments)

    def copy(self) -> "AnimationState":
        """Return an independent deep copy suitable for the export worker."""
        return copy.deepcopy(self)

    # ------------------------------------------------------------------
    # Playback control
    # ------------------------------------------------------------------

    def advance(self, wall_delta_ms: float) -> None:
        """Advance the playhead by *wall_delta_ms* milliseconds of wall time."""
        if self.paused or not self.segments:
            return
        anim_delta = wall_delta_ms / 1000.0 * self.speed_multiplier
        self.elapsed_seconds = min(
            self.elapsed_seconds + anim_delta,
            self.total_duration_seconds,
        )
        self._update_position()

    def seek(self, fraction: float) -> None:
        """Jump to *fraction* ∈ [0, 1] of the total animation duration."""
        self.elapsed_seconds = max(0.0, min(1.0, fraction)) * self.total_duration_seconds
        self._update_position()

    @property
    def fraction(self) -> float:
        """Current playhead position as a fraction of total *time* [0, 1]."""
        if self.total_duration_seconds <= 0:
            return 0.0
        return self.elapsed_seconds / self.total_duration_seconds

    @property
    def distance_fraction(self) -> float:
        """Current playhead as a fraction of total *distance* [0, 1].

        Use this for the elevation strip (X axis = distance, not time).
        """
        if self._total_km <= 0:
            return 0.0
        return self.current_distance_km / self._total_km

    @property
    def is_finished(self) -> bool:
        return self.elapsed_seconds >= self.total_duration_seconds

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _update_position(self) -> None:
        """Recompute segment_index, intra_t, current_lat/lon/bearing."""
        if not self.segments:
            return
        # Binary search for current segment
        idx = bisect.bisect_left(self._seg_end_times, self.elapsed_seconds)
        idx = min(idx, len(self.segments) - 1)
        self.segment_index = idx

        seg = self.segments[idx]
        seg_start = self._seg_end_times[idx - 1] if idx > 0 else 0.0
        seg_elapsed = self.elapsed_seconds - seg_start
        self.intra_t = (
            min(1.0, seg_elapsed / seg.duration_seconds)
            if seg.duration_seconds > 0 else 1.0
        )

        lat, lon, bearing, dist_in_seg = _interpolate(seg, self.intra_t)
        self.current_lat = lat
        self.current_lon = lon
        self.current_bearing_deg = bearing
        self.current_distance_km = self._seg_start_km[idx] + dist_in_seg


# ---------------------------------------------------------------------------
# Segment builders
# ---------------------------------------------------------------------------

def _build_activity_segment(
    activity_id: int,
    project: "Project",
    tracks: Dict[int, "Track"],
) -> Optional[AnimationSegment]:
    activity = project.activity_by_id(activity_id)
    if activity is None:
        return None

    track = tracks.get(activity_id)
    if track and len(track.points) >= 2:
        coords = [(pt.lat, pt.lon) for pt in track.points]
        cumulative = _prefix_distances(coords)
        total_km = cumulative[-1]

        # Check if timestamps are present
        times: Optional[List[datetime]] = None
        if track.points[0].time is not None and track.points[-1].time is not None:
            raw = [pt.time for pt in track.points]
            # Ensure tz-aware
            times = [
                t.replace(tzinfo=timezone.utc) if t and t.tzinfo is None else t
                for t in raw
            ]
            # Duration from actual GPS timestamps
            duration = (times[-1] - times[0]).total_seconds()
            if duration <= 0:
                duration = float(activity.moving_time or 3600)
        else:
            duration = float(activity.moving_time or 3600)

    elif activity.start_latlng and activity.end_latlng:
        # No full-res track — use start/end great-circle arc
        start = activity.start_latlng
        end   = activity.end_latlng
        gc = great_circle_points(start[0], start[1], end[0], end[1], 50)
        coords = gc
        cumulative = _prefix_distances(coords)
        total_km = cumulative[-1]
        times = None
        duration = float(activity.moving_time or 3600)
    else:
        return None  # no GPS data at all

    icon_type = (activity.type or "run").lower()
    color = _TYPE_COLORS.get(icon_type, _DEFAULT_COLOR)
    label = activity.name or icon_type

    return AnimationSegment(
        icon_type=icon_type,
        color=color,
        coords=coords,
        cumulative_km=cumulative,
        total_km=total_km,
        timestamps=times,
        duration_seconds=duration,
        activity_id=activity_id,
        segment_id=None,
        label=label,
    )


def _build_connecting_segment(
    cs,
    speeds: Optional[Dict[str, float]] = None,
) -> Optional[AnimationSegment]:
    from src.models.project import ConnectingSegment
    if cs.start.lat == 0.0 and cs.start.lon == 0.0:
        return None

    gc = great_circle_points(
        cs.start.lat, cs.start.lon,
        cs.end.lat,   cs.end.lon,
        200,
    )
    cumulative = _prefix_distances(gc)
    total_km = cumulative[-1]
    effective_speeds = speeds if speeds is not None else _SEGMENT_SPEED_KMH
    speed_kmh = effective_speeds.get(cs.segment_type) or _SEGMENT_SPEED_KMH.get(cs.segment_type, 100.0)
    duration = (total_km / speed_kmh) * 3600.0 if speed_kmh > 0 else 3600.0

    color = _SEGMENT_COLORS.get(cs.segment_type, _DEFAULT_COLOR)
    label = cs.label or cs.segment_type

    return AnimationSegment(
        icon_type=cs.segment_type,
        color=color,
        coords=gc,
        cumulative_km=cumulative,
        total_km=total_km,
        timestamps=None,
        duration_seconds=duration,
        activity_id=None,
        segment_id=cs.id,
        label=label,
    )


# ---------------------------------------------------------------------------
# Interpolation helpers
# ---------------------------------------------------------------------------

def _interpolate(
    seg: AnimationSegment,
    t: float,
) -> Tuple[float, float, float, float]:
    """Return (lat, lon, bearing_deg, dist_km_within_seg) at fraction t ∈ [0, 1]."""
    coords = seg.coords
    if len(coords) < 2:
        lat, lon = coords[0]
        return lat, lon, 0.0, 0.0

    if seg.timestamps is not None:
        # Time-based interpolation — use pre-cached float list (O(1), not O(N))
        times_ts = seg._timestamps_float  # type: ignore[attr-defined]
        t0_f = times_ts[0]
        total_s = times_ts[-1] - t0_f
        target_dt = t0_f + t * total_s

        idx = bisect.bisect_left(times_ts, target_dt)
        idx = max(1, min(idx, len(times_ts) - 1))
        frac = _lerp_frac(times_ts[idx - 1], times_ts[idx], target_dt)
    else:
        # Distance-based interpolation
        target_km = t * seg.total_km
        idx = bisect.bisect_left(seg.cumulative_km, target_km)
        idx = max(1, min(idx, len(seg.cumulative_km) - 1))
        frac = _lerp_frac(seg.cumulative_km[idx - 1], seg.cumulative_km[idx], target_km)

    lat = coords[idx - 1][0] + frac * (coords[idx][0] - coords[idx - 1][0])
    lon = coords[idx - 1][1] + frac * (coords[idx][1] - coords[idx - 1][1])
    bearing = _bearing(coords[idx - 1][0], coords[idx - 1][1],
                       coords[idx][0],     coords[idx][1])
    dist_km = (seg.cumulative_km[idx - 1]
               + frac * (seg.cumulative_km[idx] - seg.cumulative_km[idx - 1]))
    return lat, lon, bearing, dist_km


def _lerp_frac(a: float, b: float, v: float) -> float:
    if b == a:
        return 0.0
    return max(0.0, min(1.0, (v - a) / (b - a)))


def _bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Forward azimuth from point 1 to point 2 in degrees [0, 360)."""
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlon = lon2 - lon1
    x = math.cos(lat2) * math.sin(dlon)
    y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
    return (math.degrees(math.atan2(x, y)) + 360) % 360


def _prefix_distances(coords: List[Tuple[float, float]]) -> List[float]:
    """Cumulative haversine distances in km, starting at 0."""
    result = [0.0]
    for i in range(1, len(coords)):
        d = haversine_km(*coords[i - 1], *coords[i])
        result.append(result[-1] + d)
    return result
