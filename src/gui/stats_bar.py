"""Stats bar widget showing aggregate metrics for the current filtered activity set."""

from typing import List
from PyQt6.QtWidgets import QFrame, QHBoxLayout, QLabel
from PyQt6.QtCore import Qt

from src.models.activity import Activity


def _fmt_time(seconds: int) -> str:
    h = seconds // 3600
    m = (seconds % 3600) // 60
    if h >= 10:
        return f"{h}h"
    if h:
        return f"{h}h {m:02d}m"
    return f"{m}m"


class StatsBarWidget(QFrame):
    """Compact summary bar: count · distance · elevation · time."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet(
            "QFrame { background:#f5f5f5; border-top:1px solid #ddd; }"
            "QLabel { color:#444; font-size:12px; padding:0 4px; }"
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(0)

        self._count_lbl = QLabel("0 activities")
        self._dist_lbl = QLabel()
        self._elev_lbl = QLabel()
        self._time_lbl = QLabel()

        sep = " · "
        for i, lbl in enumerate([self._count_lbl, self._dist_lbl, self._elev_lbl, self._time_lbl]):
            if i:
                layout.addWidget(QLabel(sep))
            layout.addWidget(lbl)

        layout.addStretch()
        self.update_stats([])

    def update_stats(self, activities: List[Activity]) -> None:
        """Recalculate and display aggregate stats for *activities*."""
        n = len(activities)
        self._count_lbl.setText(f"{n} activit{'y' if n == 1 else 'ies'}")

        if not activities:
            for lbl in (self._dist_lbl, self._elev_lbl, self._time_lbl):
                lbl.setText("")
            return

        total_dist_km = sum(a.distance for a in activities) / 1000
        total_elev_m = sum(a.total_elevation_gain for a in activities)
        total_time_s = sum(a.moving_time for a in activities)

        self._dist_lbl.setText(f"{total_dist_km:,.1f} km")
        self._elev_lbl.setText(f"{total_elev_m:,.0f} m ↑")
        self._time_lbl.setText(_fmt_time(total_time_s))
