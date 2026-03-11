"""Map visualization widget for displaying activity tracks."""

import os
import tempfile
from typing import List, Optional
from PyQt6.QtWidgets import QWidget, QVBoxLayout
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEngineSettings
from PyQt6.QtCore import QUrl

import folium
from folium.plugins import MarkerCluster

from src.models.activity import Activity


class MapWidget(QWidget):
    """Widget for displaying activity tracks on an interactive map."""

    def __init__(self):
        super().__init__()
        self.web_view = QWebEngineView()
        self.web_view.settings().setAttribute(
            QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True
        )
        self.current_map = None
        self.temp_file = None

        # Set up layout
        layout = QVBoxLayout(self)
        layout.addWidget(self.web_view)
        layout.setContentsMargins(0, 0, 0, 0)

        self.destroyed.connect(self._cleanup_temp_file)

        # Create initial empty map
        self._create_empty_map()

    def _create_empty_map(self):
        """Create an empty map centered on a default location."""
        # Default to a central location (can be updated based on activities)
        m = folium.Map(
            location=[40.7128, -74.0060],  # New York City as default
            zoom_start=10,
            tiles='OpenStreetMap'
        )

        # Add layer control
        folium.LayerControl().add_to(m)

        self._display_map(m)

    def display_activities(self, activities: List[Activity]):
        """Display multiple activities on the map."""
        if not activities:
            self._create_empty_map()
            return

        # Calculate center point from all activities
        center_lat, center_lng = self._calculate_center(activities)

        # Create map centered on activities
        m = folium.Map(
            location=[center_lat, center_lng],
            zoom_start=12,
            tiles='OpenStreetMap'
        )

        # Add different tile layers
        folium.TileLayer('CartoDB positron').add_to(m)
        folium.TileLayer('CartoDB dark_matter').add_to(m)
        folium.LayerControl().add_to(m)

        # Group activities by type for different colors
        activity_groups = {}
        for activity in activities:
            activity_type = activity.type.lower()
            if activity_type not in activity_groups:
                activity_groups[activity_type] = []
            activity_groups[activity_type].append(activity)

        # Color mapping for different activity types
        colors = {
            'run': 'blue',
            'ride': 'red',
            'hike': 'green',
            'walk': 'purple',
            'swim': 'orange',
            'default': 'gray'
        }

        # Add each activity to the map
        for activity_type, type_activities in activity_groups.items():
            color = colors.get(activity_type, colors['default'])

            for activity in type_activities:
                self._add_activity_to_map(m, activity, color)

        self._display_map(m)

    def display_single_activity(self, activity: Activity):
        """Display a single activity with detailed track."""
        if not activity or not activity.start_latlng:
            self._create_empty_map()
            return

        # For now, just show the start/end points
        # In a full implementation, this would show the GPS track
        m = folium.Map(
            location=[activity.start_latlng[0], activity.start_latlng[1]],
            zoom_start=14,
            tiles='OpenStreetMap'
        )

        info_html = f"""
        <div style="font-family: Arial; max-width: 200px;">
            <h4>{activity.name}</h4>
            <p><strong>Type:</strong> {activity.type}</p>
            <p><strong>Distance:</strong> {activity.distance/1000:.1f} km</p>
            <p><strong>Time:</strong> {activity.moving_time//3600}h {(activity.moving_time%3600)//60}m</p>
            <p><strong>Date:</strong> {activity.start_date_local.strftime('%Y-%m-%d %H:%M')}</p>
        </div>
        """

        folium.Marker(
            location=[activity.start_latlng[0], activity.start_latlng[1]],
            popup=info_html,
            icon=folium.Icon(color='green', icon='play')
        ).add_to(m)

        if activity.end_latlng:
            folium.Marker(
                location=[activity.end_latlng[0], activity.end_latlng[1]],
                popup=f"End: {activity.name}",
                icon=folium.Icon(color='red', icon='stop')
            ).add_to(m)

        self._display_map(m)

    def _add_activity_to_map(self, map_obj: folium.Map, activity: Activity, color: str):
        """Add a single activity to the map."""
        if not activity.start_latlng:
            return

        folium.Marker(
            location=[activity.start_latlng[0], activity.start_latlng[1]],
            popup=f"{activity.name} (Start)",
            icon=folium.Icon(color=color, icon='play')
        ).add_to(map_obj)

        if activity.end_latlng:
            folium.Marker(
                location=[activity.end_latlng[0], activity.end_latlng[1]],
                popup=f"{activity.name} (End)",
                icon=folium.Icon(color=color, icon='stop')
            ).add_to(map_obj)

    def _calculate_center(self, activities: List[Activity]) -> tuple[float, float]:
        """Calculate the center point of all activities."""
        if not activities:
            return 40.7128, -74.0060  # Default to NYC

        total_lat = 0
        total_lng = 0
        count = 0

        for activity in activities:
            if hasattr(activity, 'start_latlng') and activity.start_latlng:
                total_lat += activity.start_latlng[0]
                total_lng += activity.start_latlng[1]
                count += 1

        if count == 0:
            return 40.7128, -74.0060

        return total_lat / count, total_lng / count

    def _display_map(self, map_obj: folium.Map):
        """Display a folium map in the web view."""
        # Clean up previous temp file
        if self.temp_file and os.path.exists(self.temp_file):
            try:
                os.unlink(self.temp_file)
            except:
                pass

        # Save map to temporary HTML file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
            self.temp_file = f.name
            map_obj.save(f.name)

        # Load the HTML file in the web view
        self.web_view.setUrl(QUrl.fromLocalFile(self.temp_file))

    def clear_map(self):
        """Clear the map and show empty state."""
        self._create_empty_map()

    def _cleanup_temp_file(self):
        """Clean up temporary HTML file."""
        if self.temp_file and os.path.exists(self.temp_file):
            try:
                os.unlink(self.temp_file)
            except OSError:
                pass