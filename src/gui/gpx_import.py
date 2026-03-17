"""Import GPX files as synthetic Activity objects.

Each GPX <trk> element becomes one Activity with a stable negative ID
derived from the file path and track index so re-importing the same file
produces the same IDs and project.add_activities() deduplicates correctly.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from pathlib import Path
from typing import List

import gpxpy
import polyline as polyline_codec

from src.models.activity import Activity


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6_371_000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2.0 * R * math.asin(math.sqrt(a))


def import_gpx_file(path: str) -> List[Activity]:
    """Parse *path* and return one synthetic :class:`Activity` per GPX track.

    Returns an empty list (never raises) if the file cannot be parsed.
    Negative IDs are stable across imports of the same file so that
    :meth:`Project.add_activities` deduplicates correctly.
    """
    try:
        with open(path, encoding="utf-8") as fh:
            gpx = gpxpy.parse(fh)
    except Exception:
        return []

    stem = Path(path).stem
    activities: List[Activity] = []

    for idx, track in enumerate(gpx.tracks):
        # Collect all points across all segments
        points = [pt for seg in track.segments for pt in seg.points]
        if not points:
            continue

        name = track.name or stem
        # Stable negative ID: hash of (path, track index)
        synthetic_id = -(abs(hash(f"{path}:{idx}")) % (10 ** 15))

        # Coordinates for polyline encoding
        coords = [(pt.latitude, pt.longitude) for pt in points]
        encoded = polyline_codec.encode(coords)

        # Distance (sum of consecutive haversine distances)
        distance_m = 0.0
        for i in range(1, len(coords)):
            distance_m += _haversine_m(
                coords[i - 1][0], coords[i - 1][1],
                coords[i][0],     coords[i][1],
            )

        # Timestamps
        first_time = points[0].time
        last_time  = points[-1].time
        now_utc = datetime.now(tz=timezone.utc)

        if first_time is not None:
            if first_time.tzinfo is None:
                first_time = first_time.replace(tzinfo=timezone.utc)
            start_date = start_date_local = first_time
        else:
            start_date = start_date_local = now_utc

        moving_time = elapsed_time = 0
        if first_time is not None and last_time is not None:
            if last_time.tzinfo is None:
                last_time = last_time.replace(tzinfo=timezone.utc)
            elapsed_time = moving_time = int((last_time - first_time).total_seconds())

        # Elevation gain
        elev_gain = 0.0
        elevations = [pt.elevation for pt in points if pt.elevation is not None]
        for i in range(1, len(elevations)):
            diff = elevations[i] - elevations[i - 1]
            if diff > 0:
                elev_gain += diff

        start_latlng = [coords[0][0], coords[0][1]]
        end_latlng   = [coords[-1][0], coords[-1][1]]

        activities.append(Activity(
            id=synthetic_id,
            name=name,
            type="Run",
            distance=distance_m,
            moving_time=moving_time,
            elapsed_time=elapsed_time,
            total_elevation_gain=elev_gain,
            start_date=start_date,
            start_date_local=start_date_local,
            timezone="UTC",
            achievement_count=0,
            kudos_count=0,
            comment_count=0,
            athlete_count=1,
            photo_count=0,
            trainer=False,
            commute=False,
            manual=True,
            private=False,
            flagged=False,
            average_speed=distance_m / moving_time if moving_time > 0 else 0.0,
            max_speed=0.0,
            has_heartrate=False,
            pr_count=0,
            total_photo_count=0,
            has_kudoed=False,
            start_latlng=start_latlng,
            end_latlng=end_latlng,
            summary_polyline=encoded,
        ))

    return activities
