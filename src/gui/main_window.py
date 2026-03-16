"""GUI components for GetTracks."""

import sys
import os
from datetime import datetime, timezone, timedelta
from typing import Optional, List
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QListWidget, QListWidgetItem, QLabel, QPushButton, QProgressBar,
    QMessageBox, QTextEdit, QSplitter, QFrame, QFileDialog
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QIcon, QPixmap, QColor, QPainter

from src.cache.activity_cache import ActivityCache
from src.config.settings import Config
from src.api.strava_client import StravaAPI
from src.auth.callback_handler import OAuthCallbackServer
from src.models.activity import Activity
from src.models.track import Track, TrackPoint
from src.gpx.processor import GPXProcessor
from src.visualization.map_widget import MapWidget
from src.utils.logging import setup_logging
from src.gui.splash import make_splash
from src.gui.filter_widget import FilterWidget
from src.gui.export_options_widget import ExportOptionsWidget
from src.gui.stats_bar import StatsBarWidget
from src.gui.elevation_chart import ElevationChart
from src.gui.toast import ToastManager
from src.filters.filter_engine import FilterCriteria, FilterEngine


class ActivityListWidget(QListWidget):
    """Widget for displaying list of activities."""

    activity_selected = pyqtSignal(Activity)

    def __init__(self):
        super().__init__()
        self.activities: List[Activity] = []
        self.setup_ui()
        self.itemClicked.connect(self.on_item_clicked)

    def setup_ui(self):
        """Set up the UI components."""
        self.setMinimumWidth(300)
        self.setAlternatingRowColors(True)
        self.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)

    def set_activities(self, activities: List[Activity]):
        """Set the list of activities to display."""
        self.clear()
        self.activities = activities

        for activity in activities:
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, activity)

            # Format activity display text
            distance_km = activity.distance / 1000
            display_text = f"{activity.name}\n"
            display_text += f"{activity.type} • {distance_km:.1f} km • "
            display_text += f"{activity.start_date_local.strftime('%Y-%m-%d %H:%M')}"

            item.setText(display_text)
            self.addItem(item)

    def on_item_clicked(self, item: QListWidgetItem):
        """Handle activity selection."""
        activity = item.data(Qt.ItemDataRole.UserRole)
        if activity:
            self.activity_selected.emit(activity)

    def get_selected_activities(self) -> List[Activity]:
        """Get currently selected activities."""
        selected_items = self.selectedItems()
        return [item.data(Qt.ItemDataRole.UserRole) for item in selected_items]


class ActivityDetailsWidget(QWidget):
    """Widget for displaying activity details."""

    def __init__(self):
        super().__init__()
        self.current_activity: Optional[Activity] = None
        self.setup_ui()

    def setup_ui(self):
        """Set up the UI components."""
        layout = QVBoxLayout(self)

        self.title_label = QLabel("Select an activity to view details")
        self.title_label.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        layout.addWidget(self.title_label)

        self.details_text = QTextEdit()
        self.details_text.setReadOnly(True)
        self.details_text.setMinimumHeight(200)
        layout.addWidget(self.details_text)

    def set_activity(self, activity: Activity):
        """Display details for the selected activity."""
        self.current_activity = activity

        self.title_label.setText(activity.name)

        details = f"""
<b>Type:</b> {activity.type}<br>
<b>Distance:</b> {activity.distance/1000:.2f} km<br>
<b>Moving Time:</b> {activity.moving_time//60} min {activity.moving_time%60} sec<br>
<b>Elapsed Time:</b> {activity.elapsed_time//60} min {activity.elapsed_time%60} sec<br>
<b>Elevation Gain:</b> {activity.total_elevation_gain:.0f} m<br>
<b>Average Speed:</b> {activity.average_speed * 3.6:.1f} km/h<br>
<b>Max Speed:</b> {activity.max_speed * 3.6:.1f} km/h<br>
<b>Date:</b> {activity.start_date_local.strftime('%Y-%m-%d %H:%M')}<br>
<b>Timezone:</b> {activity.timezone}<br>
"""

        if activity.has_heartrate and activity.average_heartrate:
            details += f"<b>Average HR:</b> {activity.average_heartrate:.0f} bpm<br>"
            if activity.max_heartrate:
                details += f"<b>Max HR:</b> {activity.max_heartrate:.0f} bpm<br>"

        details += f"""
<b>Achievements:</b> {activity.achievement_count}<br>
<b>Kudos:</b> {activity.kudos_count}<br>
<b>Comments:</b> {activity.comment_count}<br>
<b>Photos:</b> {activity.photo_count}<br>
<b>Private:</b> {'Yes' if activity.private else 'No'}<br>
<b>Commute:</b> {'Yes' if activity.commute else 'No'}<br>
<b>Manual:</b> {'Yes' if activity.manual else 'No'}<br>
"""

        self.details_text.setHtml(details)


