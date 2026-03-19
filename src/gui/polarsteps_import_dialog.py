"""Dialog for importing Polarsteps trips (steps) into the current project.

Left list  = trips fetched from Polarsteps but NOT yet selected
Right list = trips selected for import

The user selects trips and clicks Import. The worker fetches all steps for the
selected trips and calls project.add_waypoints(steps).
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

import re

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog, QDialogButtonBox, QHBoxLayout, QLabel,
    QLineEdit, QListWidget, QListWidgetItem, QProgressBar,
    QPushButton, QVBoxLayout, QWidget,
)

from src.config.settings import Config
from src.gui.polarsteps_settings_dialog import PolarstepsSettingsDialog
from src.gui.workers import FetchPolarstepsTripsWorker, FetchPolarstepsStepsWorker
from src.models.project import Project
from src.polarsteps_api.client import PolarstepsClient


def _trip_label(t: dict) -> str:
    start = t["start_date"].strftime("%Y-%m-%d") if isinstance(t["start_date"], datetime) else "?"
    end   = t["end_date"].strftime("%Y-%m-%d")   if isinstance(t["end_date"],   datetime) else "?"
    return f"{t['name']}  ·  {t['step_count']} steps  ·  {start} → {end}"


def _make_item(trip: dict) -> QListWidgetItem:
    wi = QListWidgetItem(_trip_label(trip))
    wi.setData(Qt.ItemDataRole.UserRole, trip)
    return wi


class PolarstepsImportDialog(QDialog):
    """Modal dialog for selecting Polarsteps trips to import into a project.

    Signals
    -------
    import_complete
        Emitted after steps have been fetched and project.waypoints updated.
    """

    import_complete = pyqtSignal()

    def __init__(
        self,
        project: Project,
        config: Config,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._project = project
        self._config = config
        self._ps_client: Optional[PolarstepsClient] = None

        self.setWindowTitle("Import from Polarsteps")
        self.setMinimumWidth(900)
        self.setMinimumHeight(540)

        self._build_ui()
        self._refresh_auth_status()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(8)

        # ── Auth bar ──────────────────────────────────────────────────
        auth_bar = QHBoxLayout()
        self._connect_btn = QPushButton("Connect to Polarsteps")
        self._connect_btn.setFixedHeight(30)
        self._connect_btn.clicked.connect(self._on_connect)
        auth_bar.addWidget(self._connect_btn)
        self._auth_status = QLabel("○ Not configured")
        self._auth_status.setStyleSheet("color: #666")
        auth_bar.addWidget(self._auth_status)
        auth_bar.addStretch()
        self._fetch_btn = QPushButton("Fetch Trips")
        self._fetch_btn.setFixedHeight(30)
        self._fetch_btn.setEnabled(False)
        self._fetch_btn.clicked.connect(self._on_fetch)
        auth_bar.addWidget(self._fetch_btn)
        root.addLayout(auth_bar)

        # ── Progress / status row ─────────────────────────────────────
        status_row = QHBoxLayout()
        self._progress = QProgressBar()
        self._progress.setFixedHeight(14)
        self._progress.setRange(0, 0)
        self._progress.setVisible(False)
        status_row.addWidget(self._progress, stretch=1)
        self._status_label = QLabel("")
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        status_row.addWidget(self._status_label, stretch=2)
        root.addLayout(status_row)

        # ── Add by URL or ID ──────────────────────────────────────────
        url_row = QHBoxLayout()
        url_row.addWidget(QLabel("Trip URL or ID:"))
        self._url_edit = QLineEdit()
        self._url_edit.setPlaceholderText(
            "e.g. https://www.polarsteps.com/user/12345678-trip-name  or  12345678"
        )
        self._url_edit.returnPressed.connect(self._on_add_by_url)
        url_row.addWidget(self._url_edit, stretch=1)
        add_url_btn = QPushButton("Add")
        add_url_btn.setFixedWidth(50)
        add_url_btn.clicked.connect(self._on_add_by_url)
        url_row.addWidget(add_url_btn)
        root.addLayout(url_row)

        # ── Two-column list area ──────────────────────────────────────
        cols = QHBoxLayout()
        cols.setSpacing(8)

        left_col = QVBoxLayout()
        self._left_label = QLabel("Available trips (0)")
        left_col.addWidget(self._left_label)
        self._left_list = QListWidget()
        self._left_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self._left_list.itemDoubleClicked.connect(self._add_selected)
        left_col.addWidget(self._left_list)
        cols.addLayout(left_col, stretch=5)

        mid_col = QVBoxLayout()
        mid_col.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mid_col.addStretch()
        add_btn = QPushButton("→  Add")
        add_btn.setFixedWidth(90)
        add_btn.clicked.connect(self._add_selected)
        mid_col.addWidget(add_btn)
        remove_btn = QPushButton("←  Remove")
        remove_btn.setFixedWidth(90)
        remove_btn.clicked.connect(self._remove_selected)
        mid_col.addWidget(remove_btn)
        mid_col.addStretch()
        cols.addLayout(mid_col, stretch=2)

        right_col = QVBoxLayout()
        self._right_label = QLabel("Selected trips (0)")
        right_col.addWidget(self._right_label)
        self._right_list = QListWidget()
        self._right_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self._right_list.itemDoubleClicked.connect(self._remove_selected)
        right_col.addWidget(self._right_list)
        cols.addLayout(right_col, stretch=5)

        root.addLayout(cols, stretch=1)

        # ── Bottom buttons ─────────────────────────────────────────────
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        self._import_btn = QPushButton("Import Selection")
        self._import_btn.setDefault(True)
        btns.addButton(self._import_btn, QDialogButtonBox.ButtonRole.AcceptRole)
        btns.rejected.connect(self.reject)
        self._import_btn.clicked.connect(self._on_import)
        root.addWidget(btns)

    # ------------------------------------------------------------------
    # Auth helpers
    # ------------------------------------------------------------------

    def _try_build_client(self) -> bool:
        token = self._config.get("polarsteps.remember_token", "")
        if not token:
            return False
        try:
            self._ps_client = PolarstepsClient(remember_token=token)
            return True
        except Exception:
            return False

    def _refresh_auth_status(self) -> None:
        if self._config.validate_polarsteps_config():
            username = self._config.get("polarsteps.username", "")
            self._auth_status.setText(f"● Configured as {username}")
            self._auth_status.setStyleSheet("color: #2e7d32; font-weight: bold")
            self._fetch_btn.setEnabled(True)
            self._try_build_client()
        else:
            self._auth_status.setText("○ Not configured")
            self._auth_status.setStyleSheet("color: #666")
            self._fetch_btn.setEnabled(False)

    def _on_connect(self) -> None:
        dlg = PolarstepsSettingsDialog(self._config, self)
        if dlg.exec() == PolarstepsSettingsDialog.DialogCode.Accepted:
            self._refresh_auth_status()

    # ------------------------------------------------------------------
    # Add by URL / ID
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_trip_id(text: str) -> Optional[int]:
        """Extract a numeric trip ID from a URL or raw integer string.

        Polarsteps trip URLs look like:
          https://www.polarsteps.com/<user>/<id>-<slug>
        The numeric ID is the first segment of the path component after the username.
        """
        text = text.strip()
        # Try raw integer first
        if text.isdigit():
            return int(text)
        # Extract first long numeric run from URL path (trip IDs are 7-10 digits)
        m = re.search(r'/(\d{5,})', text)
        if m:
            return int(m.group(1))
        return None

    def _on_add_by_url(self) -> None:
        if self._ps_client is None and not self._try_build_client():
            self._status_label.setText("No credentials — click Connect first")
            return
        text = self._url_edit.text()
        trip_id = self._parse_trip_id(text)
        if trip_id is None:
            self._status_label.setText("Could not parse a trip ID from that input")
            return

        # Already in right list?
        if trip_id in self._right_ids():
            self._status_label.setText(f"Trip {trip_id} is already selected")
            return

        self._url_edit.setEnabled(False)
        self._status_label.setText(f"Looking up trip {trip_id}…")

        from src.gui.workers import FetchPolarstepsTripsWorker as _unused  # noqa
        # Use a tiny inline QThread to call get_trip and build the summary dict
        from PyQt6.QtCore import QThread

        ps_client = self._ps_client
        class _LookupWorker(QThread):
            done  = pyqtSignal(dict)
            error = pyqtSignal(str)
            def run(self_w):
                try:
                    resp = ps_client.get_trip(str(trip_id))
                    if not resp.is_success or resp.trip is None:
                        self_w.error.emit(f"Trip {trip_id} not found (status {resp.status_code})")
                        return
                    t = resp.trip
                    self_w.done.emit({
                        "id": t.id,
                        "name": t.name or f"Trip {t.id}",
                        "step_count": t.step_count or 0,
                        "start_date": t.datetime_start,
                        "end_date": t.datetime_end,
                    })
                except Exception as e:
                    self_w.error.emit(str(e))

        self._lookup_worker = _LookupWorker()
        self._lookup_worker.done.connect(self._on_lookup_done)
        self._lookup_worker.error.connect(self._on_lookup_error)
        self._lookup_worker.start()

    def _on_lookup_done(self, trip: dict) -> None:
        self._url_edit.setEnabled(True)
        self._url_edit.clear()
        right_ids = self._right_ids()
        if trip["id"] not in right_ids:
            self._right_list.addItem(_make_item(trip))
            self._update_labels()
            self._status_label.setText(f"Added: {trip['name']}")
        else:
            self._status_label.setText(f"Trip already selected")

    def _on_lookup_error(self, msg: str) -> None:
        self._url_edit.setEnabled(True)
        self._status_label.setText(f"Error: {msg}")

    # ------------------------------------------------------------------
    # Fetch
    # ------------------------------------------------------------------

    def _on_fetch(self) -> None:
        if self._ps_client is None and not self._try_build_client():
            self._status_label.setText("No credentials — click Connect first")
            return
        username = self._config.get("polarsteps.username", "")
        self._fetch_btn.setEnabled(False)
        self._progress.setVisible(True)
        self._status_label.setText("")

        self._fetch_worker = FetchPolarstepsTripsWorker(self._ps_client, username)
        self._fetch_worker.progress.connect(self._status_label.setText)
        self._fetch_worker.finished.connect(self._on_fetch_done)
        self._fetch_worker.error.connect(self._on_fetch_error)
        self._fetch_worker.start()

    def _on_fetch_done(self, trips: List[dict]) -> None:
        self._fetch_btn.setEnabled(True)
        self._progress.setVisible(False)
        right_ids = self._right_ids()
        self._left_list.clear()
        for t in trips:
            if t["id"] not in right_ids:
                self._left_list.addItem(_make_item(t))
        self._update_labels()
        self._status_label.setText(f"{len(trips)} trip(s) found")

    def _on_fetch_error(self, msg: str) -> None:
        self._fetch_btn.setEnabled(True)
        self._progress.setVisible(False)
        self._status_label.setText(f"Error: {msg}")

    # ------------------------------------------------------------------
    # List management
    # ------------------------------------------------------------------

    def _right_ids(self) -> set:
        ids = set()
        for i in range(self._right_list.count()):
            t = self._right_list.item(i).data(Qt.ItemDataRole.UserRole)
            if t:
                ids.add(t["id"])
        return ids

    def _add_selected(self) -> None:
        right_ids = self._right_ids()
        for wi in self._left_list.selectedItems():
            t = wi.data(Qt.ItemDataRole.UserRole)
            if t and t["id"] not in right_ids:
                self._right_list.addItem(_make_item(t))
                right_ids.add(t["id"])
        # Remove added trips from left list
        for wi in self._left_list.selectedItems():
            self._left_list.takeItem(self._left_list.row(wi))
        self._update_labels()

    def _remove_selected(self) -> None:
        for wi in self._right_list.selectedItems():
            t = wi.data(Qt.ItemDataRole.UserRole)
            self._right_list.takeItem(self._right_list.row(wi))
            if t:
                self._left_list.addItem(_make_item(t))
        self._update_labels()

    def _update_labels(self) -> None:
        self._left_label.setText(f"Available trips ({self._left_list.count()})")
        self._right_label.setText(f"Selected trips ({self._right_list.count()})")

    # ------------------------------------------------------------------
    # Import
    # ------------------------------------------------------------------

    def _on_import(self) -> None:
        if self._right_list.count() == 0:
            self.accept()
            return
        if self._ps_client is None and not self._try_build_client():
            self._status_label.setText("No credentials — click Connect first")
            return

        trip_ids: List[int] = []
        trip_names: Dict[int, str] = {}
        for i in range(self._right_list.count()):
            t = self._right_list.item(i).data(Qt.ItemDataRole.UserRole)
            if t:
                trip_ids.append(t["id"])
                trip_names[t["id"]] = t["name"]

        self._import_btn.setEnabled(False)
        self._progress.setVisible(True)
        self._status_label.setText("")

        self._steps_worker = FetchPolarstepsStepsWorker(
            self._ps_client, trip_ids, trip_names
        )
        self._steps_worker.progress.connect(self._status_label.setText)
        self._steps_worker.finished.connect(self._on_steps_done)
        self._steps_worker.error.connect(self._on_steps_error)
        self._steps_worker.start()

    def _on_steps_done(self, steps) -> None:
        self._import_btn.setEnabled(True)
        self._progress.setVisible(False)
        added = self._project.add_waypoints(steps)
        self._status_label.setText(f"Imported {added} step(s)")
        self.import_complete.emit()
        self.accept()

    def _on_steps_error(self, msg: str) -> None:
        self._import_btn.setEnabled(True)
        self._progress.setVisible(False)
        self._status_label.setText(f"Error: {msg}")
