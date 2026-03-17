"""Reorderable project item list with custom delegate and sort controls."""

from __future__ import annotations

from typing import List, Optional

from PyQt6.QtCore import (
    Qt, QModelIndex, QSize, pyqtSignal,
)
from PyQt6.QtGui import QAction, QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import (
    QAbstractItemView, QHBoxLayout, QLabel,
    QListWidget, QListWidgetItem, QMenu, QPushButton,
    QStyledItemDelegate, QStyleOptionViewItem, QVBoxLayout, QWidget,
)

from src.models.activity import Activity
from src.models.great_circle import haversine_km
from src.models.project import ConnectingSegment, Project, ProjectItem

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

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
_TYPE_COLORS = {
    "run":   "#3388ff",
    "ride":  "#e03030",
    "hike":  "#228B22",
    "walk":  "#9932CC",
    "swim":  "#FF8C00",
}
_DEFAULT_TYPE_COLOR = "#666666"

_ROW_HEIGHT = 48
_SEGMENT_BG = QColor("#dce8f0")


# ---------------------------------------------------------------------------
# Delegate
# ---------------------------------------------------------------------------

class _ItemDelegate(QStyledItemDelegate):
    """Custom painter for activity and segment rows."""

    def sizeHint(self, option: QStyleOptionViewItem,
                 index: QModelIndex) -> QSize:  # noqa: N802
        return QSize(option.rect.width(), _ROW_HEIGHT)

    def paint(self, painter: QPainter, option: QStyleOptionViewItem,
              index: QModelIndex) -> None:  # noqa: N802
        item: ProjectItem = index.data(Qt.ItemDataRole.UserRole)
        if item is None:
            super().paint(painter, option, index)
            return

        painter.save()
        rect = option.rect

        # Selection highlight
        from PyQt6.QtWidgets import QStyle
        if option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(rect, QColor("#cce0ff"))
        elif item.item_type == "segment":
            painter.fillRect(rect, _SEGMENT_BG)
        else:
            painter.fillRect(rect, QColor("#ffffff"))

        # Left colour bar
        if item.item_type == "activity":
            bar_color = QColor(_TYPE_COLORS.get(
                (item._activity.type.lower() if item._activity else ""), _DEFAULT_TYPE_COLOR
            ))
        else:
            bar_color = QColor(_SEGMENT_COLORS.get(
                item.segment.segment_type if item.segment else "flight", "#888888"
            ))
        painter.fillRect(rect.x(), rect.y(), 4, rect.height(), bar_color)

        x = rect.x() + 10
        y = rect.y()
        w = rect.width() - 14
        h = rect.height()

        if item.item_type == "activity" and item._activity:
            act = item._activity
            # Icon (type initial)
            icon_font = QFont()
            icon_font.setPointSize(14)
            icon_font.setBold(True)
            painter.setFont(icon_font)
            painter.setPen(bar_color)
            painter.drawText(x, y, 28, h, Qt.AlignmentFlag.AlignVCenter, act.type[0].upper())

            # Name
            name_font = QFont()
            name_font.setPointSize(10)
            name_font.setBold(True)
            painter.setFont(name_font)
            painter.setPen(QColor("#222222"))
            painter.drawText(x + 32, y, w - 32, h // 2, Qt.AlignmentFlag.AlignBottom, act.name)

            # Sub-line: date + distance
            sub_font = QFont()
            sub_font.setPointSize(8)
            painter.setFont(sub_font)
            painter.setPen(QColor("#666666"))
            date_str = act.start_date.strftime("%Y-%m-%d") if act.start_date else ""
            dist_str = f"{act.distance / 1000:.1f} km"
            painter.drawText(x + 32, y + h // 2, w - 32, h // 2,
                             Qt.AlignmentFlag.AlignTop, f"{date_str}  ·  {dist_str}")

        elif item.item_type == "segment" and item.segment:
            seg = item.segment
            icon = _SEGMENT_ICONS.get(seg.segment_type, "•")

            # Icon
            icon_font = QFont()
            icon_font.setPointSize(18)
            painter.setFont(icon_font)
            painter.drawText(x, y, 32, h, Qt.AlignmentFlag.AlignVCenter, icon)

            # Label
            name_font = QFont()
            name_font.setPointSize(10)
            name_font.setItalic(True)
            painter.setFont(name_font)
            painter.setPen(QColor("#333333"))
            label = seg.label or f"{seg.segment_type.capitalize()} segment"
            painter.drawText(x + 36, y, w - 36, h // 2, Qt.AlignmentFlag.AlignBottom, label)

            # Distance
            sub_font = QFont()
            sub_font.setPointSize(8)
            painter.setFont(sub_font)
            painter.setPen(QColor("#666666"))
            try:
                dist_km = haversine_km(seg.start.lat, seg.start.lon,
                                       seg.end.lat, seg.end.lon)
                dist_str = f"≈ {dist_km:.0f} km (great circle)"
            except Exception:
                dist_str = ""
            painter.drawText(x + 36, y + h // 2, w - 36, h // 2,
                             Qt.AlignmentFlag.AlignTop, dist_str)

        painter.restore()


# ---------------------------------------------------------------------------
# ProjectListWidget
# ---------------------------------------------------------------------------

class ProjectListWidget(QWidget):
    """Reorderable project item list with sort toolbar and context menu.

    Signals
    -------
    item_reordered(from_index, to_index)
    item_selected(ProjectItem)
    insert_segment_requested(index)   -- insert *before* this list index
    remove_item_requested(index)
    """

    item_reordered = pyqtSignal(int, int)
    item_selected  = pyqtSignal(object)
    insert_segment_requested = pyqtSignal(int)
    remove_item_requested = pyqtSignal(int)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._project: Optional[Project] = None
        self._suppress_reorder = False
        self._setup_ui()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_project(self, project: Optional[Project]) -> None:
        self._project = project
        self._populate()

    def refresh(self) -> None:
        """Re-render the list from the current project state."""
        self._populate()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        # Sort toolbar
        toolbar = QWidget()
        tl = QHBoxLayout(toolbar)
        tl.setContentsMargins(4, 2, 4, 2)
        tl.addWidget(QLabel("Sort:"))
        btn_date = QPushButton("By Date")
        btn_date.setFixedHeight(24)
        btn_date.clicked.connect(self._sort_by_date)
        btn_name = QPushButton("By Name")
        btn_name.setFixedHeight(24)
        btn_name.clicked.connect(self._sort_by_name)
        tl.addWidget(btn_date)
        tl.addWidget(btn_name)
        tl.addStretch()
        layout.addWidget(toolbar)

        # List
        self._list = QListWidget()
        self._list.setItemDelegate(_ItemDelegate())
        self._list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self._list.setDefaultDropAction(Qt.DropAction.MoveAction)
        self._list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._list.customContextMenuRequested.connect(self._on_context_menu)
        self._list.currentItemChanged.connect(self._on_selection_changed)
        self._list.model().rowsMoved.connect(self._on_rows_moved)
        layout.addWidget(self._list)

    def _populate(self) -> None:
        self._suppress_reorder = True
        self._list.clear()
        if self._project is None:
            self._suppress_reorder = False
            return

        activity_map = {a.id: a for a in self._project.activities}
        for item in self._project.items:
            # Attach resolved activity for delegate painting
            item._activity = activity_map.get(item.activity_id) if item.item_type == "activity" else None
            wi = QListWidgetItem()
            wi.setData(Qt.ItemDataRole.UserRole, item)
            wi.setSizeHint(QSize(0, _ROW_HEIGHT))
            self._list.addItem(wi)
        self._suppress_reorder = False

    def _on_rows_moved(self, _parent, src_start: int, src_end: int,
                       _dest_parent, dest_row: int) -> None:
        if self._suppress_reorder:
            return
        # dest_row is insertion point; adjust to target index
        to_index = dest_row if dest_row <= src_start else dest_row - 1
        self.item_reordered.emit(src_start, to_index)

    def _on_selection_changed(self, current: Optional[QListWidgetItem],
                               _prev) -> None:
        if current is None:
            return
        item: ProjectItem = current.data(Qt.ItemDataRole.UserRole)
        if item is not None:
            self.item_selected.emit(item)

    def _on_context_menu(self, pos) -> None:
        wi = self._list.itemAt(pos)
        index = self._list.row(wi) if wi else self._list.count()

        menu = QMenu(self)
        insert_above = QAction("Insert connecting segment above", self)
        insert_above.triggered.connect(lambda: self.insert_segment_requested.emit(index))
        insert_below = QAction("Insert connecting segment below", self)
        insert_below.triggered.connect(lambda: self.insert_segment_requested.emit(index + 1))
        menu.addAction(insert_above)
        menu.addAction(insert_below)

        if wi is not None:
            menu.addSeparator()
            remove = QAction("Remove from project", self)
            remove.triggered.connect(lambda: self.remove_item_requested.emit(index))
            menu.addAction(remove)

        menu.exec(self._list.mapToGlobal(pos))

    def _sort_by_date(self) -> None:
        if self._project is None:
            return
        self._project.sort_activities_by_date()
        self._populate()
        self.item_reordered.emit(-1, -1)  # sentinel: full reorder

    def _sort_by_name(self) -> None:
        if self._project is None:
            return
        self._project.sort_activities_by_name()
        self._populate()
        self.item_reordered.emit(-1, -1)  # sentinel: full reorder
