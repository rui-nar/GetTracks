"""GUI components for GetTracks."""

import sys
from typing import Optional, List
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QListWidget, QListWidgetItem, QLabel, QPushButton, QProgressBar,
    QMessageBox, QTextEdit, QSplitter, QFrame
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QIcon

from src.config.settings import Config
from src.api.strava_client import StravaAPI
from src.models.activity import Activity
from src.utils.logging import setup_logging


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
    """Worker thread for fetching activities from Strava."""

    finished = pyqtSignal(list)  # List[Activity]
    error = pyqtSignal(str)
    progress = pyqtSignal(str)

    def __init__(self, api_client: StravaAPI):
        super().__init__()
        self.api_client = api_client

    def run(self):
        """Fetch activities in background thread."""
        try:
            self.progress.emit("Connecting to Strava...")
            activities_data = self.api_client.get_activities(per_page=50)

            self.progress.emit("Converting data...")
            activities = [Activity.from_strava_api(act) for act in activities_data]

            self.finished.emit(activities)

        except Exception as e:
            self.error.emit(str(e))


class MainWindow(QMainWindow):
    """Main application window."""

    def __init__(self, config: Config):
        super().__init__()
        self.config = config
        self.api_client = StravaAPI(config)
        self.logger = setup_logging(__name__)

        self.setup_ui()
        self.connect_signals()

    def setup_ui(self):
        """Set up the main UI."""
        self.setWindowTitle("GetTracks - Strava Activity Merger")
        self.setMinimumSize(1000, 700)

        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Main layout
        main_layout = QHBoxLayout(central_widget)

        # Create splitter for resizable panels
        splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(splitter)

        # Left panel - Activity list
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)

        # Control buttons
        button_layout = QHBoxLayout()
        self.fetch_button = QPushButton("Fetch Activities")
        self.fetch_button.setMinimumHeight(35)
        button_layout.addWidget(self.fetch_button)

        self.select_all_button = QPushButton("Select All")
        self.select_all_button.setEnabled(False)
        button_layout.addWidget(self.select_all_button)

        self.clear_selection_button = QPushButton("Clear Selection")
        self.clear_selection_button.setEnabled(False)
        button_layout.addWidget(self.clear_selection_button)

        left_layout.addLayout(button_layout)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        left_layout.addWidget(self.progress_bar)

        # Status label
        self.status_label = QLabel("Ready")
        left_layout.addWidget(self.status_label)

        # Activity list
        self.activity_list = ActivityListWidget()
        left_layout.addWidget(self.activity_list)

        splitter.addWidget(left_panel)

        # Right panel - Activity details
        self.activity_details = ActivityDetailsWidget()
        splitter.addWidget(self.activity_details)

        # Set splitter proportions
        splitter.setSizes([400, 600])

    def connect_signals(self):
        """Connect UI signals to handlers."""
        self.fetch_button.clicked.connect(self.fetch_activities)
        self.select_all_button.clicked.connect(self.select_all_activities)
        self.clear_selection_button.clicked.connect(self.clear_selection)
        self.activity_list.activity_selected.connect(self.activity_details.set_activity)

    def fetch_activities(self):
        """Start fetching activities from Strava."""
        self.logger.info("Starting activity fetch")

        # Update UI
        self.fetch_button.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # Indeterminate progress
        self.status_label.setText("Fetching activities...")

        # Start worker thread
        self.worker = FetchActivitiesWorker(self.api_client)
        self.worker.progress.connect(self.update_progress)
        self.worker.finished.connect(self.on_activities_fetched)
        self.worker.error.connect(self.on_fetch_error)
        self.worker.start()

    def update_progress(self, message: str):
        """Update progress display."""
        self.status_label.setText(message)

    def on_activities_fetched(self, activities: List[Activity]):
        """Handle successful activity fetch."""
        self.logger.info(f"Fetched {len(activities)} activities")

        # Update UI
        self.fetch_button.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.status_label.setText(f"Loaded {len(activities)} activities")

        # Enable selection buttons
        self.select_all_button.setEnabled(True)
        self.clear_selection_button.setEnabled(True)

        # Display activities
        self.activity_list.set_activities(activities)

    def on_fetch_error(self, error_msg: str):
        """Handle fetch error."""
        self.logger.error(f"Fetch error: {error_msg}")

        # Update UI
        self.fetch_button.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.status_label.setText("Error fetching activities")

        # Show error dialog
        QMessageBox.critical(
            self,
            "Fetch Error",
            f"Failed to fetch activities from Strava:\n\n{error_msg}"
        )

    def select_all_activities(self):
        """Select all activities in the list."""
        self.activity_list.selectAll()

    def clear_selection(self):
        """Clear all activity selections."""
        self.activity_list.clearSelection()


def main():
    """Main application entry point."""
    app = QApplication(sys.argv)

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

    # Create and show main window
    window = MainWindow(config)
    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())