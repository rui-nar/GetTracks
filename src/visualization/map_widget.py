"""Map visualization widget for displaying activity tracks."""

import os
import tempfile
from typing import List, Optional, Tuple
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEngineSettings
from PyQt6.QtCore import QUrl

import folium
import polyline as polyline_codec

from src.models.activity import Activity
from src.models.track import Track

# Color per activity type
_TYPE_COLORS = {
    'run':    '#3388ff',
    'ride':   '#e03030',
    'hike':   '#228B22',
    'walk':   '#9932CC',
    'swim':   '#FF8C00',
}
_DEFAULT_COLOR = '#666666'

# Cycling palette for track preview (no activity-type context available)
_TRACK_PALETTE = ['#3388ff', '#e03030', '#228B22', '#9932CC', '#FF8C00', '#1a9850']

# Available tile layers: display name → Folium tile string
_TILE_OPTIONS = {
    'OpenStreetMap':    'OpenStreetMap',
    'CartoDB Positron': 'CartoDB positron',
    'CartoDB Dark':     'CartoDB dark_matter',
}


class MapWidget(QWidget):
    """Widget for displaying activity tracks on an interactive map."""

    def __init__(self):
        super().__init__()
        self._tile_layer: str = 'OpenStreetMap'

        # Last render state — used to re-render when tile layer changes
        # ('empty', None) | ('activities', list) | ('single', activity) | ('tracks', list)
        self._last_render: Tuple = ('empty', None)

        self._setup_ui()
        self.destroyed.connect(self._cleanup_temp_file)
        self._create_empty_map()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def display_activities(self, activities: List[Activity]) -> None:
        """Render all activities as polylines (or markers for indoor ones)."""
        self._last_render = ('activities', activities)
        if not activities:
            self._create_empty_map()
            return

        center = self._calculate_center(activities)
        m = self._base_map(center, zoom_start=12)

        for activity in activities:
            color = _TYPE_COLORS.get(activity.type.lower(), _DEFAULT_COLOR)
            self._add_activity_to_map(m, activity, color, weight=3, opacity=0.7)

        self._display_map(m)

    def display_single_activity(self, activity: Activity) -> None:
        """Render one activity prominently and zoom to fit its route."""
        self._last_render = ('single', activity)
        coords = self._decode_polyline(activity)

        if coords:
            center = self._midpoint(coords)
        elif activity.start_latlng:
            center = (activity.start_latlng[0], activity.start_latlng[1])
        else:
            self._create_empty_map()
            return

        m = self._base_map(center, zoom_start=14)
        color = _TYPE_COLORS.get(activity.type.lower(), _DEFAULT_COLOR)
        self._add_activity_to_map(m, activity, color, weight=5, opacity=1.0,
                                  show_popup=True)

        if coords:
            lats = [c[0] for c in coords]
            lngs = [c[1] for c in coords]
            m.fit_bounds([[min(lats), min(lngs)], [max(lats), max(lngs)]])

        self._display_map(m)

    def display_tracks(self, tracks: List[Track]) -> None:
        """Render full-resolution GPS tracks (e.g. export preview)."""
        self._last_render = ('tracks', tracks)
        if not tracks:
            self._create_empty_map()
            return

        all_coords = [
            (pt.lat, pt.lon)
            for track in tracks
            for pt in track.points
        ]
        if not all_coords:
            self._create_empty_map()
            return

        center = (
            sum(c[0] for c in all_coords) / len(all_coords),
            sum(c[1] for c in all_coords) / len(all_coords),
        )
        m = self._base_map(center, zoom_start=12)

        for i, track in enumerate(tracks):
            coords = [(pt.lat, pt.lon) for pt in track.points]
            if not coords:
                continue
            color = _TRACK_PALETTE[i % len(_TRACK_PALETTE)]
            folium.PolyLine(
                coords,
                color=color,
                weight=4,
                opacity=0.9,
                tooltip=track.activity_name,
            ).add_to(m)
            folium.CircleMarker(
                location=coords[0],
                radius=6,
                color=color,
                fill=True,
                fill_color=color,
                fill_opacity=1.0,
                tooltip=f"Start: {track.activity_name}",
            ).add_to(m)

        lats = [c[0] for c in all_coords]
        lngs = [c[1] for c in all_coords]
        m.fit_bounds([[min(lats), min(lngs)], [max(lats), max(lngs)]])

        self._display_map(m)

    def clear_map(self) -> None:
        self._last_render = ('empty', None)
        self._create_empty_map()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _setup_ui(self):
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
        self._tile_combo.currentIndexChanged.connect(self._on_tile_changed)
        toolbar_layout.addWidget(self._tile_combo)
        toolbar_layout.addStretch()
        outer.addWidget(toolbar)

        # Map view
        self.web_view = QWebEngineView()
        self.web_view.settings().setAttribute(
            QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True
        )
        self.temp_file = None
        outer.addWidget(self.web_view)

    def _on_tile_changed(self, index: int) -> None:
        self._tile_layer = list(_TILE_OPTIONS.values())[index]
        self._re_render()

    def _re_render(self) -> None:
        kind, data = self._last_render
        if kind == 'activities':
            self.display_activities(data)
        elif kind == 'single':
            self.display_single_activity(data)
        elif kind == 'tracks':
            self.display_tracks(data)
        else:
            self._create_empty_map()

    def _base_map(self, center: Tuple[float, float], zoom_start: int) -> folium.Map:
        """Create a Folium map with the current tile as default and others in LayerControl."""
        m = folium.Map(location=center, zoom_start=zoom_start, tiles=self._tile_layer)
        for name, tile in _TILE_OPTIONS.items():
            if tile != self._tile_layer:
                folium.TileLayer(tile, name=name).add_to(m)
        folium.LayerControl().add_to(m)
        return m

    def _create_empty_map(self) -> None:
        m = self._base_map([40.7128, -74.0060], zoom_start=10)
        self._display_map(m)

    def _add_activity_to_map(self, map_obj: folium.Map, activity: Activity,
                              color: str, weight: int = 3, opacity: float = 0.8,
                              show_popup: bool = False) -> None:
        coords = self._decode_polyline(activity)
        tooltip = f"{activity.name} · {activity.type} · {activity.distance/1000:.1f} km"

        if coords:
            folium.PolyLine(
                coords,
                color=color,
                weight=weight,
                opacity=opacity,
                tooltip=tooltip,
            ).add_to(map_obj)

            popup_html = self._build_popup(activity) if show_popup else None
            folium.CircleMarker(
                location=coords[0],
                radius=6,
                color=color,
                fill=True,
                fill_color=color,
                fill_opacity=1.0,
                tooltip="Start",
                popup=folium.Popup(popup_html, max_width=220) if popup_html else None,
            ).add_to(map_obj)

        elif activity.start_latlng:
            popup_html = self._build_popup(activity) if show_popup else tooltip
            folium.Marker(
                location=activity.start_latlng,
                tooltip=tooltip,
                popup=folium.Popup(popup_html, max_width=220),
                icon=folium.Icon(color='gray', icon='info-sign'),
            ).add_to(map_obj)

    @staticmethod
    def _decode_polyline(activity: Activity) -> Optional[List[Tuple[float, float]]]:
        """Return decoded [(lat, lng), …] or None if no polyline available."""
        if not activity.summary_polyline:
            return None
        try:
            coords = polyline_codec.decode(activity.summary_polyline)
            return coords if coords else None
        except Exception:
            return None

    @staticmethod
    def _build_popup(activity: Activity) -> str:
        h, m = divmod(activity.moving_time // 60, 60)
        return (
            f"<div style='font-family:Arial;min-width:160px'>"
            f"<b>{activity.name}</b><br>"
            f"{activity.type} · {activity.start_date_local.strftime('%Y-%m-%d')}<br>"
            f"Distance: {activity.distance/1000:.2f} km<br>"
            f"Time: {h}h {m:02d}m"
            f"</div>"
        )

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

    def _display_map(self, map_obj: folium.Map) -> None:
        if self.temp_file and os.path.exists(self.temp_file):
            try:
                os.unlink(self.temp_file)
            except OSError:
                pass
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
            self.temp_file = f.name
            map_obj.save(f.name)
        self.web_view.setUrl(QUrl.fromLocalFile(self.temp_file))

    def _cleanup_temp_file(self) -> None:
        if self.temp_file and os.path.exists(self.temp_file):
            try:
                os.unlink(self.temp_file)
            except OSError:
                pass
