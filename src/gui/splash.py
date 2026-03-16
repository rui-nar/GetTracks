"""Splash screen with a programmatically-generated GPS-track merging image."""

from PyQt6.QtWidgets import QSplashScreen
from PyQt6.QtGui import (
    QPixmap, QPainter, QPainterPath, QPen, QColor,
    QLinearGradient, QFont, QFontMetrics,
)
from PyQt6.QtCore import Qt, QPointF


# ---------------------------------------------------------------------------
# Image generation
# ---------------------------------------------------------------------------

_BG_TOP    = QColor("#0d1b2a")
_BG_BOT    = QColor("#1b2838")
_TRACKS = [
    # (color,  [(x, y), …])  — all points in a 600×300 canvas
    ("#4fc3f7", [(0, 28),  (90, 28),  (160, 72),  (260, 72),
                 (330, 108), (420, 128), (490, 148)]),              # sky-blue
    ("#ef5350", [(0, 148), (70, 148), (130, 158), (210, 158),
                 (300, 152), (410, 150), (490, 148)]),              # red
    ("#66bb6a", [(0, 268), (100, 268), (165, 218), (255, 198),
                 (355, 178), (430, 162), (490, 148)]),              # green
    ("#ab47bc", [(0, 198), (88, 198), (148, 188), (248, 174),
                 (375, 160), (435, 154), (490, 148)]),              # purple
    ("#ffa726", [(0, 108), (80, 108), (145, 88),  (235, 90),
                 (315, 114), (415, 136), (490, 148)]),              # orange
]
_MERGE_X  = 490
_MERGE_Y  = 148
_EXIT_END = (600, 148)
_W, _H    = 600, 300


def _make_splash_pixmap() -> QPixmap:
    pixmap = QPixmap(_W, _H)

    p = QPainter(pixmap)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    # Background gradient
    bg = QLinearGradient(0, 0, 0, _H)
    bg.setColorAt(0, _BG_TOP)
    bg.setColorAt(1, _BG_BOT)
    p.fillRect(0, 0, _W, _H, bg)

    # Subtle grid (very faint)
    p.setPen(QPen(QColor(255, 255, 255, 12), 1))
    for x in range(0, _W, 40):
        p.drawLine(x, 0, x, _H)
    for y in range(0, _H, 40):
        p.drawLine(0, y, _W, y)

    # Incoming tracks
    for hex_color, pts in _TRACKS:
        color = QColor(hex_color)
        pen = QPen(color, 2.5)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)

        path = QPainterPath()
        path.moveTo(QPointF(*pts[0]))
        for pt in pts[1:]:
            path.lineTo(QPointF(*pt))
        p.drawPath(path)

        # Start dot
        dot_color = QColor(hex_color)
        p.setBrush(dot_color)
        p.setPen(QPen(dot_color.lighter(150), 1))
        p.drawEllipse(QPointF(*pts[0]), 4.5, 4.5)
        p.setBrush(Qt.BrushStyle.NoBrush)

    # Merged output track — thick white with glow
    for width, alpha in ((10, 30), (6, 70), (3, 220)):
        pen = QPen(QColor(255, 255, 255, alpha), width)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.drawLine(QPointF(_MERGE_X, _MERGE_Y), QPointF(*_EXIT_END))

    # Merge node circle
    merge_glow = QColor(255, 255, 255, 40)
    p.setBrush(merge_glow)
    p.setPen(QPen(QColor(255, 255, 255, 80), 1))
    p.drawEllipse(QPointF(_MERGE_X, _MERGE_Y), 14, 14)

    p.setBrush(QColor("#ffffff"))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawEllipse(QPointF(_MERGE_X, _MERGE_Y), 5, 5)

    # Title text
    title_font = QFont("Segoe UI", 28, QFont.Weight.Bold)
    p.setFont(title_font)
    p.setPen(QColor("#ffffff"))
    p.drawText(30, 220, "GetTracks")

    # Subtitle
    sub_font = QFont("Segoe UI", 10)
    p.setFont(sub_font)
    p.setPen(QColor("#90caf9"))
    p.drawText(32, 246, "Merge · Visualise · Export")

    p.end()
    return pixmap


# ---------------------------------------------------------------------------
# Public helper
# ---------------------------------------------------------------------------

def make_splash() -> QSplashScreen:
    """Create and return a styled splash screen (not yet shown)."""
    pixmap = _make_splash_pixmap()
    splash = QSplashScreen(pixmap, Qt.WindowType.WindowStaysOnTopHint)
    splash.setMask(pixmap.mask())
    return splash
