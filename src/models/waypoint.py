"""Waypoint data model — Polarsteps trip steps stored in a project."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional


@dataclass
class StepPhoto:
    """A single photo attached to a Polarsteps step."""
    url: str                          # Full-resolution CDN URL
    thumb_url: str = ""               # small_thumbnail_path
    caption: str = ""
    lat: Optional[float] = None
    lon: Optional[float] = None

    def to_dict(self) -> dict:
        return {
            "url": self.url,
            "thumb_url": self.thumb_url,
            "caption": self.caption,
            "lat": self.lat,
            "lon": self.lon,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "StepPhoto":
        return cls(
            url=d.get("url", ""),
            thumb_url=d.get("thumb_url", ""),
            caption=d.get("caption", ""),
            lat=d.get("lat"),
            lon=d.get("lon"),
        )


@dataclass
class TripStep:
    """One Polarsteps step (GPS waypoint with text and photos)."""
    id: int                           # Polarsteps step ID — stable, used for dedup
    trip_id: int
    trip_name: str
    name: str                         # Location name e.g. "Chamonix"
    description: str                  # Narrative text
    lat: float
    lon: float
    date: datetime
    photos: List[StepPhoto] = field(default_factory=list)
    source: str = "polarsteps"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "trip_id": self.trip_id,
            "trip_name": self.trip_name,
            "name": self.name,
            "description": self.description,
            "lat": self.lat,
            "lon": self.lon,
            "date": self.date.isoformat(),
            "photos": [p.to_dict() for p in self.photos],
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "TripStep":
        raw_date = d.get("date", "")
        try:
            date = datetime.fromisoformat(raw_date)
        except (ValueError, TypeError):
            date = datetime.now(tz=timezone.utc)

        return cls(
            id=d.get("id", 0),
            trip_id=d.get("trip_id", 0),
            trip_name=d.get("trip_name", ""),
            name=d.get("name", ""),
            description=d.get("description", ""),
            lat=d.get("lat", 0.0),
            lon=d.get("lon", 0.0),
            date=date,
            photos=[StepPhoto.from_dict(p) for p in d.get("photos", [])],
            source=d.get("source", "polarsteps"),
        )
