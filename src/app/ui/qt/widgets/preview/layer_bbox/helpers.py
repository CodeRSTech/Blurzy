"""Low-level bbox helper math for hit-testing and clamping.

These helpers are intentionally primitive operations reused by higher-level
interaction and widget facade logic.
"""

from __future__ import annotations

from PySide6.QtCore import QRect, QPoint

from app.ui.view_state.preview.bbox_drag import DragMode
from app.ui.qt.widgets.preview.layer_bbox.constants import _HANDLE_RADIUS


def get_drag_mode_for_rect_at_pos(rect: QRect, pos: QPoint) -> DragMode:
    x1, y1 = rect.left(), rect.top()
    x2, y2 = rect.right(), rect.bottom()
    mx, my = (x1 + x2) // 2, (y1 + y2) // 2
    r = _HANDLE_RADIUS

    handles: list[tuple[QPoint, DragMode]] = [
        (QPoint(x1, y1), DragMode.TOP_LEFT),
        (QPoint(x2, y1), DragMode.TOP_RIGHT),
        (QPoint(x1, y2), DragMode.BOT_LEFT),
        (QPoint(x2, y2), DragMode.BOT_RIGHT),
        (QPoint(mx, y1), DragMode.TOP),
        (QPoint(mx, y2), DragMode.BOTTOM),
        (QPoint(x1, my), DragMode.LEFT),
        (QPoint(x2, my), DragMode.RIGHT),
    ]
    for pt, mode in handles:
        if (pos - pt).manhattanLength() <= r * 2:
            return mode
    return DragMode.NONE


def clamp_rect_to_pixmap(rect: QRect, pixmap_rect: QRect) -> QRect:
    dx = dy = 0
    if rect.left() < pixmap_rect.left():
        dx = pixmap_rect.left() - rect.left()
    if rect.right() > pixmap_rect.right():
        dx = pixmap_rect.right() - rect.right()
    if rect.top() < pixmap_rect.top():
        dy = pixmap_rect.top() - rect.top()
    if rect.bottom() > pixmap_rect.bottom():
        dy = pixmap_rect.bottom() - rect.bottom()
    return rect.translated(dx, dy)


def apply_clamped_drag_deltas(mode: DragMode, pr: QRect, x1: int, x2: int, y1: int, y2: int, dx: int, dy: int) -> QRect:
    def clamp_x(v: int) -> int:
        return max(pr.left(), min(v, pr.right()))

    def clamp_y(v: int) -> int:
        return max(pr.top(), min(v, pr.bottom()))

    if mode == DragMode.TOP_LEFT:
        x1, y1 = clamp_x(x1 + dx), clamp_y(y1 + dy)
    elif mode == DragMode.TOP_RIGHT:
        x2, y1 = clamp_x(x2 + dx), clamp_y(y1 + dy)
    elif mode == DragMode.BOT_LEFT:
        x1, y2 = clamp_x(x1 + dx), clamp_y(y2 + dy)
    elif mode == DragMode.BOT_RIGHT:
        x2, y2 = clamp_x(x2 + dx), clamp_y(y2 + dy)
    elif mode == DragMode.TOP:
        y1 = clamp_y(y1 + dy)
    elif mode == DragMode.BOTTOM:
        y2 = clamp_y(y2 + dy)
    elif mode == DragMode.LEFT:
        x1 = clamp_x(x1 + dx)
    elif mode == DragMode.RIGHT:
        x2 = clamp_x(x2 + dx)

    return QRect(QPoint(x1, y1), QPoint(x2, y2)).normalized()


def clamp_point_to_rect(point: QPoint, r: QRect) -> QPoint:
    return QPoint(
        max(r.left(), min(point.x(), r.right())),
        max(r.top(), min(point.y(), r.bottom())),
    )
