"""Disk-backed cache for Strava Activity objects."""

import json
import os
from datetime import datetime, timezone
from typing import List, Optional

from src.models.activity import Activity


class ActivityCache:
    """Persists Activity objects to a JSON file in cache_dir.

    Serialisation round-trips through Activity.to_strava_dict() /
    Activity.from_strava_api() so the cache file format is the same as
    the Strava API response, making it easy to inspect manually.
    """

    _CACHE_FILE = "activities.json"
    _META_FILE = "cache_meta.json"

    def __init__(self, cache_dir: str) -> None:
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)
        self._cache_path = os.path.join(cache_dir, self._CACHE_FILE)
        self._meta_path = os.path.join(cache_dir, self._META_FILE)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load(self) -> List[Activity]:
        """Return cached activities sorted newest-first, or [] if no cache."""
        if not os.path.exists(self._cache_path):
            return []
        try:
            with open(self._cache_path, encoding="utf-8") as fh:
                raw: list = json.load(fh)
            activities = []
            for d in raw:
                try:
                    activities.append(Activity.from_strava_api(d))
                except Exception:
                    pass  # skip corrupt entries silently
            return activities
        except (json.JSONDecodeError, OSError):
            return []

    def save(self, activities: List[Activity]) -> None:
        """Overwrite the cache with *activities* (sorted newest-first)."""
        activities = sorted(activities, key=lambda a: a.start_date, reverse=True)
        data = [a.to_strava_dict() for a in activities]
        with open(self._cache_path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
        self._save_meta({
            "last_sync": datetime.now(timezone.utc).isoformat(),
            "count": len(activities),
        })

    def merge(self, new_activities: List[Activity]) -> List[Activity]:
        """Merge *new_activities* into the cache, deduplicate by id.

        Returns the combined list (newest-first).
        """
        existing = {a.id: a for a in self.load()}
        for a in new_activities:
            existing[a.id] = a  # new data wins on conflict
        combined = sorted(existing.values(), key=lambda a: a.start_date, reverse=True)
        self.save(combined)
        return combined

    def clear(self) -> None:
        """Delete all cache files."""
        for path in (self._cache_path, self._meta_path):
            if os.path.exists(path):
                os.remove(path)

    def count(self) -> int:
        """Number of activities in the cache (fast — reads metadata only)."""
        meta = self._load_meta()
        return meta.get("count", 0)

    def last_sync(self) -> Optional[datetime]:
        """UTC datetime of the last save/merge, or None if no cache."""
        meta = self._load_meta()
        ts = meta.get("last_sync")
        if ts:
            try:
                return datetime.fromisoformat(ts)
            except ValueError:
                pass
        return None

    def most_recent_start(self) -> Optional[datetime]:
        """start_date of the newest cached activity, for incremental sync."""
        activities = self.load()
        if not activities:
            return None
        return max(a.start_date for a in activities)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _save_meta(self, meta: dict) -> None:
        with open(self._meta_path, "w", encoding="utf-8") as fh:
            json.dump(meta, fh, indent=2)

    def _load_meta(self) -> dict:
        if not os.path.exists(self._meta_path):
            return {}
        try:
            with open(self._meta_path, encoding="utf-8") as fh:
                return json.load(fh)
        except (json.JSONDecodeError, OSError):
            return {}
