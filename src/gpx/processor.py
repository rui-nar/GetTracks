"""GPX processing: merge tracks and export to GPX format."""

from datetime import timezone
from typing import List

import gpxpy
import gpxpy.gpx

from src.models.track import Track


class GPXProcessor:
    """Merges Track objects and exports them as a GPX document."""

    @staticmethod
    def merge(tracks: List[Track]) -> gpxpy.gpx.GPX:
        """Combine tracks into one GPX document, sorted chronologically.

        Each source activity becomes its own GPXTrack (segment) so that
        origin metadata is preserved and viewers can distinguish routes.
        """
        gpx = gpxpy.gpx.GPX()
        gpx.creator = "GetTracks"

        for track in sorted(tracks, key=lambda t: t.start_time):
            gpx_track = gpxpy.gpx.GPXTrack(name=track.activity_name)
            segment = gpxpy.gpx.GPXTrackSegment()

            for pt in track.points:
                # gpxpy expects timezone-aware datetimes for correct XML output
                time = pt.time
                if time is not None and time.tzinfo is None:
                    time = time.replace(tzinfo=timezone.utc)

                segment.points.append(
                    gpxpy.gpx.GPXTrackPoint(
                        latitude=pt.lat,
                        longitude=pt.lon,
                        elevation=pt.elevation,
                        time=time,
                    )
                )

            gpx_track.segments.append(segment)
            gpx.tracks.append(gpx_track)

        return gpx

    @staticmethod
    def save(gpx: gpxpy.gpx.GPX, path: str) -> None:
        """Write GPX document to *path* as indented XML."""
        with open(path, "w", encoding="utf-8") as f:
            f.write(gpx.to_xml())

    @staticmethod
    def validate(gpx: gpxpy.gpx.GPX) -> List[str]:
        """Return a list of warning strings; empty list means the file is valid.

        Checks:
        - At least one track
        - Each track has at least 2 points
        - No duplicate timestamps within a track segment
        """
        warnings: List[str] = []

        if not gpx.tracks:
            warnings.append("GPX contains no tracks.")
            return warnings

        for track in gpx.tracks:
            name = track.name or "(unnamed)"
            total_points = sum(len(seg.points) for seg in track.segments)

            if total_points < 2:
                warnings.append(
                    f"Track '{name}' has fewer than 2 points ({total_points})."
                )

            for seg in track.segments:
                times = [p.time for p in seg.points if p.time is not None]
                if len(times) != len(set(times)):
                    warnings.append(
                        f"Track '{name}' contains duplicate timestamps."
                    )
                    break

        return warnings
