"""Custom QPainter silhouette icons for transport and activity modes.

Style: solid filled silhouettes with white window / detail cutouts,
matching a solid-fill icon set (think Shutterstock solid transport icons).

Each public ``draw_*`` function receives an already-configured QPainter,
a QRectF bounding box, and a fill QColor.  The caller is responsible for
saving/restoring painter state if needed.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, QPointF, QRectF
from PyQt6.QtGui import QBrush, QColor, QPainter, QPainterPath, QPen

_WHITE = QColor("white")
_NO_PEN = Qt.PenStyle.NoPen


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _body(p: QPainter, color: QColor) -> None:
    p.setBrush(QBrush(color))
    p.setPen(_NO_PEN)


def _detail(p: QPainter) -> None:
    p.setBrush(QBrush(_WHITE))
    p.setPen(_NO_PEN)


# ---------------------------------------------------------------------------
# Transport icons
# ---------------------------------------------------------------------------

def draw_train(p: QPainter, rect: QRectF, fill: QColor) -> None:
    """Side-profile high-speed train (TGV/bullet) silhouette with speed lines."""
    x, y, w, h = rect.x(), rect.y(), rect.width(), rect.height()
    r = min(w, h)

    _body(p, fill)

    # ── Main body shell ──────────────────────────────────────────────────
    # Streamlined body: pointed nose on the left, rounded tail on the right.
    body = QPainterPath()
    body.moveTo(x + w*0.04, y + h*0.62)          # nose tip (bottom)
    body.quadTo(x + w*0.01, y + h*0.44,
                x + w*0.08, y + h*0.30)           # nose curve up
    body.quadTo(x + w*0.16, y + h*0.20,
                x + w*0.28, y + h*0.18)           # cab roof start
    body.lineTo(x + w*0.88, y + h*0.18)           # roof flat
    body.quadTo(x + w*0.97, y + h*0.18,
                x + w*0.97, y + h*0.30)           # tail top corner
    body.lineTo(x + w*0.97, y + h*0.62)           # tail bottom
    body.quadTo(x + w*0.97, y + h*0.68,
                x + w*0.90, y + h*0.68)           # tail bottom corner
    body.lineTo(x + w*0.12, y + h*0.68)           # underframe bottom
    body.closeSubpath()
    p.drawPath(body)

    # ── Windows (white) ───────────────────────────────────────────────────
    _detail(p)
    win_top  = y + h*0.24
    win_h    = h*0.24
    win_w    = w*0.11
    win_gap  = w*0.035
    win_r    = r*0.04
    # Cab window (wider, slightly further right due to nose taper)
    p.drawRoundedRect(QRectF(x + w*0.20, win_top, w*0.10, win_h), win_r, win_r)
    # Three passenger windows
    for i in range(3):
        wx = x + w*0.33 + i * (win_w + win_gap)
        p.drawRoundedRect(QRectF(wx, win_top, win_w, win_h), win_r, win_r)

    # ── Underframe / skirt ────────────────────────────────────────────────
    _body(p, fill)
    skirt = QPainterPath()
    skirt.moveTo(x + w*0.12, y + h*0.68)
    skirt.lineTo(x + w*0.90, y + h*0.68)
    skirt.lineTo(x + w*0.90, y + h*0.76)
    skirt.lineTo(x + w*0.12, y + h*0.76)
    skirt.closeSubpath()
    p.drawPath(skirt)

    # ── Bogies / wheels (two sets) ────────────────────────────────────────
    bogie_y  = y + h*0.84
    bogie_r  = w*0.10
    for bx in (x + w*0.26, x + w*0.74):
        p.drawEllipse(QPointF(bx, bogie_y), bogie_r, bogie_r)
    # Wheel hubs (white)
    _detail(p)
    hub_r = bogie_r * 0.38
    for bx in (x + w*0.26, x + w*0.74):
        p.drawEllipse(QPointF(bx, bogie_y), hub_r, hub_r)

    # ── Speed lines (three horizontal stripes left of nose) ───────────────
    _body(p, fill)
    line_pen = QPen(fill, max(1.0, r * 0.055))
    line_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(line_pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    speed_x0 = x + w*0.01
    speed_x1 = x + w*0.10
    for i, fy in enumerate([0.34, 0.44, 0.54]):
        p.drawLine(QPointF(speed_x0, y + h*fy),
                   QPointF(speed_x1, y + h*fy))
    p.setPen(_NO_PEN)


def draw_airplane(p: QPainter, rect: QRectF, fill: QColor) -> None:
    """Top-down airplane silhouette, nose pointing upward."""
    x, y, w, h = rect.x(), rect.y(), rect.width(), rect.height()
    cx = x + w / 2.0

    _body(p, fill)

    # Fuselage
    fuselage = QPainterPath()
    fuselage.moveTo(cx, y + h*0.03)
    fuselage.quadTo(cx + w*0.10, y + h*0.22, cx + w*0.08, y + h*0.50)
    fuselage.lineTo(cx + w*0.06, y + h*0.76)
    fuselage.lineTo(cx, y + h*0.82)
    fuselage.lineTo(cx - w*0.06, y + h*0.76)
    fuselage.lineTo(cx - w*0.08, y + h*0.50)
    fuselage.quadTo(cx - w*0.10, y + h*0.22, cx, y + h*0.03)
    fuselage.closeSubpath()
    p.drawPath(fuselage)

    # Right wing (swept back)
    wing_r = QPainterPath()
    wing_r.moveTo(cx + w*0.08, y + h*0.33)
    wing_r.lineTo(x + w*0.97, y + h*0.58)
    wing_r.lineTo(x + w*0.78, y + h*0.64)
    wing_r.lineTo(cx + w*0.08, y + h*0.50)
    wing_r.closeSubpath()
    p.drawPath(wing_r)

    # Left wing (mirror)
    wing_l = QPainterPath()
    wing_l.moveTo(cx - w*0.08, y + h*0.33)
    wing_l.lineTo(x + w*0.03, y + h*0.58)
    wing_l.lineTo(x + w*0.22, y + h*0.64)
    wing_l.lineTo(cx - w*0.08, y + h*0.50)
    wing_l.closeSubpath()
    p.drawPath(wing_l)

    # Right tail fin
    tail_r = QPainterPath()
    tail_r.moveTo(cx + w*0.06, y + h*0.76)
    tail_r.lineTo(cx + w*0.30, y + h*0.97)
    tail_r.lineTo(cx + w*0.06, y + h*0.90)
    tail_r.closeSubpath()
    p.drawPath(tail_r)

    # Left tail fin
    tail_l = QPainterPath()
    tail_l.moveTo(cx - w*0.06, y + h*0.76)
    tail_l.lineTo(cx - w*0.30, y + h*0.97)
    tail_l.lineTo(cx - w*0.06, y + h*0.90)
    tail_l.closeSubpath()
    p.drawPath(tail_l)


def draw_ship(p: QPainter, rect: QRectF, fill: QColor) -> None:
    """Side-view ship / ferry silhouette."""
    x, y, w, h = rect.x(), rect.y(), rect.width(), rect.height()

    _body(p, fill)

    # Hull
    hull = QPainterPath()
    hull.moveTo(x + w*0.06, y + h*0.58)
    hull.lineTo(x + w*0.02, y + h*0.72)
    hull.quadTo(x + w*0.08, y + h*0.90, x + w*0.22, y + h*0.90)
    hull.lineTo(x + w*0.78, y + h*0.90)
    hull.quadTo(x + w*0.92, y + h*0.90, x + w*0.98, y + h*0.72)
    hull.lineTo(x + w*0.94, y + h*0.58)
    hull.closeSubpath()
    p.drawPath(hull)

    # Superstructure (cabin)
    p.drawRoundedRect(
        QRectF(x + w*0.18, y + h*0.28, w*0.64, h*0.32),
        w*0.05, h*0.05,
    )

    # Funnel
    p.drawRoundedRect(
        QRectF(x + w*0.42, y + h*0.08, w*0.16, h*0.22),
        w*0.04, h*0.04,
    )

    # Porthole windows (white circles)
    _detail(p)
    for i in range(3):
        wx = x + w * (0.30 + i * 0.19)
        p.drawEllipse(QPointF(wx, y + h*0.44), w*0.06, h*0.06)


def draw_bus(p: QPainter, rect: QRectF, fill: QColor) -> None:
    """Front-facing bus silhouette."""
    x, y, w, h = rect.x(), rect.y(), rect.width(), rect.height()
    r = min(w, h)

    # Body
    _body(p, fill)
    p.drawRoundedRect(
        QRectF(x + w*0.05, y + h*0.04, w*0.90, h*0.72),
        r*0.10, r*0.10,
    )

    # Windshield (large white area)
    _detail(p)
    p.drawRoundedRect(
        QRectF(x + w*0.12, y + h*0.09, w*0.76, h*0.30),
        r*0.06, r*0.06,
    )

    # Left headlight
    p.drawRoundedRect(
        QRectF(x + w*0.10, y + h*0.50, w*0.22, h*0.14),
        r*0.04, r*0.04,
    )

    # Right headlight
    p.drawRoundedRect(
        QRectF(x + w*0.68, y + h*0.50, w*0.22, h*0.14),
        r*0.04, r*0.04,
    )

    # Destination sign (small white bar under windshield)
    p.drawRect(QRectF(x + w*0.12, y + h*0.41, w*0.76, h*0.07))

    # Axle bar
    _body(p, fill)
    p.drawRect(QRectF(x + w*0.05, y + h*0.76, w*0.90, h*0.04))

    # Left wheel
    p.drawEllipse(QPointF(x + w*0.24, y + h*0.88), w*0.17, h*0.12)
    # Right wheel
    p.drawEllipse(QPointF(x + w*0.76, y + h*0.88), w*0.17, h*0.12)

    # Wheel hubs (white)
    _detail(p)
    p.drawEllipse(QPointF(x + w*0.24, y + h*0.88), w*0.07, h*0.05)
    p.drawEllipse(QPointF(x + w*0.76, y + h*0.88), w*0.07, h*0.05)


# ---------------------------------------------------------------------------
# Activity type icons (for the project list widget)
# ---------------------------------------------------------------------------

def draw_run(p: QPainter, rect: QRectF, fill: QColor) -> None:
    """Simplified running figure silhouette."""
    x, y, w, h = rect.x(), rect.y(), rect.width(), rect.height()
    r = min(w, h)

    _body(p, fill)
    # Head
    p.drawEllipse(QRectF(x + w*0.50, y + h*0.02, w*0.24, h*0.22))

    # Torso
    torso = QPainterPath()
    torso.moveTo(x + w*0.60, y + h*0.24)
    torso.lineTo(x + w*0.52, y + h*0.56)
    torso.lineTo(x + w*0.62, y + h*0.56)
    torso.lineTo(x + w*0.72, y + h*0.24)
    torso.closeSubpath()
    p.drawPath(torso)

    # Left arm (forward)
    arm_l = QPainterPath()
    arm_l.moveTo(x + w*0.68, y + h*0.28)
    arm_l.quadTo(x + w*0.82, y + h*0.36, x + w*0.88, y + h*0.50)
    arm_l.lineTo(x + w*0.80, y + h*0.53)
    arm_l.quadTo(x + w*0.74, y + h*0.40, x + w*0.62, y + h*0.34)
    arm_l.closeSubpath()
    p.drawPath(arm_l)

    # Right arm (back)
    arm_r = QPainterPath()
    arm_r.moveTo(x + w*0.62, y + h*0.30)
    arm_r.quadTo(x + w*0.42, y + h*0.38, x + w*0.28, y + h*0.46)
    arm_r.lineTo(x + w*0.34, y + h*0.52)
    arm_r.quadTo(x + w*0.48, y + h*0.44, x + w*0.68, y + h*0.36)
    arm_r.closeSubpath()
    p.drawPath(arm_r)

    # Left leg (forward, bent)
    leg_l = QPainterPath()
    leg_l.moveTo(x + w*0.56, y + h*0.54)
    leg_l.quadTo(x + w*0.54, y + h*0.70, x + w*0.44, y + h*0.82)
    leg_l.lineTo(x + w*0.28, y + h*0.96)
    leg_l.lineTo(x + w*0.20, y + h*0.90)
    leg_l.lineTo(x + w*0.36, y + h*0.78)
    leg_l.quadTo(x + w*0.44, y + h*0.66, x + w*0.46, y + h*0.54)
    leg_l.closeSubpath()
    p.drawPath(leg_l)

    # Right leg (back, bent up)
    leg_r = QPainterPath()
    leg_r.moveTo(x + w*0.62, y + h*0.54)
    leg_r.quadTo(x + w*0.70, y + h*0.66, x + w*0.80, y + h*0.60)
    leg_r.lineTo(x + w*0.90, y + h*0.46)
    leg_r.lineTo(x + w*0.84, y + h*0.42)
    leg_r.lineTo(x + w*0.76, y + h*0.54)
    leg_r.quadTo(x + w*0.68, y + h*0.58, x + w*0.62, y + h*0.58)  # noqa
    leg_r.closeSubpath()
    p.drawPath(leg_r)


def draw_bicycle(p: QPainter, rect: QRectF, fill: QColor) -> None:
    """Bicycle silhouette (side view) matching the reference icon set style."""
    x, y, w, h = rect.x(), rect.y(), rect.width(), rect.height()
    r = min(w, h)

    _body(p, fill)

    wheel_r_px = w * 0.30
    wheel_stroke = max(2.0, r * 0.09)

    # Rear wheel
    rear_cx = x + w * 0.26
    wheel_cy = y + h * 0.68

    pen = QPen(fill, wheel_stroke)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawEllipse(QPointF(rear_cx, wheel_cy), wheel_r_px, wheel_r_px)

    # Front wheel
    front_cx = x + w * 0.74
    p.drawEllipse(QPointF(front_cx, wheel_cy), wheel_r_px, wheel_r_px)

    # Frame — chain stay (rear axle to bottom bracket)
    frame_pen = QPen(fill, wheel_stroke * 0.9)
    frame_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(frame_pen)

    bb_x = x + w * 0.50   # bottom bracket (pedals)
    bb_y = y + h * 0.72

    # chain stay
    p.drawLine(QPointF(rear_cx, wheel_cy), QPointF(bb_x, bb_y))

    # seat stay
    seat_x = x + w * 0.42
    seat_y = y + h * 0.30
    p.drawLine(QPointF(rear_cx, wheel_cy), QPointF(seat_x, seat_y))

    # top tube (seat to head tube)
    head_x = x + w * 0.66
    head_y = y + h * 0.28
    p.drawLine(QPointF(seat_x, seat_y), QPointF(head_x, head_y))

    # down tube (head tube to bottom bracket)
    p.drawLine(QPointF(head_x, head_y), QPointF(bb_x, bb_y))

    # seat tube
    p.drawLine(QPointF(seat_x, seat_y), QPointF(bb_x, bb_y))

    # fork (head tube to front axle)
    p.drawLine(QPointF(head_x, head_y), QPointF(front_cx, wheel_cy))

    # Handlebar
    bar_pen = QPen(fill, wheel_stroke * 0.85)
    bar_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(bar_pen)
    p.drawLine(QPointF(head_x, head_y),
               QPointF(head_x + w*0.08, head_y - h*0.08))
    p.drawLine(QPointF(head_x + w*0.08, head_y - h*0.08),
               QPointF(head_x + w*0.12, head_y - h*0.04))

    # Saddle
    p.drawLine(QPointF(seat_x - w*0.08, seat_y - h*0.04),
               QPointF(seat_x + w*0.08, seat_y - h*0.04))

    # Wheel hubs (solid filled dots)
    _body(p, fill)
    hub_r = wheel_stroke * 0.7
    p.drawEllipse(QPointF(rear_cx, wheel_cy), hub_r, hub_r)
    p.drawEllipse(QPointF(front_cx, wheel_cy), hub_r, hub_r)
    p.drawEllipse(QPointF(bb_x, bb_y), hub_r, hub_r)


def draw_hike(p: QPainter, rect: QRectF, fill: QColor) -> None:
    """Hiker silhouette with walking stick."""
    x, y, w, h = rect.x(), rect.y(), rect.width(), rect.height()
    r = min(w, h)

    _body(p, fill)
    # Head
    p.drawEllipse(QRectF(x + w*0.38, y + h*0.02, w*0.24, h*0.20))

    # Body
    body = QPainterPath()
    body.moveTo(x + w*0.46, y + h*0.22)
    body.lineTo(x + w*0.40, y + h*0.55)
    body.lineTo(x + w*0.56, y + h*0.55)
    body.lineTo(x + w*0.62, y + h*0.22)
    body.closeSubpath()
    p.drawPath(body)

    # Left leg
    leg_l = QPainterPath()
    leg_l.moveTo(x + w*0.44, y + h*0.53)
    leg_l.lineTo(x + w*0.34, y + h*0.76)
    leg_l.lineTo(x + w*0.26, y + h*0.96)
    leg_l.lineTo(x + w*0.34, y + h*0.96)
    leg_l.lineTo(x + w*0.42, y + h*0.76)
    leg_l.lineTo(x + w*0.52, y + h*0.54)
    leg_l.closeSubpath()
    p.drawPath(leg_l)

    # Right leg
    leg_r = QPainterPath()
    leg_r.moveTo(x + w*0.52, y + h*0.53)
    leg_r.lineTo(x + w*0.60, y + h*0.76)
    leg_r.lineTo(x + w*0.66, y + h*0.96)
    leg_r.lineTo(x + w*0.74, y + h*0.96)
    leg_r.lineTo(x + w*0.68, y + h*0.76)
    leg_r.lineTo(x + w*0.58, y + h*0.54)
    leg_r.closeSubpath()
    p.drawPath(leg_r)

    # Right arm (holds stick)
    arm_r = QPainterPath()
    arm_r.moveTo(x + w*0.58, y + h*0.27)
    arm_r.quadTo(x + w*0.72, y + h*0.36, x + w*0.78, y + h*0.50)
    arm_r.lineTo(x + w*0.70, y + h*0.52)
    arm_r.quadTo(x + w*0.64, y + h*0.40, x + w*0.52, y + h*0.32)
    arm_r.closeSubpath()
    p.drawPath(arm_r)

    # Walking stick
    stick_pen = QPen(fill, max(2.0, r * 0.08))
    stick_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(stick_pen)
    p.drawLine(QPointF(x + w*0.76, y + h*0.48), QPointF(x + w*0.82, y + h*0.98))
    p.setPen(_NO_PEN)


def draw_walk(p: QPainter, rect: QRectF, fill: QColor) -> None:
    """Walking figure silhouette."""
    x, y, w, h = rect.x(), rect.y(), rect.width(), rect.height()

    _body(p, fill)
    # Head
    p.drawEllipse(QRectF(x + w*0.44, y + h*0.02, w*0.24, h*0.20))

    # Body
    body = QPainterPath()
    body.moveTo(x + w*0.48, y + h*0.22)
    body.lineTo(x + w*0.38, y + h*0.54)
    body.lineTo(x + w*0.54, y + h*0.54)
    body.lineTo(x + w*0.66, y + h*0.22)
    body.closeSubpath()
    p.drawPath(body)

    # Left leg (forward)
    leg_l = QPainterPath()
    leg_l.moveTo(x + w*0.42, y + h*0.52)
    leg_l.lineTo(x + w*0.36, y + h*0.76)
    leg_l.lineTo(x + w*0.22, y + h*0.96)
    leg_l.lineTo(x + w*0.30, y + h*0.96)
    leg_l.lineTo(x + w*0.44, y + h*0.76)
    leg_l.lineTo(x + w*0.50, y + h*0.52)
    leg_l.closeSubpath()
    p.drawPath(leg_l)

    # Right leg (back)
    leg_r = QPainterPath()
    leg_r.moveTo(x + w*0.50, y + h*0.52)
    leg_r.lineTo(x + w*0.60, y + h*0.76)
    leg_r.lineTo(x + w*0.68, y + h*0.96)
    leg_r.lineTo(x + w*0.76, y + h*0.96)
    leg_r.lineTo(x + w*0.68, y + h*0.76)
    leg_r.lineTo(x + w*0.58, y + h*0.52)
    leg_r.closeSubpath()
    p.drawPath(leg_r)

    # Left arm (back)
    arm_l = QPainterPath()
    arm_l.moveTo(x + w*0.56, y + h*0.28)
    arm_l.quadTo(x + w*0.68, y + h*0.38, x + w*0.72, y + h*0.52)
    arm_l.lineTo(x + w*0.64, y + h*0.54)
    arm_l.quadTo(x + w*0.60, y + h*0.42, x + w*0.50, y + h*0.34)
    arm_l.closeSubpath()
    p.drawPath(arm_l)

    # Right arm (forward)
    arm_r = QPainterPath()
    arm_r.moveTo(x + w*0.50, y + h*0.28)
    arm_r.quadTo(x + w*0.34, y + h*0.36, x + w*0.26, y + h*0.46)
    arm_r.lineTo(x + w*0.32, y + h*0.52)
    arm_r.quadTo(x + w*0.40, y + h*0.42, x + w*0.54, y + h*0.34)
    arm_r.closeSubpath()
    p.drawPath(arm_r)


def draw_swim(p: QPainter, rect: QRectF, fill: QColor) -> None:
    """Swimmer silhouette."""
    x, y, w, h = rect.x(), rect.y(), rect.width(), rect.height()
    r = min(w, h)

    _body(p, fill)

    # Head
    p.drawEllipse(QRectF(x + w*0.04, y + h*0.30, w*0.22, h*0.24))

    # Body (horizontal streamlined shape)
    body = QPainterPath()
    body.moveTo(x + w*0.24, y + h*0.38)
    body.quadTo(x + w*0.50, y + h*0.30, x + w*0.80, y + h*0.36)
    body.lineTo(x + w*0.80, y + h*0.50)
    body.quadTo(x + w*0.50, y + h*0.56, x + w*0.24, y + h*0.50)
    body.closeSubpath()
    p.drawPath(body)

    # Outstretched arm
    arm = QPainterPath()
    arm.moveTo(x + w*0.50, y + h*0.36)
    arm.lineTo(x + w*0.96, y + h*0.28)
    arm.lineTo(x + w*0.96, y + h*0.36)
    arm.lineTo(x + w*0.50, y + h*0.44)
    arm.closeSubpath()
    p.drawPath(arm)

    # Legs / kick
    kick = QPainterPath()
    kick.moveTo(x + w*0.78, y + h*0.42)
    kick.lineTo(x + w*0.96, y + h*0.56)
    kick.lineTo(x + w*0.88, y + h*0.60)
    kick.lineTo(x + w*0.72, y + h*0.50)
    kick.closeSubpath()
    p.drawPath(kick)
    kick2 = QPainterPath()
    kick2.moveTo(x + w*0.78, y + h*0.50)
    kick2.lineTo(x + w*0.96, y + h*0.68)
    kick2.lineTo(x + w*0.88, y + h*0.72)
    kick2.lineTo(x + w*0.72, y + h*0.58)
    kick2.closeSubpath()
    p.drawPath(kick2)

    # Wave lines
    wave_pen = QPen(fill, max(1.5, r * 0.06))
    wave_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(wave_pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    for i, base_y in enumerate([y + h*0.74, y + h*0.84]):
        for j in range(3):
            wx = x + w*(0.10 + j*0.28)
            p.drawArc(
                QRectF(wx, base_y, w*0.22, h*0.10),
                0, 180 * 16,
            )
    p.setPen(_NO_PEN)


# ---------------------------------------------------------------------------
# Dispatch table
# ---------------------------------------------------------------------------

_TRANSPORT_DRAW = {
    "train":  draw_train,
    "flight": draw_airplane,
    "boat":   draw_ship,
    "bus":    draw_bus,
}

_ACTIVITY_DRAW = {
    "run":  draw_run,
    "ride": draw_bicycle,
    "hike": draw_hike,
    "walk": draw_walk,
    "swim": draw_swim,
}


def draw_transport_icon(
    p: QPainter,
    cx: float, cy: float,
    size: float,
    transport_type: str,
    fill: QColor,
) -> None:
    """Draw a transport icon centered at *(cx, cy)* within a *size×size* square."""
    func = _TRANSPORT_DRAW.get(transport_type)
    if func is None:
        return
    half = size / 2.0
    p.save()
    func(p, QRectF(cx - half, cy - half, size, size), fill)
    p.restore()


def draw_activity_icon(
    p: QPainter,
    cx: float, cy: float,
    size: float,
    activity_type: str,
    fill: QColor,
) -> None:
    """Draw an activity-type icon centered at *(cx, cy)* within a *size×size* square."""
    func = _ACTIVITY_DRAW.get(activity_type.lower())
    if func is None:
        # Fallback: bold initial letter
        from PyQt6.QtGui import QFont
        font = QFont()
        font.setPointSize(int(size * 0.55))
        font.setBold(True)
        p.save()
        p.setFont(font)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(fill))
        half = size / 2.0
        p.drawText(
            QRectF(cx - half, cy - half, size, size),
            Qt.AlignmentFlag.AlignCenter,
            activity_type[0].upper() if activity_type else "?",
        )
        p.restore()
        return
    half = size / 2.0
    p.save()
    func(p, QRectF(cx - half, cy - half, size, size), fill)
    p.restore()
