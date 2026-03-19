"""Map visualization widget — native Qt slippy map (no WebEngine/Folium).

Public API is identical to the previous Folium-based implementation so the
rest of the application requires no changes.
"""

import os
from typing import List, Optional, Tuple

from PyQt6.QtCore import pyqtSignal, Qt, QSize, QThread
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QSlider, QFrame, QScrollArea, QSizePolicy,
)
from PyQt6.QtGui import QColor, QPixmap, QFont

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


# ---------------------------------------------------------------------------
# Thumbnail loader (shared with WaypointPanel, kept minimal here)
# ---------------------------------------------------------------------------

class _ThumbLoader(QThread):
    loaded = pyqtSignal(str, object)  # url, QPixmap | None

    def __init__(self, urls: list) -> None:
        super().__init__()
        self._urls = urls

    def run(self) -> None:
        import urllib.request
        for url in self._urls:
            if not url:
                self.loaded.emit(url, None)
                continue
            try:
                with urllib.request.urlopen(url, timeout=8) as resp:
                    data = resp.read()
                px = QPixmap()
                px.loadFromData(data)
                self.loaded.emit(url, px if not px.isNull() else None)
            except Exception:
                self.loaded.emit(url, None)


# ---------------------------------------------------------------------------
# Hover tooltip overlay
# ---------------------------------------------------------------------------

class _WaypointTooltip(QFrame):
    """Floating overlay shown while hovering over a waypoint pin."""

    _THUMB_SIZE = 64

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet(
            "QFrame { background: rgba(30,30,30,220); border-radius: 6px; }"
            "QLabel { color: white; }"
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setMaximumWidth(340)
        self.hide()

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 6, 8, 6)
        root.setSpacing(4)

        self._title = QLabel()
        font = QFont()
        font.setBold(True)
        self._title.setFont(font)
        self._title.setWordWrap(True)
        root.addWidget(self._title)

        self._desc = QLabel()
        self._desc.setWordWrap(True)
        self._desc.setMaximumWidth(320)
        root.addWidget(self._desc)

        self._thumb_row = QHBoxLayout()
        self._thumb_row.setSpacing(3)
        root.addLayout(self._thumb_row)

        self._thumb_labels: List[QLabel] = []

    def set_step(self, step: "TripStep", thumb_cache: dict) -> None:
        self._title.setText(step.name)
        desc = (step.description or "").strip()
        self._desc.setText(desc[:200] + ("…" if len(desc) > 200 else ""))
        self._desc.setVisible(bool(desc))

        for lbl in self._thumb_labels:
            self._thumb_row.removeWidget(lbl)
            lbl.deleteLater()
        self._thumb_labels.clear()

        for photo in step.photos[:5]:
            lbl = QLabel()
            lbl.setFixedSize(QSize(self._THUMB_SIZE, self._THUMB_SIZE))
            lbl.setStyleSheet("background: #444; border-radius: 3px;")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            url = photo.thumb_url or photo.url
            px = thumb_cache.get(url)
            if px:
                lbl.setPixmap(px.scaled(self._THUMB_SIZE, self._THUMB_SIZE,
                                        Qt.AspectRatioMode.KeepAspectRatio,
                                        Qt.TransformationMode.SmoothTransformation))
            else:
                lbl.setText("…")
            self._thumb_labels.append(lbl)
            self._thumb_row.addWidget(lbl)

        self._thumb_row.addStretch()
        self.adjustSize()

    def update_thumb(self, url: str, px: QPixmap, step: "TripStep") -> None:
        """Update a thumbnail label if it belongs to the currently shown step."""
        for i, photo in enumerate(step.photos[:5]):
            if (photo.thumb_url or photo.url) == url and i < len(self._thumb_labels):
                lbl = self._thumb_labels[i]
                lbl.setPixmap(px.scaled(self._THUMB_SIZE, self._THUMB_SIZE,
                                        Qt.AspectRatioMode.KeepAspectRatio,
                                        Qt.TransformationMode.SmoothTransformation))
                self.adjustSize()
                break

    def place_near(self, pos, canvas_size) -> None:
        """Position the tooltip near *pos* (QPoint), keeping it on screen."""
        x, y = pos.x() + 16, pos.y() + 16
        if x + self.width()  > canvas_size.width():
            x = pos.x() - self.width() - 8
        if y + self.height() > canvas_size.height():
            y = pos.y() - self.height() - 8
        self.move(max(0, x), max(0, y))


