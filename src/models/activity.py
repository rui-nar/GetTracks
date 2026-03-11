"""Activity data model for Strava activities."""

from dataclasses import dataclass
from typing import List, Optional
from datetime import datetime


@dataclass
class Activity:
    """Represents a Strava activity with metadata."""

    # All required fields (no defaults) must come first
    id: Optional[int]
    name: str
    type: str
    distance: float  # meters
    moving_time: int  # seconds
    elapsed_time: int  # seconds
    total_elevation_gain: float  # meters
    start_date: datetime
    start_date_local: datetime
    timezone: str
    achievement_count: int
    kudos_count: int
    comment_count: int
    athlete_count: int
    photo_count: int
    trainer: bool
    commute: bool
    manual: bool
    private: bool
    flagged: bool
    average_speed: float  # m/s
    max_speed: float  # m/s
    has_heartrate: bool
    pr_count: int
    total_photo_count: int
    has_kudoed: bool
    
    # Optional fields with defaults (must come last)
    gear_id: Optional[str] = None
    average_heartrate: Optional[float] = None
    max_heartrate: Optional[int] = None
    heartrate_opt_out: bool = False
    display_hide_heartrate_option: bool = False
    elev_high: Optional[float] = None
    elev_low: Optional[float] = None
    start_latlng: Optional[List[float]] = None  # [lat, lng]
    end_latlng: Optional[List[float]] = None    # [lat, lng]
    summary_polyline: Optional[str] = None       # Google-encoded polyline

    def __str__(self) -> str:
        """Return string representation of activity."""
        distance_km = self.distance / 1000
        return f"{self.name} ({self.type}) - {distance_km:.1f} km"

    def __repr__(self) -> str:
        """Return detailed string representation."""
        return f"Activity(id={self.id}, name='{self.name}', type='{self.type}')"

    @classmethod
    def from_strava_api(cls, data: dict) -> "Activity":
        """Create an Activity instance from Strava API response data."""
        return cls(
            id=data.get("id"),
            name=data.get("name", ""),
            type=data.get("type", ""),
            distance=data.get("distance", 0.0),
            moving_time=data.get("moving_time", 0),
            elapsed_time=data.get("elapsed_time", 0),
            total_elevation_gain=data.get("total_elevation_gain", 0.0),
            start_date=datetime.fromisoformat(data.get("start_date", "").replace("Z", "+00:00")) if data.get("start_date") else datetime.now(),
            start_date_local=datetime.fromisoformat(data.get("start_date_local", "").replace("Z", "+00:00")) if data.get("start_date_local") else datetime.now(),
            timezone=data.get("timezone", "UTC"),
            achievement_count=data.get("achievement_count", 0),
            kudos_count=data.get("kudos_count", 0),
            comment_count=data.get("comment_count", 0),
            athlete_count=data.get("athlete_count", 0),
            photo_count=data.get("photo_count", 0),
            trainer=data.get("trainer", False),
            commute=data.get("commute", False),
            manual=data.get("manual", False),
            private=data.get("private", False),
            flagged=data.get("flagged", False),
            average_speed=data.get("average_speed", 0.0),
            max_speed=data.get("max_speed", 0.0),
            has_heartrate=data.get("has_heartrate", False),
            pr_count=data.get("pr_count", 0),
            total_photo_count=data.get("total_photo_count", 0),
            has_kudoed=data.get("has_kudoed", False),
            gear_id=data.get("gear_id"),
            average_heartrate=data.get("average_heartrate"),
            max_heartrate=data.get("max_heartrate"),
            heartrate_opt_out=data.get("heartrate_opt_out", False),
            display_hide_heartrate_option=data.get("display_hide_heartrate_option", False),
            elev_high=data.get("elev_high"),
            elev_low=data.get("elev_low"),
            start_latlng=data.get("start_latlng"),
            end_latlng=data.get("end_latlng"),
            summary_polyline=data.get("map", {}).get("summary_polyline") or None,
        )
