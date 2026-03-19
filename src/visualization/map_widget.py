"""Map visualization widget — native Qt slippy map (no WebEngine/Folium).

Public API is identical to the previous Folium-based implementation so the
rest of the application requires no changes.
"""

import os
from typing import List, Optional, Tuple

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox
from PyQt6.QtGui import QColor

import polyline as polyline_codec

from src.models.activity import Activity
from src.models.project import Project
from src.models.track import Track
from src.models.waypoint import TripStep
from src.models.great_circle import great_circle_points
from src.visualization.map_canvas import MapCanvas, Polyline, Marker
from src.visualization.tile_cache import MemoryTileCache, DiskTileCache
from src.visualization.tile_provider import PROVIDERS


# Segment type → color and icon
_SEGMENT_COLORS = {
    "train":  "#8B4513",
    "flight": "#1565C0",
    "boat":   "#00838F",
    "bus":    "#6A1B9A",
}
_SEGMENT_ICONS = {
    "train":  "🚂",
    "flight": "✈",
    "boat":   "⛴",
    "bus":    "🚌",
}

# Color per activity type (same as before)
_TYPE_COLORS = {
    'run':    '#3388ff',
    'ride':   '#e03030',
    'hike':   '#228B22',
    'walk':   '#9932CC',
    'swim':   '#FF8C00',
}
_DEFAULT_COLOR = '#666666'

# Cycling palette for track preview
_TRACK_PALETTE = ['#3388ff', '#e03030', '#228B22', '#9932CC', '#FF8C00', '#1a9850']

# Display name → provider key (must match PROVIDERS in tile_provider.py)
_TILE_OPTIONS = {
    'OpenStreetMap':    'OpenStreetMap',
    'CartoDB Positron': 'CartoDB Positron',
    'CartoDB Dark':     'CartoDB Dark',
}

# Shared tile disk cache stored alongside app data
_TILE_CACHE_DIR = os.path.join(
    os.path.expanduser("~"), ".gettracks", "tile_cache"
)


