"""GUI components for GetTracks."""

import sys
import os
from datetime import datetime, timezone, timedelta
from typing import Optional, List
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QListWidget, QListWidgetItem, QLabel, QPushButton, QProgressBar,
    QMessageBox, QTextEdit, QSplitter, QFrame, QFileDialog, QInputDialog, QDialog,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QAction, QFont, QIcon, QPixmap, QColor, QPainter

from src.config.settings import Config
from src.api.strava_client import StravaAPI
from src.models.activity import Activity
from src.models.project import Project, ProjectItem
from src.models.track import Track, TrackPoint
from src.gpx.processor import GPXProcessor
from src.project.project_manager import ProjectManager
from src.visualization.map_widget import MapWidget
from src.utils.logging import setup_logging
from src.gui.splash import make_splash
from src.gui.strava_import_dialog import StravaImportDialog
from src.gui.gpx_import import import_gpx_file
from src.gui.export_options_widget import ExportOptionsWidget
from src.gui.stats_bar import StatsBarWidget
from src.gui.elevation_chart import ElevationChart
from src.gui.toast import ToastManager
from src.gui.project_list_widget import ProjectListWidget
from src.gui.connecting_segment_dialog import AddTransportationDialog, ConnectingSegmentDialog
from src.gui.strava_settings_dialog import StravaSettingsDialog
from src.gui.workers import StreamFetchWorker, ElevationFetchWorker, BatchElevationFetchWorker


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


# Workers are imported from src.gui.workers (FetchActivitiesWorker,
# OAuthAuthenticationWorker, StreamFetchWorker, ElevationFetchWorker)