class FetchActivitiesWorker(QThread):
    """Worker thread for fetching activities from Strava.

    When *after_date* is provided the worker performs an incremental sync,
    fetching only activities that started after that UTC datetime (up to
    200 per page).  Otherwise it fetches the 50 most recent activities.
    """

    finished = pyqtSignal(list)  # List[Activity]
    error = pyqtSignal(str)
    progress = pyqtSignal(str)

    def __init__(self, api_client: StravaAPI, after_date=None):
        super().__init__()
        self.api_client = api_client
        self.after_date = after_date  # Optional[datetime]

    def run(self):
        """Fetch activities in background thread."""
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
    """Worker thread for handling OAuth authentication."""

    finished = pyqtSignal(dict)  # token_data
    error = pyqtSignal(str)
    progress = pyqtSignal(str)

    def __init__(self, api_client: StravaAPI):
        super().__init__()
        self.api_client = api_client

    def run(self):
        """Handle OAuth authentication flow."""
        import webbrowser
        
        try:
            self.progress.emit("Starting authentication...")
            
            # Start the callback server
            callback_server = OAuthCallbackServer(port=8000)
            callback_server.start()
            self.progress.emit("Opening browser for authentication...")
            
            # Open browser to authorization URL
            auth_url = self.api_client.oauth.authorization_url()
            webbrowser.open(auth_url)
            
            # Wait for callback
            self.progress.emit("Waiting for authorization...")
            auth_code = callback_server.wait_for_callback(timeout=300)
            callback_server.stop()
            
            if not auth_code:
                raise Exception("Authorization timeout - please try again")
            
            # Exchange code for token
            self.progress.emit("Exchanging authorization code for token...")
            token_data = self.api_client.oauth.exchange_code(auth_code)
            
            # Store token
            self.progress.emit("Storing token...")
            self.api_client.set_token(token_data)
            
            self.finished.emit(token_data)
            
        except Exception as e:
            self.error.emit(str(e))


class StreamFetchWorker(QThread):
    """Fetch full-resolution GPS streams for a list of activities."""

    finished = pyqtSignal(list)   # List[Track]
    error = pyqtSignal(str)
    progress = pyqtSignal(str)

    def __init__(self, api_client: StravaAPI, activities: List[Activity]):
        super().__init__()
        self.api_client = api_client
        self.activities = activities

    def run(self):
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
                self.error.emit(
                    f"Failed to fetch streams for '{activity.name}': {e}"
                )
                return

            latlng_data = streams.get("latlng", {}).get("data", [])
            if not latlng_data:
                skipped += 1
                continue

            altitude_data = streams.get("altitude", {}).get("data", [])
            time_data = streams.get("time", {}).get("data", [])   # seconds from start

            # Build absolute UTC timestamps from elapsed-second offsets
            start_utc = activity.start_date
            if start_utc.tzinfo is None:
                start_utc = start_utc.replace(tzinfo=timezone.utc)

            points: List[TrackPoint] = []
            for j, (lat, lon) in enumerate(latlng_data):
                elevation = altitude_data[j] if j < len(altitude_data) else None
                time = (
                    start_utc + timedelta(seconds=time_data[j])
                    if j < len(time_data)
                    else None
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
                f"Done — {skipped} indoor/no-GPS activit{'y' if skipped == 1 else 'ies'} skipped"
            )
        self.finished.emit(tracks)