class MapWidget(QWidget):
    """Widget for displaying activity tracks on a native slippy map."""

    waypoint_clicked = pyqtSignal(object)  # TripStep

    def __init__(self) -> None:
        super().__init__()
        self._provider_name: str = 'OpenStreetMap'

        # Last render state for re-render on tile change
        # ('empty', None) | ('activities', list) | ('single', activity) | ('tracks', list)
        self._last_render: Tuple = ('empty', None)

        self._setup_ui()
        self._create_empty_map()

    # ------------------------------------------------------------------
    # Public API  (same signatures as the old Folium MapWidget)
    # ------------------------------------------------------------------

    def display_activities(self, activities: List[Activity]) -> None:
        """Render all activities as polylines (or markers for indoor ones)."""
        self._last_render = ('activities', activities)
        if not activities:
            self._create_empty_map()
            return

        self._canvas.clear_overlays()

        all_lats, all_lons = [], []
        for activity in activities:
            color = QColor(_TYPE_COLORS.get(activity.type.lower(), _DEFAULT_COLOR))
            coords = self._decode_polyline(activity)
            tooltip = f"{activity.name} · {activity.type} · {activity.distance/1000:.1f} km"
            if coords:
                self._canvas.add_polyline(Polyline(
                    coords=coords, color=color, weight=3, opacity=0.7, tooltip=tooltip
                ))
                self._canvas.add_marker(Marker(
                    lat=coords[0][0], lon=coords[0][1], color=color, tooltip="Start"
                ))
                all_lats += [c[0] for c in coords]
                all_lons += [c[1] for c in coords]
            elif activity.start_latlng:
                lat, lon = activity.start_latlng
                self._canvas.add_marker(Marker(lat=lat, lon=lon, color=color, tooltip=tooltip))
                all_lats.append(lat)
                all_lons.append(lon)

        if all_lats:
            self._canvas.fit_bounds(min(all_lats), max(all_lats), min(all_lons), max(all_lons))
        else:
            self._create_empty_map()

    def display_single_activity(self, activity: Activity) -> None:
        """Render one activity prominently and zoom to fit its route."""
        self._last_render = ('single', activity)
        coords = self._decode_polyline(activity)
        self._canvas.clear_overlays()

        color = QColor(_TYPE_COLORS.get(activity.type.lower(), _DEFAULT_COLOR))
        tooltip = f"{activity.name} · {activity.type} · {activity.distance/1000:.1f} km"

        if coords:
            self._canvas.add_polyline(Polyline(
                coords=coords, color=color, weight=5, opacity=1.0, tooltip=tooltip
            ))
            self._canvas.add_marker(Marker(
                lat=coords[0][0], lon=coords[0][1], color=color, tooltip="Start"
            ))
            lats = [c[0] for c in coords]
            lons = [c[1] for c in coords]
            self._canvas.fit_bounds(min(lats), max(lats), min(lons), max(lons))
        elif activity.start_latlng:
            lat, lon = activity.start_latlng
            self._canvas.add_marker(Marker(lat=lat, lon=lon, color=color, tooltip=tooltip))
            self._canvas.set_view(lat, lon, 14)
        else:
            self._create_empty_map()

    def display_tracks(self, tracks: List[Track]) -> None:
        """Render full-resolution GPS tracks (e.g. export preview)."""
        self._last_render = ('tracks', tracks)
        if not tracks:
            self._create_empty_map()
            return

        self._canvas.clear_overlays()
        all_lats, all_lons = [], []

        for i, track in enumerate(tracks):
            coords = [(pt.lat, pt.lon) for pt in track.points]
            if not coords:
                continue
            color = QColor(_TRACK_PALETTE[i % len(_TRACK_PALETTE)])
            self._canvas.add_polyline(Polyline(
                coords=coords, color=color, weight=4, opacity=0.9,
                tooltip=track.activity_name,
            ))
            self._canvas.add_marker(Marker(
                lat=coords[0][0], lon=coords[0][1], color=color,
                tooltip=f"Start: {track.activity_name}",
            ))
            all_lats += [c[0] for c in coords]
            all_lons += [c[1] for c in coords]

        if all_lats:
            self._canvas.fit_bounds(min(all_lats), max(all_lats), min(all_lons), max(all_lons))
        else:
            self._create_empty_map()

    def display_project(self, project: Project) -> None:
        """Render a project's ordered items (activities + connecting segments)."""
        self._last_render = ('project', project)
        self._canvas.clear_overlays()

        all_lats, all_lons = [], []
        activity_map = {a.id: a for a in project.activities}

        for item in project.items:
            if item.item_type == "activity":
                activity = activity_map.get(item.activity_id)
                if activity is None:
                    continue
                color = QColor(_TYPE_COLORS.get(activity.type.lower(), _DEFAULT_COLOR))
                coords = self._decode_polyline(activity)
                tooltip = f"{activity.name} · {activity.type} · {activity.distance/1000:.1f} km"
                if coords:
                    self._canvas.add_polyline(Polyline(
                        coords=coords, color=color, weight=3, opacity=0.7, tooltip=tooltip
                    ))
                    self._canvas.add_marker(Marker(
                        lat=coords[0][0], lon=coords[0][1], color=color, tooltip="Start"
                    ))
                    all_lats += [c[0] for c in coords]
                    all_lons += [c[1] for c in coords]
                elif activity.start_latlng:
                    lat, lon = activity.start_latlng
                    self._canvas.add_marker(Marker(lat=lat, lon=lon, color=color, tooltip=tooltip))
                    all_lats.append(lat)
                    all_lons.append(lon)

            elif item.item_type == "segment" and item.segment is not None:
                seg = item.segment
                color_hex = _SEGMENT_COLORS.get(seg.segment_type, "#888888")
                color = QColor(color_hex)
                icon = _SEGMENT_ICONS.get(seg.segment_type, "•")
                coords = great_circle_points(
                    seg.start.lat, seg.start.lon,
                    seg.end.lat, seg.end.lon,
                )
                tooltip = f"{icon} {seg.label or seg.segment_type}"
                self._canvas.add_polyline(Polyline(
                    coords=coords, color=color, weight=2, opacity=0.75,
                    dash_pattern=[6.0, 6.0], tooltip=tooltip,
                ))
                mid = coords[len(coords) // 2]
                self._canvas.add_marker(Marker(
                    lat=mid[0], lon=mid[1], color=color, tooltip=tooltip,
                    icon=seg.segment_type,   # key used by draw_transport_icon
                ))
                all_lats += [c[0] for c in coords]
                all_lons += [c[1] for c in coords]

        if all_lats:
            self._canvas.fit_bounds(min(all_lats), max(all_lats), min(all_lons), max(all_lons))
        else:
            self._create_empty_map()

        if project.waypoints:
            self.display_waypoints(project.waypoints)

    def display_activities(self, activities) -> None:
        """Render multiple activities as a combined map view (multi-selection)."""
        self._last_render = ('activities', activities)
        self._canvas.clear_overlays()
        all_lats, all_lons = [], []
        for i, activity in enumerate(activities):
            color = QColor(_TYPE_COLORS.get(activity.type.lower(), _DEFAULT_COLOR))
            coords = self._decode_polyline(activity)
            tooltip = f"{activity.name} · {activity.type} · {activity.distance/1000:.1f} km"
            if coords:
                self._canvas.add_polyline(Polyline(
                    coords=coords, color=color, weight=3, opacity=0.8, tooltip=tooltip
                ))
                self._canvas.add_marker(Marker(
                    lat=coords[0][0], lon=coords[0][1], color=color, tooltip="Start"
                ))
                all_lats += [c[0] for c in coords]
                all_lons += [c[1] for c in coords]
            elif activity.start_latlng:
                lat, lon = activity.start_latlng
                self._canvas.add_marker(Marker(lat=lat, lon=lon, color=color, tooltip=tooltip))
                all_lats.append(lat)
                all_lons.append(lon)
        if all_lats:
            self._canvas.fit_bounds(min(all_lats), max(all_lats), min(all_lons), max(all_lons))
        else:
            self._create_empty_map()

    def display_waypoints(self, steps: List[TripStep]) -> None:
        """Add amber camera-pin markers for each TripStep (does not clear other overlays)."""
        self._waypoint_map = {s.id: s for s in steps}
        amber = QColor("#FF8F00")
        for step in steps:
            self._canvas.add_marker(Marker(
                lat=step.lat,
                lon=step.lon,
                color=amber,
                tooltip=step.name,
                marker_type="waypoint",
                waypoint_id=step.id,
            ))

    def _on_canvas_marker_clicked(self, marker: Marker) -> None:
        if marker.marker_type == "waypoint" and marker.waypoint_id is not None:
            step = self._waypoint_map.get(marker.waypoint_id)
            if step is not None:
                self.waypoint_clicked.emit(step)

    def overlay_segments(self, project) -> None:
        """Add segment arc polylines/markers to the current canvas without clearing it."""
        for item in project.items:
            if item.item_type != "segment" or item.segment is None:
                continue
            seg = item.segment
            color = QColor(_SEGMENT_COLORS.get(seg.segment_type, "#888888"))
            coords = great_circle_points(
                seg.start.lat, seg.start.lon,
                seg.end.lat, seg.end.lon,
            )
            tooltip = seg.label or seg.segment_type
            self._canvas.add_polyline(Polyline(
                coords=coords, color=color, weight=2, opacity=0.75,
                dash_pattern=[6.0, 6.0], tooltip=tooltip,
            ))
            mid = coords[len(coords) // 2]
            self._canvas.add_marker(Marker(
                lat=mid[0], lon=mid[1], color=color,
                tooltip=tooltip, icon=seg.segment_type,
            ))
        self._canvas.update()

    def clear_map(self) -> None:
        self._last_render = ('empty', None)
        self._create_empty_map()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Tile selector toolbar
        toolbar = QWidget()
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(4, 2, 4, 2)
        toolbar_layout.addWidget(QLabel("Tiles:"))
        self._tile_combo = QComboBox()
        for display_name in _TILE_OPTIONS:
            self._tile_combo.addItem(display_name)
        self._tile_combo.currentTextChanged.connect(self._on_tile_changed)
        toolbar_layout.addWidget(self._tile_combo)
        toolbar_layout.addStretch()
        outer.addWidget(toolbar)

        # Shared caches
        mem_cache  = MemoryTileCache(max_size=512)
        disk_cache = DiskTileCache(_TILE_CACHE_DIR)

        # Map canvas
        self._canvas = MapCanvas(mem_cache=mem_cache, disk_cache=disk_cache,
                                 provider=self._provider_name)
        self._canvas.marker_clicked.connect(self._on_canvas_marker_clicked)
        outer.addWidget(self._canvas)

        # Waypoint lookup used by marker click handler
        self._waypoint_map: dict = {}

    def _on_tile_changed(self, display_name: str) -> None:
        provider = _TILE_OPTIONS.get(display_name)
        if provider and provider != self._provider_name:
            self._provider_name = provider
            self._canvas.set_provider(provider)
            self._re_render()

    def _re_render(self) -> None:
        kind, data = self._last_render
        if kind == 'activities':
            self.display_activities(data)
        elif kind == 'single':
            self.display_single_activity(data)
        elif kind == 'tracks':
            self.display_tracks(data)
        elif kind == 'project':
            self.display_project(data)
        else:
            self._create_empty_map()

    def _create_empty_map(self) -> None:
        self._canvas.clear_overlays()
        self._canvas.set_view(40.7128, -74.0060, 10)

    @staticmethod
    def _decode_polyline(activity: Activity) -> Optional[List[Tuple[float, float]]]:
        if not activity.summary_polyline:
            return None
        try:
            coords = polyline_codec.decode(activity.summary_polyline)
            return coords if coords else None
        except Exception:
            return None

    @staticmethod
    def _calculate_center(activities: List[Activity]) -> Tuple[float, float]:
        coords = [a.start_latlng for a in activities if a.start_latlng]
        if not coords:
            return 40.7128, -74.0060
        return (sum(c[0] for c in coords) / len(coords),
                sum(c[1] for c in coords) / len(coords))

    @staticmethod
    def _midpoint(coords: List[Tuple[float, float]]) -> Tuple[float, float]:
        return coords[len(coords) // 2]