# ---------------------------------------------------------------------------
# MapWidget
# ---------------------------------------------------------------------------

class MapWidget(QWidget):
    """Widget for displaying activity tracks on a native slippy map."""

    waypoint_clicked = pyqtSignal(object)  # TripStep

    def __init__(self) -> None:
        super().__init__()
        self._provider_name: str = 'OpenStreetMap'
        self._last_render: Tuple = ('empty', None)
        self._thumb_cache: dict = {}          # url → QPixmap
        self._hovered_step: Optional[TripStep] = None
        self._thumb_loader: Optional[_ThumbLoader] = None

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
        toolbar_layout.setSpacing(6)
        toolbar_layout.addWidget(QLabel("Tiles:"))
        self._tile_combo = QComboBox()
        for display_name in _TILE_OPTIONS:
            self._tile_combo.addItem(display_name)
        self._tile_combo.currentTextChanged.connect(self._on_tile_changed)
        toolbar_layout.addWidget(self._tile_combo)

        toolbar_layout.addWidget(QLabel("  Points:"))
        self._circle_slider = QSlider(Qt.Orientation.Horizontal)
        self._circle_slider.setRange(2, 14)
        self._circle_slider.setValue(6)
        self._circle_slider.setFixedWidth(70)
        self._circle_slider.setToolTip("Activity start/end point size")
        self._circle_slider.valueChanged.connect(self._on_circle_slider)
        toolbar_layout.addWidget(self._circle_slider)

        toolbar_layout.addWidget(QLabel("  Icons:"))
        self._icon_slider = QSlider(Qt.Orientation.Horizontal)
        self._icon_slider.setRange(4, 24)
        self._icon_slider.setValue(10)
        self._icon_slider.setFixedWidth(70)
        self._icon_slider.setToolTip("Transport segment & waypoint icon size")
        self._icon_slider.valueChanged.connect(self._on_icon_slider)
        toolbar_layout.addWidget(self._icon_slider)

        toolbar_layout.addStretch()
        outer.addWidget(toolbar)

        # Shared caches
        mem_cache  = MemoryTileCache(max_size=512)
        disk_cache = DiskTileCache(_TILE_CACHE_DIR)

        # Map canvas
        self._canvas = MapCanvas(mem_cache=mem_cache, disk_cache=disk_cache,
                                 provider=self._provider_name)
        self._canvas.marker_clicked.connect(self._on_canvas_marker_clicked)
        self._canvas.waypoint_hovered.connect(self._on_waypoint_hovered)
        outer.addWidget(self._canvas)

        # Hover tooltip (child of canvas so it overlays correctly)
        self._tooltip = _WaypointTooltip(self._canvas)

        # Waypoint lookup used by marker click/hover handlers
        self._waypoint_map: dict = {}

    def _on_circle_slider(self, value: int) -> None:
        self._canvas.set_circle_radius(float(value))

    def _on_icon_slider(self, value: int) -> None:
        self._canvas.set_icon_radius(float(value))

    def _on_waypoint_hovered(self, marker) -> None:
        if marker is None:
            self._tooltip.hide()
            self._hovered_step = None
            return

        step = self._waypoint_map.get(marker.waypoint_id)
        if step is None:
            self._tooltip.hide()
            return

        self._hovered_step = step
        self._tooltip.set_step(step, self._thumb_cache)
        cursor_pos = self._canvas.mapFromGlobal(
            self._canvas.cursor().pos()
        )
        self._tooltip.place_near(cursor_pos, self._canvas.size())
        self._tooltip.show()
        self._tooltip.raise_()

        # Kick off thumbnail loading for any uncached photos
        uncached = [
            photo.thumb_url or photo.url
            for photo in step.photos[:5]
            if (photo.thumb_url or photo.url) and (photo.thumb_url or photo.url) not in self._thumb_cache
        ]
        if uncached:
            if self._thumb_loader and self._thumb_loader.isRunning():
                self._thumb_loader.terminate()
            self._thumb_loader = _ThumbLoader(uncached)
            self._thumb_loader.loaded.connect(self._on_thumb_loaded)
            self._thumb_loader.start()

    def _on_thumb_loaded(self, url: str, px) -> None:
        if px:
            self._thumb_cache[url] = px
            if self._hovered_step and self._tooltip.isVisible():
                self._tooltip.update_thumb(url, px, self._hovered_step)
        else:
            self._thumb_cache[url] = None  # mark as tried

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
