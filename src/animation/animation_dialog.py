"""AnimationDialog — live trip animation preview with playback controls."""

from __future__ import annotations

import os
from typing import Dict, List, Optional, Set, TYPE_CHECKING

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QFont, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QFrame, QHBoxLayout,
    QLabel, QPushButton, QScrollArea, QSizePolicy, QSlider,
    QSplitter, QVBoxLayout, QWidget,
)

from src.visualization.tile_cache import MemoryTileCache, DiskTileCache
from src.visualization.map_canvas import Polyline, Marker
from src.animation.animation_canvas import AnimationCanvas
from src.animation.animation_state import (
    AnimationState, AnimationSegment,
    _TYPE_COLORS, _SEGMENT_COLORS, _DEFAULT_COLOR,
)
from src.animation.elevation_strip import ElevationStrip

if TYPE_CHECKING:
    from src.models.project import Project
    from src.models.track import Track
    from src.config.settings import Config

_TILE_CACHE_DIR = os.path.join(os.path.expanduser("~"), ".gettracks", "tile_cache")

_SPEED_LABELS   = ["½×",  "1×",  "2×",   "5×",   "10×",  "30×",  "120×"]
_SPEED_MULTIS   = [1800.0, 3600.0, 7200.0, 18000.0, 36000.0, 108000.0, 432000.0]
_DEFAULT_SPEED_IDX = 1   # 1× (1 hour → 1 second)


