"""Background worker threads shared by the main window and import dialogs."""

from __future__ import annotations

import webbrowser
from datetime import timezone, timedelta
from typing import List, Optional

from PyQt6.QtCore import QThread, pyqtSignal

from src.api.strava_client import StravaAPI
from src.auth.callback_handler import OAuthCallbackServer
from src.models.activity import Activity
from src.models.track import Track, TrackPoint


class FetchActivitiesWorker(QThread):
    """Fetch activities from Strava in a background thread.

    When *after_date* is provided the worker performs an incremental sync,
    fetching only activities that started after that UTC datetime (up to
    200 per page).  Otherwise it fetches the 50 most recent activities.
    """

    finished = pyqtSignal(list)   # List[Activity]
    error    = pyqtSignal(str)
    progress = pyqtSignal(str)

    def __init__(self, api_client: StravaAPI, after_date=None) -> None:
        super().__init__()
        self.api_client = api_client
        self.after_date = after_date  # Optional[datetime]

    def run(self) -> None:
        try:
            if self.after_date is not None:
                self.progress.emit("Syncing new activities from Strava...")
                after_ts = int(self.after_date.timestamp())
                activities_data = self.api_client.get_activities(
                    after=after_ts, per_page=200
                )
            else:
                self.progress.emit("Connecting to Strava...")
                activities_data = self.api_client.get_activities(per_page=50)

            self.progress.emit("Converting data...")
            activities = [Activity.from_strava_api(act) for act in activities_data]
            self.finished.emit(activities)
        except Exception as e:
            self.error.emit(str(e))


class OAuthAuthenticationWorker(QThread):
    """Handle the Strava OAuth 2.0 flow in a background thread."""

    finished = pyqtSignal(dict)   # token_data
    error    = pyqtSignal(str)
    progress = pyqtSignal(str)

    def __init__(self, api_client: StravaAPI) -> None:
        super().__init__()
        self.api_client = api_client

    def run(self) -> None:
        try:
            self.progress.emit("Starting authentication...")
            callback_server = OAuthCallbackServer(port=8000)
            callback_server.start()
            self.progress.emit("Opening browser for authentication...")
            auth_url = self.api_client.oauth.authorization_url()
            webbrowser.open(auth_url)
            self.progress.emit("Waiting for authorization...")
            auth_code = callback_server.wait_for_callback(timeout=300)
            callback_server.stop()
            if not auth_code:
                raise Exception("Authorization timeout - please try again")
            self.progress.emit("Exchanging authorization code for token...")
            token_data = self.api_client.oauth.exchange_code(auth_code)
            self.progress.emit("Storing token...")
            self.api_client.set_token(token_data)
            self.finished.emit(token_data)
        except Exception as e:
            self.error.emit(str(e))


class StreamFetchWorker(QThread):
    """Fetch full-resolution GPS streams for a list of activities."""

    finished = pyqtSignal(list)   # List[Track]
    error    = pyqtSignal(str)
    progress = pyqtSignal(str)

    def __init__(self, api_client: StravaAPI, activities: List[Activity]) -> None:
        super().__init__()
        self.api_client = api_client
        self.activities = activities

    def run(self) -> None:
        tracks: List[Track] = []
        skipped = 0

        for i, activity in enumerate(self.activities, 1):
            self.progress.emit(
                f"Fetching streams {i}/{len(self.activities)}: {activity.name}"
            )
            if not activity.start_latlng:
                skipped += 1
                continue

            try:
                streams = self.api_client.get_activity_streams(activity.id)
            except Exception as e:
                self.error.emit(f"Failed to fetch streams for '{activity.name}': {e}")
                return

            latlng_data  = streams.get("latlng",   {}).get("data", [])
            if not latlng_data:
                skipped += 1
                continue

            altitude_data = streams.get("altitude", {}).get("data", [])
            time_data     = streams.get("time",     {}).get("data", [])

            start_utc = activity.start_date
            if start_utc.tzinfo is None:
                start_utc = start_utc.replace(tzinfo=timezone.utc)

            points: List[TrackPoint] = []
            for j, (lat, lon) in enumerate(latlng_data):
                elevation = altitude_data[j] if j < len(altitude_data) else None
                time = (
                    start_utc + timedelta(seconds=time_data[j])
                    if j < len(time_data) else None
                )
                points.append(TrackPoint(lat=lat, lon=lon,
                                         elevation=elevation, time=time))

            tracks.append(Track(
                activity_id=activity.id,
                activity_name=activity.name,
                start_time=start_utc,
                points=points,
            ))

        if skipped:
            self.progress.emit(
                f"Done — {skipped} indoor/no-GPS "
                f"activit{'y' if skipped == 1 else 'ies'} skipped"
            )
        self.finished.emit(tracks)


class BatchElevationFetchWorker(QThread):
    """Fetch and cache elevation profiles for a list of activities.

    Activities whose ``elevation_profile`` is already set are skipped.
    Results are written directly onto each ``Activity`` object so that
    the caller can rebuild the aggregated chart in ``finished``.
    """

    progress = pyqtSignal(str)           # e.g. "Fetching 2 / 5…"
    finished = pyqtSignal(list)          # the same activities list, now with profiles set
    error    = pyqtSignal(str)

    def __init__(self, api_client, activities: list) -> None:
        super().__init__()
        self.api_client = api_client
        self.activities = activities

    def run(self) -> None:
        missing = [a for a in self.activities if not a.elevation_profile and a.id > 0]
        total = len(missing)
        for i, act in enumerate(missing, 1):
            self.progress.emit(f"Fetching elevation {i} / {total}…")
            try:
                streams = self.api_client.get_activity_streams(act.id)
                alt  = streams.get("altitude", {}).get("data", [])
                dist = streams.get("distance", {}).get("data", [])
                if alt and dist:
                    n = min(len(alt), len(dist))
                    act.elevation_profile = ([d / 1000 for d in dist[:n]], list(alt[:n]))
            except Exception:
                pass  # leave profile as None; chart will skip this activity
        self.finished.emit(self.activities)


class ElevationFetchWorker(QThread):
    """Fetch altitude + distance streams for a single activity."""

    finished = pyqtSignal(list, list)   # distances_km, elevations_m
    error    = pyqtSignal(str)

    def __init__(self, api_client: StravaAPI, activity_id: int) -> None:
        super().__init__()
        self.api_client = api_client
        self.activity_id = activity_id

    def run(self) -> None:
        try:
            streams = self.api_client.get_activity_streams(self.activity_id)
            alt  = streams.get("altitude", {}).get("data", [])
            dist = streams.get("distance", {}).get("data", [])
            if alt and dist:
                n = min(len(alt), len(dist))
                self.finished.emit([d / 1000 for d in dist[:n]], list(alt[:n]))
            else:
                self.finished.emit([], [])
        except Exception as e:
            self.error.emit(str(e))
