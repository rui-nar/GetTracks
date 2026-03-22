"""AnimationExportDialog — configure and run video export."""

from __future__ import annotations

import os
from typing import Optional, TYPE_CHECKING

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QFileDialog,
    QFormLayout, QHBoxLayout, QLabel, QLineEdit, QMessageBox,
    QProgressDialog, QPushButton, QVBoxLayout, QWidget,
)

if TYPE_CHECKING:
    from src.animation.animation_state import AnimationState
    from src.animation.animation_canvas import AnimationCanvas


_RESOLUTIONS = {
    "720p  (1280 × 720)":  (1280, 720),
    "1080p (1920 × 1080)": (1920, 1080),
    "480p  (854 × 480)":   (854,  480),
}
_FPS_OPTIONS = [24, 30]


class AnimationExportDialog(QDialog):
    """Modal dialog for configuring and running animation export."""

    def __init__(
        self,
        state: "AnimationState",
        canvas: "AnimationCanvas",
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Export Animation")
        self.setModal(True)
        self.setFixedWidth(440)

        self._state  = state
        self._canvas = canvas

        self._build_ui()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(10)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        # Format
        self._format_combo = QComboBox()
        self._format_combo.addItem("MP4 (H.264)",  "mp4")
        self._format_combo.addItem("GIF (animated)", "gif")
        self._format_combo.currentIndexChanged.connect(self._on_format_changed)
        form.addRow("Format:", self._format_combo)

        # Resolution
        self._res_combo = QComboBox()
        for label in _RESOLUTIONS:
            self._res_combo.addItem(label)
        form.addRow("Resolution:", self._res_combo)

        # FPS
        self._fps_combo = QComboBox()
        for fps in _FPS_OPTIONS:
            self._fps_combo.addItem(f"{fps} fps", fps)
        self._fps_combo.setCurrentIndex(1)   # 30 fps default
        form.addRow("Frame rate:", self._fps_combo)

        # Include elevation
        self._elev_check = QCheckBox("Include elevation strip")
        form.addRow("", self._elev_check)

        root.addLayout(form)

        # Output path
        path_row = QHBoxLayout()
        self._path_edit = QLineEdit()
        self._path_edit.setPlaceholderText("Select output file…")
        path_row.addWidget(self._path_edit)
        browse_btn = QPushButton("Browse…")
        browse_btn.setFixedWidth(80)
        browse_btn.clicked.connect(self._on_browse)
        path_row.addWidget(browse_btn)
        root.addLayout(path_row)

        # Duration info
        total_s = int(self._state.total_duration_seconds / self._state.speed_multiplier)
        fps = _FPS_OPTIONS[self._fps_combo.currentIndex()]
        frames = int(total_s * fps)
        self._info_label = QLabel(
            f"Approx. {total_s}s video · ~{frames} frames"
        )
        self._info_label.setStyleSheet("color: #777; font-size: 11px;")
        root.addWidget(self._info_label)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)
        self._ok_btn = QPushButton("Export")
        self._ok_btn.setDefault(True)
        self._ok_btn.clicked.connect(self._on_export)
        btn_row.addWidget(self._ok_btn)
        root.addLayout(btn_row)

    # ------------------------------------------------------------------
    # Handlers
    # ------------------------------------------------------------------

    def _on_format_changed(self, _: int) -> None:
        fmt = self._format_combo.currentData()
        # Update path extension if already set
        path = self._path_edit.text()
        if path:
            base = os.path.splitext(path)[0]
            self._path_edit.setText(f"{base}.{fmt}")

    def _on_browse(self) -> None:
        fmt = self._format_combo.currentData()
        if fmt == "mp4":
            flt = "MP4 Video (*.mp4)"
        else:
            flt = "Animated GIF (*.gif)"
        path, _ = QFileDialog.getSaveFileName(self, "Save animation", "", flt)
        if path:
            ext = f".{fmt}"
            if not path.lower().endswith(ext):
                path += ext
            self._path_edit.setText(path)

    def _on_export(self) -> None:
        path = self._path_edit.text().strip()
        if not path:
            QMessageBox.warning(self, "No output path", "Please select an output file.")
            return

        fmt  = self._format_combo.currentData()
        res_label = self._res_combo.currentText()
        W, H = _RESOLUTIONS[res_label]
        fps  = self._fps_combo.currentData()
        include_elev = self._elev_check.isChecked()

        # Check dependencies
        if fmt == "mp4":
            try:
                import imageio
                import imageio_ffmpeg  # noqa: F401
            except ImportError:
                QMessageBox.critical(
                    self, "Missing dependency",
                    "MP4 export requires imageio and imageio-ffmpeg.\n\n"
                    "Install with:  pip install imageio imageio-ffmpeg"
                )
                return

        self.accept()
        _run_export(
            state=self._state.copy(),
            canvas=self._canvas,
            path=path,
            fmt=fmt,
            size=QSize(W, H),
            fps=fps,
            include_elev=include_elev,
            parent=self.parent(),
        )