class MainWindow(QMainWindow):
    """Main application window."""

    def __init__(self, config: Config):
        super().__init__()
        self.config = config
        self.api_client = StravaAPI(config)
        self.logger = setup_logging(__name__)
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

        self.view_project_button = QPushButton("View Project")
        self.view_project_button.setEnabled(False)
        self.view_project_button.setToolTip("Show all project tracks on the map using stored polylines")
        self.view_project_button.clicked.connect(self._on_view_project)
        button_layout.addWidget(self.view_project_button)

        self.export_button = QPushButton("Preview & Export")
        self.export_button.setEnabled(False)
        self.export_button.setToolTip(
            "Fetch full GPS tracks for all project activities and preview before export"
        )
        button_layout.addWidget(self.export_button)

        left_layout.addLayout(button_layout)

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

        # Settings menu
        settings_menu = mb.addMenu("&Settings")
        act_strava_cfg = QAction("Strava Connection…", self)
        act_strava_cfg.triggered.connect(self._open_strava_settings)
        settings_menu.addAction(act_strava_cfg)

        # Add track menu
        import_menu = mb.addMenu("&Add track")

        self._act_strava = QAction("From &Strava…", self)
        self._act_strava.triggered.connect(self._import_from_strava)
        import_menu.addAction(self._act_strava)
        self._update_strava_action_state()

        act_gpx = QAction("From &GPX file…", self)
        act_gpx.triggered.connect(self._import_from_gpx)
        import_menu.addAction(act_gpx)

        import_menu.addSeparator()

        act_transport = QAction("🚂 &Transportation…", self)
        act_transport.triggered.connect(self._add_transportation)
        import_menu.addAction(act_transport)

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
        project = self._project_manager.project
        default_name = (project.name if project else "") + ".gettracks"
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Project As", default_name, "GetTracks Project (*.gettracks)"
        )
        if not path:
            return
        if not path.endswith(".gettracks"):
            path += ".gettracks"
        self._project_manager.save_as(path)
        self.config.set("app.last_project_path", path)
        self.config.save()

    # ------------------------------------------------------------------
    # Import menu handlers
    # ------------------------------------------------------------------

    def _update_strava_action_state(self) -> None:
        self._act_strava.setEnabled(self.config.validate_strava_config())

    def _open_strava_settings(self) -> None:
        dlg = StravaSettingsDialog(self.config, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._update_strava_action_state()

    def _import_from_strava(self) -> None:
        project = self._project_manager.project
        if project is None:
            return
        dlg = StravaImportDialog(project, self.api_client, self)
        dlg.import_complete.connect(self._on_strava_import_complete)
        dlg.exec()

    def _on_strava_import_complete(self) -> None:
        project = self._project_manager.project
        if project is None:
            return
        self._project_manager.mark_dirty()
        self.project_list.refresh()
        self.stats_bar.update_stats(project.activities)
        self._update_export_button_state()
        if project.items:
            self.map_widget.setVisible(True)
            self.map_widget.display_project(project)
            self._show_project_elevation(project)

    def _import_from_gpx(self) -> None:
        project = self._project_manager.project
        if project is None:
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Import GPX file", "", "GPX Files (*.gpx)"
        )
        if not path:
            return
        activities = import_gpx_file(path)
        if not activities:
            self.show_toast(f"No tracks found in {os.path.basename(path)}", "warning")
            return
        project.add_activities(activities)
        for act in activities:
            project.items.append(ProjectItem(item_type="activity", activity_id=act.id))
        self._project_manager.mark_dirty()
        self.project_list.refresh()
        self.stats_bar.update_stats(project.activities)
        self.map_widget.setVisible(True)
        self.map_widget.display_project(project)
        self._show_project_elevation(project)
        n = len(activities)
        self.show_toast(
            f"Imported {n} track{'s' if n != 1 else ''} from {os.path.basename(path)}",
            "success",
        )

    def _add_transportation(self) -> None:
        project = self._project_manager.project
        if project is None:
            return
        dlg = AddTransportationDialog(project, self)
        if dlg.exec() != AddTransportationDialog.DialogCode.Accepted:
            return
        seg = dlg.result_segment()
        idx = dlg.result_index()
        project.items.insert(idx, ProjectItem(item_type="segment", segment=seg))
        self._project_manager.mark_dirty()
        self.project_list.refresh()
        self.map_widget.setVisible(True)
        self.map_widget.display_project(project)

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
        self._exit_preview_mode()
        self._update_title()
        self.project_list.set_project(project)
        if project:
            self.stats_bar.update_stats(project.activities)
            if project.activities:
                self.map_widget.setVisible(True)
                self.map_widget.display_project(project)
                self._show_project_elevation(project)
            else:
                self.map_widget.setVisible(False)
                self.elevation_chart.clear()
                self.elevation_chart.setVisible(False)
        else:
            self.map_widget.setVisible(False)
            self.elevation_chart.clear()
            self.elevation_chart.setVisible(False)
            self.stats_bar.update_stats([])
        self._update_export_button_state()

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

    def _on_selection_changed(self, items: list) -> None:
        project = self._project_manager.project
        if project is None or not items:
            return

        act_map = {a.id: a for a in project.activities}

        # Collect selected activities in project order
        selected_acts = [
            act_map[it.activity_id]
            for it in items
            if it.item_type == "activity" and it.activity_id in act_map
        ]

        if len(selected_acts) == 1:
            self.on_activity_selected(selected_acts[0])
        elif len(selected_acts) > 1:
            self._on_multi_activity_selected(selected_acts)
        else:
            # Only segment(s) selected — show full project map, hide elevation
            self.elevation_chart.setVisible(False)
            self.map_widget.setVisible(True)
            self.map_widget.display_project(project)

    def _on_multi_activity_selected(self, activities: list) -> None:
        """Show combined map + aggregated elevation for a multi-activity selection."""
        self.map_widget.setVisible(True)
        self.map_widget.display_activities(activities)

        # Show whatever is already cached while fetching the rest
        self._render_multi_elevation(activities)

        missing = [a for a in activities if not a.elevation_profile and a.id > 0]
        if missing:
            self.elevation_chart.setVisible(True)
            self.elevation_chart.set_loading(True)
            self._batch_elev_worker = BatchElevationFetchWorker(self.api_client, activities)
            self._batch_elev_worker.finished.connect(
                lambda acts: self._on_batch_elevation_done(acts)
            )
            self._batch_elev_worker.start()

    def _on_batch_elevation_done(self, activities: list) -> None:
        self._project_manager.mark_dirty()   # profiles are now cached on activity objects
        self._render_multi_elevation(activities)

    def _render_multi_elevation(self, activities: list) -> None:
        """Aggregate cached elevation profiles and push to the chart."""
        combined_dist: list = []
        combined_elev: list = []
        offset = 0.0
        for act in activities:
            if not act.elevation_profile:
                continue
            dists, elevs = act.elevation_profile
            combined_dist.extend(d + offset for d in dists)
            combined_elev.extend(elevs)
            offset = combined_dist[-1] if combined_dist else offset
        if combined_dist:
            label = f"{len(activities)} activities"
            self.elevation_chart.set_data(combined_dist, combined_elev, label)
            self.elevation_chart.setVisible(True)
        else:
            self.elevation_chart.clear()
            self.elevation_chart.setVisible(False)

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

    def _on_edit_segment_requested(self, index: int) -> None:
        project = self._project_manager.project
        if project is None or index < 0 or index >= len(project.items):
            return
        item = project.items[index]
        if item.item_type != "segment" or item.segment is None:
            return
        dlg = AddTransportationDialog(
            project, self, segment=item.segment, segment_index=index
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        project.items[index] = ProjectItem(item_type="segment", segment=dlg.result_segment())
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
        self.export_button.clicked.connect(self.on_export_selected)

        # Project manager signals
        self._project_manager.project_changed.connect(self._on_project_changed)
        self._project_manager.dirty_changed.connect(self._on_dirty_changed)

        # Project list signals
        self.project_list.item_reordered.connect(self._on_item_reordered)
        self.project_list.selection_changed.connect(self._on_selection_changed)
        self.project_list.insert_segment_requested.connect(self._on_insert_segment_requested)
        self.project_list.remove_item_requested.connect(self._on_remove_item_requested)
        self.project_list.edit_segment_requested.connect(self._on_edit_segment_requested)

    def _restore_session(self) -> None:
        """Restore auth token and last open project."""
        if self.api_client.token_data:
            self.update_status("Session restored", "success")
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
        """Show cached elevation profile or fetch from Strava if not yet cached."""
        if not activity.start_latlng:
            self.elevation_chart.clear()
            self.elevation_chart.setVisible(False)
            return

        # Use cached profile if available (GPX always has one; Strava after first view)
        if activity.elevation_profile:
            dist_km, elev_m = activity.elevation_profile
            self.elevation_chart.set_data(dist_km, elev_m, activity.name)
            self.elevation_chart.setVisible(True)
            return

        if activity.id < 0:
            # GPX activity with no elevation data in the file
            self.elevation_chart.clear()
            self.elevation_chart.setVisible(False)
            return

        # Strava activity — fetch altitude + distance streams for the first time
        self.elevation_chart.setVisible(True)
        self.elevation_chart.set_loading(True)
        self._elev_worker = ElevationFetchWorker(self.api_client, activity.id)
        self._elev_worker.finished.connect(
            lambda dist, elev, act=activity:
                self._on_elevation_fetched(dist, elev, act)
        )
        self._elev_worker.error.connect(self._on_elevation_error)
        self._elev_worker.start()

    def _on_elevation_error(self, msg: str) -> None:
        self.elevation_chart.clear()
        if not self.api_client.token_data:
            self.show_toast(
                "No Strava token — go to Add track → From Strava… to authenticate",
                "warning", duration_ms=6000,
            )

    def _on_elevation_fetched(self, distances_km, elevations_m, activity: Activity) -> None:
        if distances_km and elevations_m:
            activity.elevation_profile = (distances_km, elevations_m)
            self._project_manager.mark_dirty()
            self.elevation_chart.set_data(distances_km, elevations_m, activity.name)
        else:
            self.elevation_chart.clear()
            self.elevation_chart.setVisible(False)

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

    def on_fetch_error(self, error_msg: str):
        """Handle stream-fetch error."""
        self.logger.error(f"Fetch error: {error_msg}")
        self.progress_bar.setVisible(False)
        self.update_status("Error fetching activities", "error")

        self.show_toast(f"Stream fetch error: {error_msg}", "error", duration_ms=6000)

    def _update_export_button_state(self):
        """Enable/label export button based on project state."""
        project = self._project_manager.project
        has_items = bool(project and project.items)
        self.view_project_button.setEnabled(has_items)
        if self._pending_tracks is not None:
            self.export_button.setText("Export as GPX")
            self.export_button.setEnabled(True)
        else:
            self.export_button.setText("Preview & Export")
            self.export_button.setEnabled(has_items)

    def _on_view_project(self) -> None:
        """Instantly show full project on map using stored summary polylines."""
        project = self._project_manager.project
        if project is None:
            return
        self._exit_preview_mode()
        self.project_list.clear_selection()
        self.map_widget.setVisible(True)
        self.map_widget.display_project(project)
        self._show_project_elevation(project)

    def _show_project_elevation(self, project) -> None:
        """Show aggregated elevation for all project activities, fetching any missing profiles."""
        act_map = {a.id: a for a in project.activities}
        activities = [
            act_map[it.activity_id]
            for it in project.items
            if it.item_type == "activity" and it.activity_id in act_map
        ]
        self._render_multi_elevation(activities)

        missing = [a for a in activities if not a.elevation_profile and a.id > 0]
        if missing:
            self.elevation_chart.setVisible(True)
            self.elevation_chart.set_loading(True)
            self._batch_elev_worker = BatchElevationFetchWorker(self.api_client, activities)
            self._batch_elev_worker.finished.connect(
                lambda acts: self._on_batch_elevation_done(acts)
            )
            self._batch_elev_worker.start()

    def _enter_preview_mode(self, tracks: List[Track]) -> None:
        """Show export preview on map and switch button to 'Save GPX'."""
        self._pending_tracks = tracks
        project = self._project_manager.project
        self.map_widget.setVisible(True)
        self.map_widget.display_tracks(tracks)
        if project:
            self.map_widget.overlay_segments(project)
        n = len(tracks)
        self.update_status(
            f"{n} track(s) ready — click 'Export as GPX' to save, or modify the project to cancel",
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

        # Collect all activity items from the project (in order)
        act_map = {a.id: a for a in project.activities}
        selected_activities: List[Activity] = [
            act_map[it.activity_id]
            for it in project.items
            if it.item_type == "activity"
            and it.activity_id in act_map
        ]

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

    # Create and show main window; dismiss splash once window is ready
    window = MainWindow(config)
    window.show()
    splash.finish(window)

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())