class ElevationFetchWorker(QThread):
    """Fetch altitude + distance streams for a single activity."""

    finished = pyqtSignal(list, list)   # distances_km, elevations_m
    error = pyqtSignal(str)

    def __init__(self, api_client: StravaAPI, activity_id: int) -> None:
        super().__init__()
        self.api_client = api_client
        self.activity_id = activity_id

    def run(self) -> None:
        try:
            streams = self.api_client.get_activity_streams(self.activity_id)
            alt = streams.get("altitude", {}).get("data", [])
            dist = streams.get("distance", {}).get("data", [])
            if alt and dist:
                n = min(len(alt), len(dist))
                self.finished.emit(
                    [d / 1000 for d in dist[:n]],
                    list(alt[:n]),
                )
            else:
                self.finished.emit([], [])
        except Exception as e:
            self.error.emit(str(e))


class MainWindow(QMainWindow):
    """Main application window."""

    def __init__(self, config: Config):
        super().__init__()
        self.config = config
        self.api_client = StravaAPI(config)
        self.logger = setup_logging(__name__)
        self._all_activities: List[Activity] = []
        self._filter_engine = FilterEngine()
        self._pending_tracks: Optional[List[Track]] = None  # set during export preview
        self._cache = ActivityCache(config.get("app.cache_dir", "cache"))

        self.setup_ui()
        self.connect_signals()
        self._toasts = ToastManager(self)
        self._restore_session()

    def setup_ui(self):
        """Set up the main UI."""
        self.setWindowTitle("GetTracks - Strava Activity Merger")
        self.setMinimumSize(1200, 800)
        
        # Load and set application icon
        icon_paths = [
            "assets/app_icon.png",
            "../assets/app_icon.png",
            os.path.join(os.path.dirname(__file__), "..", "..", "assets", "app_icon.png")
        ]
        
        for icon_path in icon_paths:
            if os.path.exists(icon_path):
                icon = QIcon(icon_path)
                if not icon.isNull():
                    self.setWindowIcon(icon)
                    break

        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)

        # Main horizontal splitter: left = activity list, right = details + map
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(main_splitter)

        # Left panel - Activity list
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)

        # Control buttons
        button_layout = QHBoxLayout()

        self.auth_button = QPushButton("Authenticate with Strava")
        self.auth_button.setMinimumHeight(35)
        button_layout.addWidget(self.auth_button)

        self.fetch_button = QPushButton("Fetch Activities")
        self.fetch_button.setMinimumHeight(35)
        button_layout.addWidget(self.fetch_button)

        self.select_all_button = QPushButton("Select All")
        self.select_all_button.setEnabled(False)
        button_layout.addWidget(self.select_all_button)

        self.clear_selection_button = QPushButton("Clear Selection")
        self.clear_selection_button.setEnabled(False)
        button_layout.addWidget(self.clear_selection_button)

        self.export_button = QPushButton("Export Selected")
        self.export_button.setEnabled(False)
        self.export_button.setToolTip(
            "Fetch full GPS tracks for selected activities and export as GPX"
        )
        button_layout.addWidget(self.export_button)

        left_layout.addLayout(button_layout)

        # Filter widget
        self.filter_widget = FilterWidget()
        left_layout.addWidget(self.filter_widget)

        # Export options
        self.export_options = ExportOptionsWidget()
        left_layout.addWidget(self.export_options)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        left_layout.addWidget(self.progress_bar)

        # Activity list
        self.activity_list = ActivityListWidget()
        left_layout.addWidget(self.activity_list)

        # Stats bar at the bottom of the left panel
        self.stats_bar = StatsBarWidget()
        left_layout.addWidget(self.stats_bar)

        main_splitter.addWidget(left_panel)

        # Right panel - vertical splitter: details on top, map on bottom
        right_splitter = QSplitter(Qt.Orientation.Vertical)

        self.activity_details = ActivityDetailsWidget()
        right_splitter.addWidget(self.activity_details)

        self.elevation_chart = ElevationChart()
        self.elevation_chart.setFixedHeight(130)
        self.elevation_chart.setVisible(False)
        right_splitter.addWidget(self.elevation_chart)

        self.map_widget = MapWidget()
        self.map_widget.setMinimumHeight(200)
        self.map_widget.setVisible(False)
        right_splitter.addWidget(self.map_widget)

        right_splitter.setSizes([260, 130, 400])
        main_splitter.addWidget(right_splitter)

        # Set main splitter proportions
        main_splitter.setSizes([400, 800])
        
        # Status bar with icon
        self.status_bar = self.statusBar()
        self.status_icon = QLabel()
        self.status_text = QLabel("Ready")
        self.status_bar.addWidget(self.status_icon, 0)
        self.status_bar.addWidget(self.status_text, 1)

    def resizeEvent(self, event):
        """Reposition toasts when the window is resized."""
        super().resizeEvent(event)
        if hasattr(self, "_toasts"):
            self._toasts.restack()

    def connect_signals(self):
        """Connect UI signals to handlers."""
        self.auth_button.clicked.connect(self.authenticate)
        self.fetch_button.clicked.connect(self.fetch_activities)
        self.select_all_button.clicked.connect(self.select_all_activities)
        self.clear_selection_button.clicked.connect(self.clear_selection)
        self.export_button.clicked.connect(self.on_export_selected)
        self.activity_list.activity_selected.connect(self.on_activity_selected)
        self.activity_list.itemSelectionChanged.connect(self._on_selection_changed)
        self.filter_widget.filters_changed.connect(self._on_filters_changed)

    def _restore_session(self) -> None:
        """Restore UI state from keyring token and on-disk activity cache."""
        if self.api_client.token_data:
            self.auth_button.setText("✓ Connected")
            self.update_status("Session restored — click 'Fetch Activities' to continue", "success")
            self.show_toast("Previous session restored", "success", duration_ms=3000)

        # Load cached activities immediately so the UI is populated without a network call
        cached = self._cache.load()
        if cached:
            self._all_activities = cached
            self.filter_widget.populate_types(cached)
            self.activity_list.set_activities(cached)
            self.select_all_button.setEnabled(True)
            self.clear_selection_button.setEnabled(True)
            self.stats_bar.update_stats(cached)
            self.map_widget.setVisible(True)
            self.map_widget.display_activities(cached)
            last = self._cache.last_sync()
            last_str = last.strftime("%Y-%m-%d %H:%M") if last else "unknown"
            self.update_status(
                f"Loaded {len(cached)} cached activities (last sync: {last_str})", "info"
            )
            self._update_fetch_button_label()

    def _update_fetch_button_label(self) -> None:
        """Show 'Sync New' when cache is populated, 'Fetch Activities' otherwise."""
        if self._cache.count() > 0:
            most_recent = self._cache.most_recent_start()
            label = "Sync New Activities"
            if most_recent:
                label += f" (since {most_recent.strftime('%Y-%m-%d')})"
            self.fetch_button.setText(label)
        else:
            self.fetch_button.setText("Fetch Activities")

    def show_toast(self, message: str, level: str = "info", duration_ms: int = 4000) -> None:
        """Show a floating toast notification."""
        self._toasts.show(message, level, duration_ms)

    def on_activity_selected(self, activity: Activity):
        """Handle activity selection — update details, map, and elevation chart."""
        self.activity_details.set_activity(activity)
        self.map_widget.setVisible(True)
        self.map_widget.display_single_activity(activity)
        self._fetch_elevation(activity)

    def _fetch_elevation(self, activity: Activity) -> None:
        """Start an async fetch of the elevation profile for *activity*."""
        if not activity.start_latlng:
            self.elevation_chart.clear()
            self.elevation_chart.setVisible(False)
            return
        self.elevation_chart.setVisible(True)
        self.elevation_chart.set_loading(True)
        self._elev_worker = ElevationFetchWorker(self.api_client, activity.id)
        self._elev_worker.finished.connect(
            lambda dist, elev: self._on_elevation_fetched(dist, elev, activity.name)
        )
        self._elev_worker.error.connect(lambda _: self.elevation_chart.clear())
        self._elev_worker.start()

    def _on_elevation_fetched(self, distances_km, elevations_m, name: str) -> None:
        if distances_km and elevations_m:
            self.elevation_chart.set_data(distances_km, elevations_m, name)
        else:
            self.elevation_chart.clear()
            self.elevation_chart.setVisible(False)

    def authenticate(self):
        """Start authentication with Strava."""
        self.logger.info("Starting Strava authentication")

        # Update UI
        self.auth_button.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # Indeterminate progress
        self.update_status("Authenticating with Strava...", "working")

        # Start authentication worker thread
        self.auth_worker = OAuthAuthenticationWorker(self.api_client)
        self.auth_worker.progress.connect(self.update_progress)
        self.auth_worker.finished.connect(self.on_authenticated)
        self.auth_worker.error.connect(self.on_auth_error)
        self.auth_worker.start()

    def on_authenticated(self, token_data: dict):
        """Handle successful authentication."""
        self.logger.info("Successfully authenticated with Strava")

        self.auth_button.setEnabled(True)
        self.auth_button.setText("✓ Connected")
        self.progress_bar.setVisible(False)
        self.update_status("Authenticated — click 'Fetch Activities' to load your activities.", "success")
        self.show_toast("Successfully authenticated with Strava", "success")

    def on_auth_error(self, error_msg: str):
        """Handle authentication error."""
        self.logger.error(f"Authentication error: {error_msg}")

        self.auth_button.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.update_status("Authentication failed", "error")
        self.show_toast(f"Authentication failed: {error_msg}", "error", duration_ms=6000)

    def fetch_activities(self):
        """Fetch from Strava: incremental sync if cache populated, full fetch otherwise."""
        self.logger.info("Starting activity fetch")

        after_date = self._cache.most_recent_start() if self._cache.count() > 0 else None

        self.fetch_button.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)
        self.update_status("Syncing activities…" if after_date else "Fetching activities…", "working")

        self.worker = FetchActivitiesWorker(self.api_client, after_date=after_date)
        self.worker.progress.connect(self.update_progress)
        self.worker.finished.connect(self.on_activities_fetched)
        self.worker.error.connect(self.on_fetch_error)
        self.worker.start()

    def update_progress(self, message: str):
        """Update progress display."""
        self.status_text.setText(message)

    def update_status(self, message: str, status_type: str = "info"):
        """Update status bar with message and icon.
        
        Args:
            message: Status message to display
            status_type: Type of status - 'ready', 'working', 'success', 'error', 'info'
        """
        self.status_text.setText(message)
        
        # Create status icons
        if status_type == "ready":
            # Green circle for ready
            pixmap = self._create_colored_pixmap("#4CAF50", 16)
        elif status_type == "working":
            # Yellow circle for working
            pixmap = self._create_colored_pixmap("#2196F3", 16)
        elif status_type == "success":
            # Green checkmark
            pixmap = self._create_colored_pixmap("#4CAF50", 16)
        elif status_type == "error":
            # Red X
            pixmap = self._create_colored_pixmap("#F44336", 16)
        else:  # info
            # Gray circle
            pixmap = self._create_colored_pixmap("#9E9E9E", 16)
        
        self.status_icon.setPixmap(pixmap)

    @staticmethod
    def _create_colored_pixmap(color: str, size: int):
        """Create a colored circle pixmap.
        
        Args:
            color: Hex color string (e.g., "#4CAF50")
            size: Size of the pixmap in pixels
        
        Returns:
            QPixmap with colored circle
        """
        pixmap = QPixmap(size, size)
        pixmap.fill(QColor(0, 0, 0, 0))  # Transparent
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QColor(color))
        painter.setPen(QColor(color))
        painter.drawEllipse(1, 1, size - 2, size - 2)
        painter.end()
        
        return pixmap

    def on_activities_fetched(self, activities: List[Activity]):
        """Merge new activities into cache, refresh the UI."""
        self.logger.info(f"Fetched {len(activities)} activities from Strava")

        # Merge into cache; combined list is deduplicated and sorted newest-first
        combined = self._cache.merge(activities)
        new_count = len(activities)
        total = len(combined)

        self._all_activities = combined

        self.fetch_button.setEnabled(True)
        self.progress_bar.setVisible(False)

        if new_count:
            msg = f"Synced {new_count} new activit{'y' if new_count == 1 else 'ies'} — {total} total"
        else:
            msg = f"No new activities — {total} total in cache"
        self.update_status(msg, "success")
        self.show_toast(msg, "success", duration_ms=3000)

        self._update_fetch_button_label()
        self.select_all_button.setEnabled(True)
        self.clear_selection_button.setEnabled(True)
        self.filter_widget.populate_types(combined)
        self.activity_list.set_activities(combined)
        self.stats_bar.update_stats(combined)
        self.map_widget.setVisible(True)
        self.map_widget.display_activities(combined)

    def _on_filters_changed(self, criteria: FilterCriteria) -> None:
        """Apply filters and refresh the activity list and map."""
        filtered = self._filter_engine.apply(self._all_activities, criteria)
        self.activity_list.set_activities(filtered)
        self.stats_bar.update_stats(filtered)
        self.update_status(
            f"Showing {len(filtered)} of {len(self._all_activities)} activities",
            "info",
        )
        if filtered:
            self.map_widget.setVisible(True)
            self.map_widget.display_activities(filtered)
        else:
            self.map_widget.setVisible(False)

    def on_fetch_error(self, error_msg: str):
        """Handle fetch error."""
        self.logger.error(f"Fetch error: {error_msg}")

        self.fetch_button.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.update_status("Error fetching activities", "error")

        if "No token data available" in error_msg or "not authenticated" in error_msg.lower():
            self.update_status("Not authenticated — please connect with Strava first", "error")
            self.show_toast("Please authenticate with Strava first", "warning", duration_ms=5000)
        elif "Token refresh failed" in error_msg or "re-authenticate" in error_msg.lower():
            # Refresh token is dead — reset the auth button so the user can re-auth
            self.auth_button.setText("Authenticate with Strava")
            self.update_status("Session expired — please re-authenticate", "error")
            self.show_toast("Session expired — please re-authenticate with Strava", "error", duration_ms=6000)
        else:
            self.show_toast(f"Fetch error: {error_msg}", "error", duration_ms=6000)

    def select_all_activities(self):
        """Select all activities in the list."""
        self.activity_list.selectAll()

    def clear_selection(self):
        """Clear all activity selections."""
        self.activity_list.clearSelection()

    def _update_export_button_state(self):
        """Enable/label export button based on selection and preview state."""
        if self._pending_tracks is not None:
            self.export_button.setText("Save GPX")
            self.export_button.setEnabled(True)
        else:
            self.export_button.setText("Export Selected")
            self.export_button.setEnabled(len(self.activity_list.selectedItems()) > 0)

    def _on_selection_changed(self):
        """Exit preview mode if the user changes their selection."""
        if self._pending_tracks is not None:
            self._exit_preview_mode()
        self._update_export_button_state()

    def _enter_preview_mode(self, tracks: List[Track]) -> None:
        """Show export preview on map and switch button to 'Save GPX'."""
        self._pending_tracks = tracks
        self.map_widget.setVisible(True)
        self.map_widget.display_tracks(tracks)
        n = len(tracks)
        self.update_status(
            f"{n} track(s) shown — click 'Save GPX' to export, or change selection to cancel",
            "info",
        )
        self._update_export_button_state()

    def _exit_preview_mode(self) -> None:
        """Discard pending tracks and restore button to 'Export Selected'."""
        self._pending_tracks = None
        self._update_export_button_state()

    def on_export_selected(self):
        """Either fetch GPS streams (normal) or save pending preview tracks."""
        if self._pending_tracks is not None:
            self._save_tracks(self._pending_tracks)
            self._exit_preview_mode()
            return

        activities = self.activity_list.get_selected_activities()
        if not activities:
            return

        self.export_button.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)
        n = len(activities)
        self.update_status(
            f"Fetching GPS streams for {n} activit{'y' if n == 1 else 'ies'}...", "working"
        )

        self.stream_worker = StreamFetchWorker(self.api_client, activities)
        self.stream_worker.progress.connect(self.update_progress)
        self.stream_worker.finished.connect(self.on_streams_fetched)
        self.stream_worker.error.connect(self.on_fetch_error)
        self.stream_worker.start()

    def on_streams_fetched(self, tracks: List[Track]):
        """Show preview on map; user confirms before the file dialog opens."""
        self.progress_bar.setVisible(False)

        if not tracks:
            self.update_status("No GPS tracks found in selection (indoor activities?)", "error")
            self._update_export_button_state()
            return

        self._enter_preview_mode(tracks)

    def _save_tracks(self, tracks: List[Track]) -> None:
        """Open file dialog and write tracks to GPX."""
        path, _ = QFileDialog.getSaveFileName(
            self, "Export GPX", "", "GPX Files (*.gpx)"
        )
        if not path:
            self.update_status("Export cancelled", "info")
            return

        if not path.endswith(".gpx"):
            path += ".gpx"

        gpx = GPXProcessor.merge(tracks, self.export_options.current_options())
        warnings = GPXProcessor.validate(gpx)
        GPXProcessor.save(gpx, path)

        selected = self.activity_list.get_selected_activities()
        skipped = len(selected) - len(tracks)
        msg = f"Exported {len(tracks)} track(s) to {os.path.basename(path)}"
        if skipped:
            msg += f" ({skipped} indoor/no-GPS activit{'y' if skipped == 1 else 'ies'} skipped)"
        if warnings:
            msg += f" — {len(warnings)} warning(s)"
        self.update_status(msg, "success")
        self.show_toast(msg, "success")


def main():
    """Main application entry point."""
    app = QApplication(sys.argv)
    
    # Load and set application icon
    icon_paths = [
        "assets/app_icon.png",
        "./assets/app_icon.png",
        os.path.join(os.path.dirname(__file__), "..", "..", "assets", "app_icon.png")
    ]
    
    for icon_path in icon_paths:
        if os.path.exists(icon_path):
            app_icon = QIcon(icon_path)
            if not app_icon.isNull():
                app.setWindowIcon(app_icon)
                break

    # Show splash screen while the app initialises
    splash = make_splash()
    splash.show()
    app.processEvents()

    # Load configuration
    config = Config()

    # Check if Strava is configured
    if not config.validate_strava_config():
        QMessageBox.critical(
            None,
            "Configuration Error",
            "Strava client ID and secret are not configured.\n\n"
            "Please check your config.json file."
        )
        return 1

    # Create and show main window; dismiss splash once window is ready
    window = MainWindow(config)
    window.show()
    splash.finish(window)

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())