class AnimationDialog(QDialog):
    """Non-modal dialog that animates the trip on a live map."""

    TIMER_MS = 33   # ~30 fps

    def __init__(
        self,
        project: "Project",
        tracks: Dict[int, "Track"],
        config: "Config",
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Animate — {project.name}")
        self.resize(1100, 720)

        self._project = project
        self._tracks = tracks
        self._config = config
        self._excluded_ids: Set = set()
        self._state: Optional[AnimationState] = None
        self._timer = QTimer(self)
        self._timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._timer.setInterval(self.TIMER_MS)
        self._timer.timeout.connect(self._on_tick)

        self._build_ui()
        self._rebuild_state()
        self._fit_overview()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Left dock — item selector
        dock = self._build_item_dock()
        root.addWidget(dock)

        # Right side — map + controls
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        # Map canvas
        mem_cache  = MemoryTileCache(max_size=512)
        disk_cache = DiskTileCache(_TILE_CACHE_DIR)
        self._canvas = AnimationCanvas(
            mem_cache=mem_cache,
            disk_cache=disk_cache,
            provider="OpenStreetMap",
        )
        self._canvas.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        right_layout.addWidget(self._canvas, stretch=1)

        # Elevation strip
        self._elev_strip = ElevationStrip()
        self._elev_strip.setVisible(False)
        right_layout.addWidget(self._elev_strip)

        # Controls
        controls = self._build_controls()
        right_layout.addWidget(controls)

        root.addWidget(right, stretch=1)

        # Keyboard shortcuts
        QShortcut(QKeySequence(Qt.Key.Key_Space), self, self._on_play_pause)
        QShortcut(QKeySequence(Qt.Key.Key_Escape), self, self.close)

    def _build_item_dock(self) -> QWidget:
        dock = QFrame()
        dock.setFixedWidth(190)
        dock.setFrameShape(QFrame.Shape.StyledPanel)

        layout = QVBoxLayout(dock)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        header = QLabel("Items to animate")
        font = QFont()
        font.setBold(True)
        header.setFont(font)
        layout.addWidget(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        inner = QWidget()
        self._item_layout = QVBoxLayout(inner)
        self._item_layout.setContentsMargins(0, 0, 0, 0)
        self._item_layout.setSpacing(2)
        scroll.setWidget(inner)
        layout.addWidget(scroll, stretch=1)

        # Populate checkboxes
        self._item_checks: List[QCheckBox] = []
        for item in self._project.items:
            if item.item_type == "activity" and item.activity_id is not None:
                act = self._project.activity_by_id(item.activity_id)
                if act is None:
                    continue
                label = act.name or act.type
                cb = QCheckBox(label)
                cb.setChecked(True)
                cb.setProperty("item_id", item.activity_id)
                cb.setProperty("item_kind", "activity")
                cb.toggled.connect(self._on_item_toggled)
                self._item_checks.append(cb)
                self._item_layout.addWidget(cb)
            elif item.item_type == "segment" and item.segment is not None:
                seg = item.segment
                label = seg.label or seg.segment_type
                cb = QCheckBox(label)
                cb.setChecked(True)
                cb.setProperty("item_id", seg.id)
                cb.setProperty("item_kind", "segment")
                cb.toggled.connect(self._on_item_toggled)
                self._item_checks.append(cb)
                self._item_layout.addWidget(cb)

        self._item_layout.addStretch()
        return dock

    def _build_controls(self) -> QWidget:
        panel = QFrame()
        panel.setFrameShape(QFrame.Shape.StyledPanel)
        vbox = QVBoxLayout(panel)
        vbox.setContentsMargins(6, 4, 6, 4)
        vbox.setSpacing(4)

        # Top row: play/pause, rewind, speed, camera, elevation, export
        top = QHBoxLayout()

        self._play_btn = QPushButton("▶  Play")
        self._play_btn.setFixedWidth(90)
        self._play_btn.clicked.connect(self._on_play_pause)
        top.addWidget(self._play_btn)

        rewind_btn = QPushButton("⏮")
        rewind_btn.setFixedWidth(36)
        rewind_btn.setToolTip("Rewind to start")
        rewind_btn.clicked.connect(self._on_rewind)
        top.addWidget(rewind_btn)

        top.addSpacing(12)

        top.addWidget(QLabel("Speed:"))
        self._speed_combo = QComboBox()
        for lbl in _SPEED_LABELS:
            self._speed_combo.addItem(lbl)
        self._speed_combo.setCurrentIndex(_DEFAULT_SPEED_IDX)
        self._speed_combo.currentIndexChanged.connect(self._on_speed_changed)
        top.addWidget(self._speed_combo)

        top.addSpacing(12)

        top.addWidget(QLabel("Camera:"))
        self._camera_combo = QComboBox()
        self._camera_combo.addItem("Follow icon")
        self._camera_combo.addItem("Overview")
        self._camera_combo.currentIndexChanged.connect(self._on_camera_changed)
        top.addWidget(self._camera_combo)

        top.addSpacing(12)

        self._elev_check = QCheckBox("Elevation")
        self._elev_check.toggled.connect(self._on_elev_toggled)
        top.addWidget(self._elev_check)

        top.addStretch()

        self._export_btn = QPushButton("Export…")
        self._export_btn.clicked.connect(self._on_export)
        top.addWidget(self._export_btn)

        vbox.addLayout(top)

        # Scrubber
        self._scrubber = QSlider(Qt.Orientation.Horizontal)
        self._scrubber.setRange(0, 1000)
        self._scrubber.setValue(0)
        self._scrubber.sliderMoved.connect(self._on_scrubber_moved)
        vbox.addWidget(self._scrubber)

        # Status label
        self._status_label = QLabel("Ready")
        self._status_label.setStyleSheet("color: #555; font-size: 12px;")
        vbox.addWidget(self._status_label)

        return panel

    # ------------------------------------------------------------------
    # State management
    # ------------------------------------------------------------------

    def _rebuild_state(self) -> None:
        """Rebuild AnimationState from current project + exclusions."""
        speeds = self._config.get_animation_speeds() if self._config else None
        self._state = AnimationState.build_from_project(
            self._project, self._tracks, self._excluded_ids,
            segment_speeds=speeds,
        )
        if self._state is not None:
            self._state.speed_multiplier = _SPEED_MULTIS[self._speed_combo.currentIndex()]
            # Wire elevation data
            self._sync_elevation()
        self._update_status()
        self._canvas.set_animation_state(self._state)

    def _sync_elevation(self) -> None:
        """Attach elevation arrays to segments and update the strip."""
        if self._state is None:
            return
        for seg in self._state.segments:
            if seg.activity_id is not None:
                track = self._tracks.get(seg.activity_id)
                if track:
                    elevations = [pt.elevation for pt in track.points]
                    seg._elevations = elevations  # type: ignore[attr-defined]
        if self._elev_check.isChecked():
            self._elev_strip.set_segments(self._state.segments)

    def _fit_overview(self) -> None:
        """Fit the camera to show all active segments."""
        if self._state is None or not self._state.segments:
            return
        all_lats = [lat for seg in self._state.segments for lat, lon in seg.coords]
        all_lons = [lon for seg in self._state.segments for lat, lon in seg.coords]
        if all_lats:
            self._canvas.fit_bounds(
                min(all_lats), max(all_lats), min(all_lons), max(all_lons)
            )
            self._canvas._follow_zoom = self._canvas._tile_zoom

        # Draw the full route as dim polylines
        self._canvas.clear_overlays()
        if self._state:
            for seg in self._state.segments:
                color = QColor(*seg.color)
                color.setAlphaF(0.5)
                self._canvas.add_polyline(Polyline(
                    coords=seg.coords,
                    color=color,
                    weight=2.5,
                    opacity=0.5,
                ))

    # ------------------------------------------------------------------
    # Timer tick
    # ------------------------------------------------------------------

    def _on_tick(self) -> None:
        if self._state is None:
            return
        self._state.advance(self.TIMER_MS)

        if self._camera_combo.currentIndex() == 0:   # Follow
            self._canvas.follow_current_position()
        else:
            self._canvas.set_animation_state(self._state)

        if self._elev_check.isChecked():
            self._elev_strip.set_playhead(self._state.distance_fraction)

        # Update scrubber (block signals to avoid feedback loop)
        self._scrubber.blockSignals(True)
        self._scrubber.setValue(int(self._state.fraction * 1000))
        self._scrubber.blockSignals(False)

        self._update_status()

        if self._state.is_finished:
            self._timer.stop()
            self._state.paused = True
            self._play_btn.setText("▶  Play")

    # ------------------------------------------------------------------
    # Control handlers
    # ------------------------------------------------------------------

    def _on_play_pause(self) -> None:
        if self._state is None:
            return
        if self._state.is_finished:
            self._on_rewind()
        self._state.paused = not self._state.paused
        if self._state.paused:
            self._timer.stop()
            self._play_btn.setText("▶  Play")
        else:
            self._timer.start()
            self._play_btn.setText("⏸  Pause")

    def _on_rewind(self) -> None:
        if self._state is None:
            return
        self._state.elapsed_seconds = 0.0
        self._state._update_position()
        self._scrubber.setValue(0)
        self._canvas.set_animation_state(self._state)
        self._elev_strip.set_playhead(0.0)
        self._update_status()
        if self._camera_combo.currentIndex() == 0:
            self._fit_overview()

    def _on_speed_changed(self, index: int) -> None:
        if self._state is not None:
            self._state.speed_multiplier = _SPEED_MULTIS[index]

    def _on_camera_changed(self, index: int) -> None:
        mode = "follow" if index == 0 else "overview"
        self._canvas.set_camera_mode(mode)
        if mode == "overview":
            self._fit_overview()

    def _on_elev_toggled(self, checked: bool) -> None:
        self._elev_strip.setVisible(checked)
        if checked and self._state:
            self._sync_elevation()
            self._elev_strip.set_playhead(self._state.distance_fraction)

    def _on_scrubber_moved(self, value: int) -> None:
        if self._state is None:
            return
        self._state.seek(value / 1000.0)
        self._canvas.set_animation_state(self._state)
        if self._elev_check.isChecked():
            self._elev_strip.set_playhead(self._state.distance_fraction)
        self._update_status()

    def _on_item_toggled(self) -> None:
        self._excluded_ids = set()
        for cb in self._item_checks:
            if not cb.isChecked():
                self._excluded_ids.add(cb.property("item_id"))
        was_playing = self._timer.isActive()
        self._timer.stop()
        self._rebuild_state()
        self._fit_overview()
        if was_playing and self._state:
            self._state.paused = False
            self._timer.start()

    def _on_export(self) -> None:
        if self._state is None:
            return
        # Pause during export
        was_playing = self._timer.isActive()
        self._timer.stop()

        from src.animation.export_dialog import AnimationExportDialog
        dlg = AnimationExportDialog(self._state, self._canvas, parent=self)
        dlg.exec()

        if was_playing and self._state and not self._state.is_finished:
            self._state.paused = False
            self._timer.start()

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def _update_status(self) -> None:
        if self._state is None:
            self._status_label.setText("No animatable items in selection")
            self._play_btn.setEnabled(False)
            self._export_btn.setEnabled(False)
            return

        self._play_btn.setEnabled(True)
        self._export_btn.setEnabled(True)

        elapsed = self._state.elapsed_seconds
        total   = self._state.total_duration_seconds
        e_h, e_rem = divmod(int(elapsed), 3600)
        e_m, e_s   = divmod(e_rem, 60)
        t_h, t_rem = divmod(int(total),   3600)
        t_m, t_s   = divmod(t_rem, 60)
        time_str = (
            f"{e_h:02d}:{e_m:02d}:{e_s:02d} / {t_h:02d}:{t_m:02d}:{t_s:02d}"
        )

        si = self._state.segment_index
        seg = self._state.segments[si]
        n = len(self._state.segments)
        seg_str = f"  •  {si + 1}/{n}: {seg.label}"

        self._status_label.setText(time_str + seg_str)

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def closeEvent(self, event) -> None:
        self._timer.stop()
        super().closeEvent(event)
