"""GUI components for GetTracks."""

import sys
import os
from datetime import datetime, timezone, timedelta
from typing import Optional, List
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QListWidget, QListWidgetItem, QLabel, QPushButton, QProgressBar,
    QMessageBox, QTextEdit, QSplitter, QFrame, QFileDialog, QInputDialog,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QAction, QFont, QIcon, QPixmap, QColor, QPainter

from src.config.settings import Config
from src.api.strava_client import StravaAPI
from src.auth.callback_handler import OAuthCallbackServer
from src.models.activity import Activity
from src.models.project import Project, ProjectItem
from src.models.track import Track, TrackPoint
from src.gpx.processor import GPXProcessor
from src.project.project_manager import ProjectManager
from src.visualization.map_widget import MapWidget
from src.utils.logging import setup_logging
from src.gui.splash import make_splash
from src.gui.filter_widget import FilterWidget
from src.gui.export_options_widget import ExportOptionsWidget
from src.gui.stats_bar import StatsBarWidget
from src.gui.elevation_chart import ElevationChart
from src.gui.toast import ToastManager
from src.gui.project_list_widget import ProjectListWidget
from src.gui.connecting_segment_dialog import ConnectingSegmentDialog
from src.filters.filter_engine import FilterCriteria, FilterEngine


class ActivityListWidget(QListWidget):
    """Legacy activity list widget — kept for backward compatibility."""

    activity_selected = pyqtSignal(Activity)

    def __init__(self):
        super().__init__()
        self.activities: List[Activity] = []
        self.setMinimumWidth(300)
        self.setAlternatingRowColors(True)
        self.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.itemClicked.connect(self._on_item_clicked)

    def set_activities(self, activities: List[Activity]):
        self.clear()
        self.activities = activities
        for activity in activities:
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, activity)
            distance_km = activity.distance / 1000
            display_text = (
                f"{activity.name}\n"
                f"{activity.type} • {distance_km:.1f} km • "
                f"{activity.start_date_local.strftime('%Y-%m-%d %H:%M')}"
            )
            item.setText(display_text)
            self.addItem(item)

    def _on_item_clicked(self, item: QListWidgetItem):
        activity = item.data(Qt.ItemDataRole.UserRole)
        if activity:
            self.activity_selected.emit(activity)

    def get_selected_activities(self) -> List[Activity]:
        return [item.data(Qt.ItemDataRole.UserRole) for item in self.selectedItems()]


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
        self._filter_engine = FilterEngine()
        self._pending_tracks: Optional[List[Track]] = None  # set during export preview
        self._project_manager = ProjectManager(self)

        self.setup_ui()
        self._build_menu()
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

        self.export_button = QPushButton("Visualise Selection")
        self.export_button.setEnabled(False)
        self.export_button.setToolTip(
            "Fetch full GPS tracks for selected activities and preview before export"
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

        # Project item list (replaces flat ActivityListWidget)
        self.project_list = ProjectListWidget()
        left_layout.addWidget(self.project_list)

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

    def closeEvent(self, event):
        """Guard against closing with unsaved changes."""
        if self._project_manager.is_dirty:
            reply = QMessageBox.question(
                self, "Unsaved changes",
                "The current project has unsaved changes. Save before closing?",
                QMessageBox.StandardButton.Save |
                QMessageBox.StandardButton.Discard |
                QMessageBox.StandardButton.Cancel,
            )
            if reply == QMessageBox.StandardButton.Save:
                if not self._project_manager.save():
                    self._file_save_as()
                event.accept()
            elif reply == QMessageBox.StandardButton.Discard:
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()

    # ------------------------------------------------------------------
    # Menu bar
    # ------------------------------------------------------------------

    def _build_menu(self) -> None:
        mb = self.menuBar()
        file_menu = mb.addMenu("&File")

        act_new = QAction("&New Project\tCtrl+N", self)
        act_new.setShortcut("Ctrl+N")
        act_new.triggered.connect(self._file_new)
        file_menu.addAction(act_new)

        act_open = QAction("&Open Project…\tCtrl+O", self)
        act_open.setShortcut("Ctrl+O")
        act_open.triggered.connect(self._file_open)
        file_menu.addAction(act_open)

        act_close = QAction("&Close Project", self)
        act_close.triggered.connect(self._file_close)
        file_menu.addAction(act_close)

        file_menu.addSeparator()

        act_save = QAction("&Save\tCtrl+S", self)
        act_save.setShortcut("Ctrl+S")
        act_save.triggered.connect(self._file_save)
        file_menu.addAction(act_save)

        act_save_as = QAction("Save &As…", self)
        act_save_as.triggered.connect(self._file_save_as)
        file_menu.addAction(act_save_as)

    # ------------------------------------------------------------------
    # File menu handlers
    # ------------------------------------------------------------------

    def _file_new(self) -> None:
        if not self._confirm_discard_changes():
            return
        name, ok = QInputDialog.getText(self, "New Project", "Project name:")
        if not ok or not name.strip():
            return
        project = self._project_manager.new_project(name.strip())
        self.config.set("app.last_project_path", None)
        self._on_project_changed(project)

    def _file_open(self) -> None:
        if not self._confirm_discard_changes():
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Project", "", "GetTracks Project (*.gettracks)"
        )
        if not path:
            return
        try:
            project = self._project_manager.open_project(path)
            self.config.set("app.last_project_path", path)
            self.config.save()
            self._on_project_changed(project)
        except Exception as e:
            QMessageBox.critical(self, "Open failed", str(e))

    def _file_close(self) -> None:
        if not self._confirm_discard_changes():
            return
        self._project_manager.close_project()
        self.config.set("app.last_project_path", None)
        self.config.save()

    def _file_save(self) -> None:
        if not self._project_manager.save():
            self._file_save_as()

    def _file_save_as(self) -> None:
        if not self._project_manager.has_project:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Project As", "", "GetTracks Project (*.gettracks)"
        )
        if not path:
            return
        if not path.endswith(".gettracks"):
            path += ".gettracks"
        self._project_manager.save_as(path)
        self.config.set("app.last_project_path", path)
        self.config.save()

    def _confirm_discard_changes(self) -> bool:
        """Return True if it's safe to proceed (changes saved or discarded)."""
        if not self._project_manager.is_dirty:
            return True
        reply = QMessageBox.question(
            self, "Unsaved changes",
            "The current project has unsaved changes. Discard them?",
            QMessageBox.StandardButton.Save |
            QMessageBox.StandardButton.Discard |
            QMessageBox.StandardButton.Cancel,
        )
        if reply == QMessageBox.StandardButton.Save:
            if not self._project_manager.save():
                self._file_save_as()
            return True
        return reply == QMessageBox.StandardButton.Discard

    # ------------------------------------------------------------------
    # Project signal handlers
    # ------------------------------------------------------------------

    def _on_project_changed(self, project: Optional[Project]) -> None:
        """Called when a project is opened, created, or closed."""
        self._update_title()
        self.project_list.set_project(project)
        if project:
            # Pre-populate filter widget from saved state
            self.filter_widget.populate_types(project.activities)
            self.stats_bar.update_stats(project.activities)
            if project.activities:
                self.map_widget.setVisible(True)
                self.map_widget.display_project(project)
            else:
                self.map_widget.setVisible(False)
            self.fetch_button.setEnabled(True)
            self.select_all_button.setEnabled(bool(project.items))
            self.clear_selection_button.setEnabled(bool(project.items))
        else:
            self.map_widget.setVisible(False)
            self.stats_bar.update_stats([])
            self.fetch_button.setEnabled(False)
            self.select_all_button.setEnabled(False)
            self.clear_selection_button.setEnabled(False)

    def _on_dirty_changed(self, dirty: bool) -> None:
        self._update_title()

    def _update_title(self) -> None:
        project = self._project_manager.project
        if project:
            dirty_marker = "*" if self._project_manager.is_dirty else ""
            self.setWindowTitle(f"GetTracks — {project.name}{dirty_marker}")
        else:
            self.setWindowTitle("GetTracks")

    # ------------------------------------------------------------------
    # Project list signal handlers
    # ------------------------------------------------------------------

    def _on_item_reordered(self, from_idx: int, to_idx: int) -> None:
        project = self._project_manager.project
        if project is None:
            return
        if from_idx >= 0 and to_idx >= 0:
            project.move_item(from_idx, to_idx)
        self._project_manager.mark_dirty()
        self.map_widget.display_project(project)

    def _on_item_selected(self, item: ProjectItem) -> None:
        project = self._project_manager.project
        if project is None:
            return
        if item.item_type == "activity":
            activity = project.activity_by_id(item.activity_id)
            if activity:
                self.on_activity_selected(activity)
        elif item.item_type == "segment" and item.segment:
            self.elevation_chart.setVisible(False)
            self.map_widget.setVisible(True)
            self.map_widget.display_project(project)

    def _on_insert_segment_requested(self, index: int) -> None:
        project = self._project_manager.project
        if project is None:
            return

        # Find adjacent activities for auto-fill
        prev_act, next_act = None, None
        act_map = {a.id: a for a in project.activities}
        for i, it in enumerate(project.items):
            if it.item_type == "activity":
                act = act_map.get(it.activity_id)
                if i < index:
                    prev_act = act
                elif i >= index and next_act is None:
                    next_act = act

        dlg = ConnectingSegmentDialog(self, prev_activity=prev_act, next_activity=next_act)
        if dlg.exec() != ConnectingSegmentDialog.DialogCode.Accepted:
            return

        seg = dlg.result_segment()
        project.items.insert(index, ProjectItem(item_type="segment", segment=seg))
        self._project_manager.mark_dirty()
        self.project_list.refresh()
        self.map_widget.setVisible(True)
        self.map_widget.display_project(project)

    def _on_remove_item_requested(self, index: int) -> None:
        project = self._project_manager.project
        if project is None:
            return
        project.remove_item(index)
        self._project_manager.mark_dirty()
        self.project_list.refresh()
        if project.items:
            self.map_widget.display_project(project)

    def connect_signals(self):
        """Connect UI signals to handlers."""
        self.auth_button.clicked.connect(self.authenticate)
        self.fetch_button.clicked.connect(self.fetch_activities)
        self.select_all_button.clicked.connect(self.select_all_activities)
        self.clear_selection_button.clicked.connect(self.clear_selection)
        self.export_button.clicked.connect(self.on_export_selected)
        self.filter_widget.filters_changed.connect(self._on_filters_changed)

        # Project manager signals
        self._project_manager.project_changed.connect(self._on_project_changed)
        self._project_manager.dirty_changed.connect(self._on_dirty_changed)

        # Project list signals
        self.project_list.item_reordered.connect(self._on_item_reordered)
        self.project_list.item_selected.connect(self._on_item_selected)
        self.project_list.insert_segment_requested.connect(self._on_insert_segment_requested)
        self.project_list.remove_item_requested.connect(self._on_remove_item_requested)

    def _restore_session(self) -> None:
        """Restore auth token and last open project."""
        if self.api_client.token_data:
            self.auth_button.setText("✓ Connected")
            self.update_status("Session restored — click 'Fetch Activities' to continue", "success")
            self.show_toast("Previous session restored", "success", duration_ms=3000)

        last_path = self.config.get("app.last_project_path")
        if last_path and os.path.exists(last_path):
            try:
                project = self._project_manager.open_project(last_path)
                self.update_status(
                    f"Opened project '{project.name}' ({len(project.activities)} activities)", "info"
                )
                return
            except Exception as e:
                self.logger.warning(f"Could not restore last project: {e}")

        # No project: create a default one so the UI is functional
        # new_project already calls _set_dirty(False), so nothing extra needed
        self._project_manager.new_project("My Activities")

    def _update_fetch_button_label(self) -> None:
        """Show 'Sync New' when project has activities, 'Fetch Activities' otherwise."""
        project = self._project_manager.project
        if project and project.activities:
            most_recent = max(
                (a.start_date for a in project.activities if a.start_date),
                default=None,
            )
            label = "Sync New Activities"
            if most_recent:
                label += f" (since {most_recent.strftime('%Y-%m-%d')})"
            self.fetch_button.setText(label)
        else:
            self.fetch_button.setText("Fetch Activities")

    def show_toast(self, message: str, level: str = "info", duration_ms: int = 4000) -> None:
        """Show a floating toast notification."""
        self._toasts.show(message, level, duration_ms)

    def on_activity_selected(self, activity: Activity) -> None:
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
        """Fetch from Strava: incremental sync if project has activities, else full fetch."""
        self.logger.info("Starting activity fetch")
        project = self._project_manager.project
        if project is None:
            return

        after_date: Optional[datetime] = None
        if project.activities:
            after_date = max(
                (a.start_date for a in project.activities if a.start_date),
                default=None,
            )

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
        """Merge new activities into the project, refresh the UI."""
        self.logger.info(f"Fetched {len(activities)} activities from Strava")
        project = self._project_manager.project
        if project is None:
            return

        existing_ids = {a.id for a in project.activities}
        new_activities = [a for a in activities if a.id not in existing_ids]
        project.add_activities(activities)  # deduplicates internally

        # Append new activities as project items (date-sorted)
        new_activities_sorted = sorted(
            new_activities, key=lambda a: a.start_date or datetime.min
        )
        for act in new_activities_sorted:
            project.items.append(ProjectItem(item_type="activity", activity_id=act.id))

        new_count = len(new_activities)
        total = len(project.activities)

        if new_count:
            self._project_manager.mark_dirty()

        self.fetch_button.setEnabled(True)
        self.progress_bar.setVisible(False)

        if new_count:
            msg = f"Synced {new_count} new activit{'y' if new_count == 1 else 'ies'} — {total} total"
        else:
            msg = f"No new activities — {total} total in project"
        self.update_status(msg, "success")
        self.show_toast(msg, "success", duration_ms=3000)

        self._update_fetch_button_label()
        self.select_all_button.setEnabled(True)
        self.clear_selection_button.setEnabled(True)
        self.filter_widget.populate_types(project.activities)
        self.project_list.refresh()
        self.stats_bar.update_stats(project.activities)
        self.map_widget.setVisible(True)
        self.map_widget.display_project(project)

    def _on_filters_changed(self, criteria: FilterCriteria) -> None:
        """Persist filter state to project and refresh stats."""
        project = self._project_manager.project
        if project is None:
            return
        # Persist to project filter state
        project.filter_state.start_date = criteria.start_date.isoformat() if criteria.start_date else None
        project.filter_state.end_date = criteria.end_date.isoformat() if criteria.end_date else None
        project.filter_state.activity_types = list(criteria.activity_types) if criteria.activity_types else None
        self._project_manager.mark_dirty()

        filtered = self._filter_engine.apply(project.activities, criteria)
        self.stats_bar.update_stats(filtered)
        self.update_status(
            f"Filter active — {len(filtered)} of {len(project.activities)} activities match",
            "info",
        )

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
        """Select all items in the project list."""
        self.project_list._list.selectAll()

    def clear_selection(self):
        """Clear all selections."""
        self.project_list._list.clearSelection()

    def _update_export_button_state(self):
        """Enable/label export button based on selection and preview state."""
        if self._pending_tracks is not None:
            self.export_button.setText("Export as GPX")
            self.export_button.setEnabled(True)
        else:
            self.export_button.setText("Visualise Selection")
            has_sel = len(self.project_list._list.selectedItems()) > 0
            self.export_button.setEnabled(has_sel)

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

        project = self._project_manager.project
        if project is None:
            return

        # Collect selected activity items
        act_map = {a.id: a for a in project.activities}
        selected_activities: List[Activity] = []
        for wi in self.project_list._list.selectedItems():
            from PyQt6.QtCore import Qt
            item = wi.data(Qt.ItemDataRole.UserRole)
            if item and item.item_type == "activity":
                act = act_map.get(item.activity_id)
                if act:
                    selected_activities.append(act)

        if not selected_activities:
            return

        self.export_button.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)
        n = len(selected_activities)
        self.update_status(
            f"Fetching GPS streams for {n} activit{'y' if n == 1 else 'ies'}...", "working"
        )

        self.stream_worker = StreamFetchWorker(self.api_client, selected_activities)
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

        skipped = 0
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