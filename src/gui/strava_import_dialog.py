"""Dialog for importing Strava activities into the current project.

Left list  = activities fetched from Strava but NOT yet in project.items
Right list = activities currently selected for the project (activity items only)

The user moves activities between the two lists via arrow buttons or double-click,
then clicks "Import Selection" to commit the changes to project.items.
Cancel leaves project.items unchanged (but any fetched activities are kept in
project.activities as an offline cache).
"""

from __future__ import annotations

from datetime import date
from typing import Dict, List, Optional, Set

from PyQt6.QtCore import Qt, QDate, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox, QDateEdit, QDialog, QDialogButtonBox,
    QGroupBox, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QProgressBar, QPushButton, QVBoxLayout, QWidget,
)

from src.api.strava_client import StravaAPI
from src.filters.filter_engine import FilterCriteria, FilterEngine
from src.models.activity import Activity
from src.models.project import Project, ProjectItem
from src.gui.workers import FetchActivitiesWorker, OAuthAuthenticationWorker

_DEFAULT_START = QDate(2010, 1, 1)


# ---------------------------------------------------------------------------
# Helper — row format
# ---------------------------------------------------------------------------

def _activity_label(a: Activity) -> str:
    date_str = a.start_date_local.strftime("%Y-%m-%d") if a.start_date_local else "?"
    dist_str = f"{a.distance / 1000:.1f} km"
    return f"{a.name}  ·  {a.type}  ·  {dist_str}  ·  {date_str}"


def _make_item(activity: Activity) -> QListWidgetItem:
    wi = QListWidgetItem(_activity_label(activity))
    wi.setData(Qt.ItemDataRole.UserRole, activity)
    return wi


# ---------------------------------------------------------------------------
# Dialog
# ---------------------------------------------------------------------------