# ---------------------------------------------------------------------------
# Main export runner (called on the GUI thread with a progress dialog)
# ---------------------------------------------------------------------------

def _run_export(
    state: "AnimationState",
    canvas: "AnimationCanvas",
    path: str,
    fmt: str,
    size: QSize,
    fps: int,
    include_elev: bool,
    parent: Optional[QWidget] = None,
) -> None:
    """Render all frames and encode the video.  Runs on the main thread."""
    state.elapsed_seconds = 0.0
    state.paused = False
    state._update_position()

    frame_delta_ms = 1000.0 / fps
    # Video duration = total_duration_seconds / speed_multiplier (real seconds).
    # Each advance(frame_delta_ms) steps forward frame_delta_ms/1000 * speed_multiplier
    # animation-seconds, so total frames = video_duration_s * fps.
    video_duration_s = state.total_duration_seconds / state.speed_multiplier
    total_frames = max(1, int(video_duration_s * fps))

    progress = QProgressDialog(
        "Exporting animation…", "Cancel", 0, total_frames, parent
    )
    progress.setWindowModality(Qt.WindowModality.WindowModal)
    progress.setMinimumDuration(0)
    progress.setValue(0)

    if fmt == "mp4":
        _export_mp4(state, canvas, path, fps, size, total_frames,
                    frame_delta_ms, include_elev, progress)
    else:
        _export_gif(state, canvas, path, fps, size, total_frames,
                    frame_delta_ms, include_elev, progress)

    progress.close()


def _export_mp4(state, canvas, path, fps, size, total_frames,
                frame_delta_ms, include_elev, progress) -> None:
    import imageio

    writer = imageio.get_writer(path, fps=fps, codec="libx264",
                                quality=8, macro_block_size=None)
    try:
        for i in range(total_frames):
            if progress.wasCanceled():
                break
            state.advance(frame_delta_ms)
            img = canvas.render_to_image(size, state)
            arr = _qimage_to_numpy(img)
            writer.append_data(arr)
            progress.setValue(i + 1)
            QApplication.processEvents()
    finally:
        writer.close()


def _export_gif(state, canvas, path, fps, size, total_frames,
                frame_delta_ms, include_elev, progress) -> None:
    from PIL import Image
    frames = []
    # For GIF, cap at reasonable frame count to avoid huge files
    step = max(1, total_frames // 300)
    actual = 0
    for i in range(total_frames):
        if progress.wasCanceled():
            break
        state.advance(frame_delta_ms)
        if i % step != 0:
            continue
        img = canvas.render_to_image(size, state)
        arr = _qimage_to_numpy(img)
        frames.append(Image.fromarray(arr))
        actual += 1
        progress.setValue(i + 1)
        QApplication.processEvents()

    if frames:
        duration_ms = int(1000 / fps) * step
        frames[0].save(
            path,
            save_all=True,
            append_images=frames[1:],
            loop=0,
            duration=duration_ms,
            optimize=False,
        )


def _qimage_to_numpy(img):
    """Convert QImage to a numpy uint8 RGB array."""
    import numpy as np
    from PyQt6.QtGui import QImage
    img = img.convertToFormat(QImage.Format.Format_RGB888)
    ptr = img.bits()
    ptr.setsize(img.sizeInBytes())
    arr = np.frombuffer(ptr, dtype=np.uint8).reshape(img.height(), img.width(), 3)
    return arr.copy()   # detach from Qt memory
