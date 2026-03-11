"""Track and TrackPoint models for full-resolution GPS data."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional


@dataclass
class TrackPoint:
    """A single GPS point with optional elevation and timestamp."""

    lat: float
    lon: float
    elevation: Optional[float] = None
    time: Optional[datetime] = None     # absolute UTC datetime


@dataclass
class Track:
    """Full-resolution GPS track built from Strava activity streams."""

    activity_id: int
    activity_name: str
    start_time: datetime               # UTC — used for chronological sort
    points: List[TrackPoint] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.points)

    def is_empty(self) -> bool:
        return len(self.points) == 0