class StravaImportDialog(QDialog):
    """Modal dialog for importing / managing Strava activities in a project.

    Signals
    -------
    import_complete
        Emitted after the user confirms Import Selection and project.items
        has been updated.  The caller should mark the project dirty and
        refresh the project list widget.
    """

    import_complete = pyqtSignal()

    def __init__(
        self,
        project: Project,
        api_client: StravaAPI,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._project = project
        self._api_client = api_client
        self._type_checkboxes: Dict[str, QCheckBox] = {}

        self.setWindowTitle("Import from Strava")
        self.setMinimumWidth(960)
        self.setMinimumHeight(620)

        self._build_ui()
        self._populate_from_project()
        self._refresh_auth_status()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(8)

        # ── Auth bar ──────────────────────────────────────────────────
        auth_bar = QHBoxLayout()
        self._auth_btn = QPushButton("Connect to Strava")
        self._auth_btn.setFixedHeight(30)
        self._auth_btn.clicked.connect(self._on_authenticate)
        auth_bar.addWidget(self._auth_btn)
        self._auth_status = QLabel("○ Not connected")
        self._auth_status.setStyleSheet("color: #666")
        auth_bar.addWidget(self._auth_status)
        auth_bar.addStretch()
        self._fetch_btn = QPushButton("Fetch Activities")
        self._fetch_btn.setFixedHeight(30)
        self._fetch_btn.setEnabled(False)
        self._fetch_btn.clicked.connect(self._on_fetch)
        auth_bar.addWidget(self._fetch_btn)
        root.addLayout(auth_bar)

        # ── Fetch status row ──────────────────────────────────────────
        fetch_status_row = QHBoxLayout()
        self._progress = QProgressBar()
        self._progress.setFixedHeight(14)
        self._progress.setRange(0, 0)
        self._progress.setVisible(False)
        fetch_status_row.addWidget(self._progress, stretch=1)
        self._fetch_status = QLabel("")
        self._fetch_status.setAlignment(Qt.AlignmentFlag.AlignRight)
        fetch_status_row.addWidget(self._fetch_status, stretch=2)
        root.addLayout(fetch_status_row)

        # ── Filter bar ────────────────────────────────────────────────
        filter_box = QGroupBox("Filters  (affect Available list only)")
        fl = QVBoxLayout(filter_box)
        fl.setSpacing(4)

        date_row = QHBoxLayout()
        date_row.addWidget(QLabel("From:"))
        self._start_date = QDateEdit()
        self._start_date.setDisplayFormat("yyyy-MM-dd")
        self._start_date.setDate(_DEFAULT_START)
        date_row.addWidget(self._start_date)
        date_row.addWidget(QLabel("To:"))
        self._end_date = QDateEdit()
        self._end_date.setDisplayFormat("yyyy-MM-dd")
        self._end_date.setDate(QDate.currentDate())
        date_row.addWidget(self._end_date)
        apply_btn = QPushButton("Apply")
        apply_btn.setFixedWidth(60)
        apply_btn.clicked.connect(self._refresh_left_list)
        date_row.addWidget(apply_btn)
        date_row.addStretch()
        fl.addLayout(date_row)

        self._types_row = QHBoxLayout()
        self._types_row.setSpacing(6)
        self._types_row.addWidget(QLabel("Types:"))
        self._types_row.addStretch()
        fl.addLayout(self._types_row)
        root.addWidget(filter_box)

        # ── Three-column main area ─────────────────────────────────────
        cols = QHBoxLayout()
        cols.setSpacing(8)

        # Left: available
        left_col = QVBoxLayout()
        self._left_label = QLabel("Available from Strava (0)")
        left_col.addWidget(self._left_label)
        self._left_list = QListWidget()
        self._left_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self._left_list.itemDoubleClicked.connect(self._add_selected)
        left_col.addWidget(self._left_list)
        cols.addLayout(left_col, stretch=5)

        # Middle: controls
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

        # Right: in project
        right_col = QVBoxLayout()
        self._right_label = QLabel("In project (0)")
        right_col.addWidget(self._right_label)
        self._right_list = QListWidget()
        self._right_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self._right_list.itemDoubleClicked.connect(self._remove_selected)
        right_col.addWidget(self._right_list)
        cols.addLayout(right_col, stretch=5)

        root.addLayout(cols, stretch=1)

        # ── Bottom buttons ─────────────────────────────────────────────
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel
        )
        self._import_btn = QPushButton("Import Selection")
        self._import_btn.setDefault(True)
        btns.addButton(self._import_btn, QDialogButtonBox.ButtonRole.AcceptRole)
        btns.rejected.connect(self.reject)
        self._import_btn.clicked.connect(self._on_import)
        root.addWidget(btns)

    # ------------------------------------------------------------------
    # Initialisation helpers
    # ------------------------------------------------------------------

    def _populate_from_project(self) -> None:
        """Pre-fill right list from project.items; left list from remaining cache."""
        # IDs currently in project items
        project_ids: Set[int] = {
            it.activity_id
            for it in self._project.items
            if it.item_type == "activity" and it.activity_id is not None
        }
        act_map: Dict[int, Activity] = {a.id: a for a in self._project.activities}

        # Right list = activities currently in project
        for aid in project_ids:
            act = act_map.get(aid)
            if act:
                self._right_list.addItem(_make_item(act))

        self._update_labels()

        # Left list will be built by _refresh_left_list once cache is available
        self._refresh_left_list()

        # Update fetch button label
        self._update_fetch_button_label()

    def _refresh_auth_status(self) -> None:
        if self._api_client.token_data:
            athlete = self._api_client.token_data.get("athlete", {})
            if athlete:
                name = (athlete.get("firstname", "") + " " + athlete.get("lastname", "")).strip()
            else:
                name = ""
            self._auth_status.setText(f"● Connected{' as ' + name if name else ''}")
            self._auth_status.setStyleSheet("color: #2e7d32; font-weight: bold")
            self._fetch_btn.setEnabled(True)
        else:
            self._auth_status.setText("○ Not connected")
            self._auth_status.setStyleSheet("color: #666")
            self._fetch_btn.setEnabled(False)

    def _update_fetch_button_label(self) -> None:
        if self._project.activities:
            most_recent = max(
                (a.start_date for a in self._project.activities if a.start_date),
                default=None,
            )
            label = "Sync New"
            if most_recent:
                label += f"\n(since {most_recent.strftime('%Y-%m-%d')})"
            self._fetch_btn.setText(label)
        else:
            self._fetch_btn.setText("Fetch Activities")

    # ------------------------------------------------------------------
    # Filter helpers
    # ------------------------------------------------------------------

    def _populate_type_checkboxes(self, activities: List[Activity]) -> None:
        for cb in self._type_checkboxes.values():
            self._types_row.removeWidget(cb)
            cb.deleteLater()
        self._type_checkboxes.clear()

        stretch_index = self._types_row.count() - 1
        for i, t in enumerate(FilterEngine.extract_activity_types(activities)):
            cb = QCheckBox(t)
            cb.setChecked(True)
            self._types_row.insertWidget(stretch_index + i, cb)
            self._type_checkboxes[t] = cb

    def _build_criteria(self) -> FilterCriteria:
        start: date = self._start_date.date().toPyDate()
        end: date   = self._end_date.date().toPyDate()
        selected: Optional[Set[str]] = None
        if self._type_checkboxes:
            checked = {t for t, cb in self._type_checkboxes.items() if cb.isChecked()}
            if len(checked) < len(self._type_checkboxes):
                selected = checked
        return FilterCriteria(start_date=start, end_date=end, activity_types=selected)

    # ------------------------------------------------------------------
    # List management
    # ------------------------------------------------------------------

    def _right_ids(self) -> Set[int]:
        ids: Set[int] = set()
        for i in range(self._right_list.count()):
            act: Activity = self._right_list.item(i).data(Qt.ItemDataRole.UserRole)
            if act:
                ids.add(act.id)
        return ids

    def _refresh_left_list(self) -> None:
        """Rebuild left list: cached activities not in right list, filtered."""
        right_ids = self._right_ids()
        criteria = self._build_criteria()
        available = [
            a for a in self._project.activities
            if a.id not in right_ids
        ]
        filtered = FilterEngine().apply(available, criteria)
        filtered_sorted = sorted(
            filtered,
            key=lambda a: a.start_date or date.min,
            reverse=True,
        )
        self._left_list.clear()
        for act in filtered_sorted:
            self._left_list.addItem(_make_item(act))
        self._update_labels()

    def _update_labels(self) -> None:
        self._left_label.setText(f"Available from Strava ({self._left_list.count()})")
        self._right_label.setText(f"In project ({self._right_list.count()})")

    def _add_selected(self) -> None:
        right_ids = self._right_ids()
        skipped = 0
        for wi in self._left_list.selectedItems():
            act: Activity = wi.data(Qt.ItemDataRole.UserRole)
            if act and act.id not in right_ids:
                self._right_list.addItem(_make_item(act))
                right_ids.add(act.id)
            elif act:
                skipped += 1
        if skipped:
            self._fetch_status.setText(
                f"{skipped} activit{'y' if skipped == 1 else 'ies'} already in project — skipped"
            )
        self._refresh_left_list()

    def _remove_selected(self) -> None:
        for wi in self._right_list.selectedItems():
            self._right_list.takeItem(self._right_list.row(wi))
        self._refresh_left_list()

    # ------------------------------------------------------------------
    # Auth
    # ------------------------------------------------------------------

    def _on_authenticate(self) -> None:
        self._auth_btn.setEnabled(False)
        self._auth_status.setText("Opening browser…")
        self._auth_worker = OAuthAuthenticationWorker(self._api_client)
        self._auth_worker.progress.connect(self._auth_status.setText)
        self._auth_worker.finished.connect(self._on_auth_done)
        self._auth_worker.error.connect(self._on_auth_error)
        self._auth_worker.start()

    def _on_auth_done(self, _token_data: dict) -> None:
        self._auth_btn.setEnabled(True)
        self._refresh_auth_status()

    def _on_auth_error(self, msg: str) -> None:
        self._auth_btn.setEnabled(True)
        self._auth_status.setText(f"Auth failed: {msg}")

    # ------------------------------------------------------------------
    # Fetch
    # ------------------------------------------------------------------

    def _on_fetch(self) -> None:
        after_date = None
        if self._project.activities:
            after_date = max(
                (a.start_date for a in self._project.activities if a.start_date),
                default=None,
            )
        self._fetch_btn.setEnabled(False)
        self._progress.setVisible(True)
        self._fetch_status.setText("")

        self._fetch_worker = FetchActivitiesWorker(self._api_client, after_date=after_date)
        self._fetch_worker.progress.connect(self._fetch_status.setText)
        self._fetch_worker.finished.connect(self._on_fetch_done)
        self._fetch_worker.error.connect(self._on_fetch_error)
        self._fetch_worker.start()

    def _on_fetch_done(self, activities: List[Activity]) -> None:
        self._fetch_btn.setEnabled(True)
        self._progress.setVisible(False)
        added = self._project.add_activities(activities)
        self._fetch_status.setText(
            f"{added} new activit{'y' if added == 1 else 'ies'} found"
            if added else "Already up to date"
        )
        self._populate_type_checkboxes(self._project.activities)
        self._refresh_left_list()
        self._update_fetch_button_label()

    def _on_fetch_error(self, msg: str) -> None:
        self._fetch_btn.setEnabled(True)
        self._progress.setVisible(False)
        # Show a concise, actionable message for auth failures
        if "invalid or expired" in msg or "re-authenticate" in msg.lower() or "401" in msg:
            self._fetch_status.setText(
                "Token expired — click \"Connect to Strava\" to reconnect"
            )
            self._auth_btn.setEnabled(True)
            self._auth_status.setText("○ Not connected")
            self._auth_status.setStyleSheet("color: #666")
            self._fetch_btn.setEnabled(False)
        else:
            self._fetch_status.setText(f"Error: {msg}")

    # ------------------------------------------------------------------
    # Import
    # ------------------------------------------------------------------

    def _on_import(self) -> None:
        """Commit the right-list state to project.items and emit import_complete."""
        desired_ids: List[int] = []
        for i in range(self._right_list.count()):
            act: Activity = self._right_list.item(i).data(Qt.ItemDataRole.UserRole)
            if act:
                desired_ids.append(act.id)
        desired_set = set(desired_ids)

        # Current activity IDs in project.items
        current_ids = {
            it.activity_id
            for it in self._project.items
            if it.item_type == "activity" and it.activity_id is not None
        }

        # Remove items that were moved back to the left list
        removed_ids = current_ids - desired_set
        self._project.items = [
            it for it in self._project.items
            if not (it.item_type == "activity" and it.activity_id in removed_ids)
        ]

        # Append newly added activities (date-sorted)
        added_ids = desired_set - current_ids
        act_map = {a.id: a for a in self._project.activities}
        new_items = sorted(
            [act_map[aid] for aid in added_ids if aid in act_map],
            key=lambda a: a.start_date,
        )
        for act in new_items:
            self._project.items.append(
                ProjectItem(item_type="activity", activity_id=act.id)
            )

        self.import_complete.emit()
        self.accept()
