"""Low-level bbox helper math for hit-testing and clamping.

These helpers are intentionally primitive operations reused by higher-level
interaction and widget facade logic.

See Also:
    - [`DragMode`][app.ui.qt.widgets.preview.layer_bbox.bbox_drag.DragMode] — describes the resize handle selected by hit-testing
    - [`find_bbox_at_pos`][app.ui.qt.widgets.preview.layer_bbox.geometry.find_bbox_at_pos] — locates boxes under the pointer

Layer: Presentation.
Context: Contains concrete Qt presentation components and supporting utilities.
"""

from __future__ import annotations

from PySide6.QtCore import QRect, QPoint

from app.ui.qt.widgets.preview.layer_bbox.bbox_drag import DragMode
from app.ui.qt.widgets.preview.layer_bbox.constants import _HANDLE_RADIUS


def get_drag_mode_for_rect_at_pos(rect: QRect, pos: QPoint) -> DragMode:
    """Identify the resize handle nearest to a pointer position.

    Args:
        rect: Bounding rectangle whose handles are hit-tested.
        pos: Pointer position in the same widget coordinate space.

    Returns:
        Matching handle mode, or `DragMode.NONE` when no handle is hit.
    """
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
    """Clamp a rectangle to the pixmap bounds.

    Args:
        rect: Rectangle to keep inside the displayed image area.
        pixmap_rect: Bounds of the displayed image.

    Returns:
        Normalized rectangle shifted back within the image bounds.
    """
    if rect.isNull():
        return rect

    normalized = rect.normalized()
    left = normalized.left()
    right = normalized.right()
    top = normalized.top()
    bottom = normalized.bottom()

    if right > pixmap_rect.right():
        shift = pixmap_rect.right() - right
        left += shift
        right += shift
    elif left < pixmap_rect.left():
        shift = pixmap_rect.left() - left
        left += shift
        right += shift

    if bottom > pixmap_rect.bottom():
        shift = pixmap_rect.bottom() - bottom
        top += shift
        bottom += shift
    elif top < pixmap_rect.top():
        shift = pixmap_rect.top() - top
        top += shift
        bottom += shift

    return QRect(QPoint(left, top), QPoint(right, bottom)).normalized()


def apply_clamped_drag_deltas(mode: DragMode, pr: QRect, x1: int, x2: int, y1: int, y2: int, dx: int, dy: int) -> QRect:
    """Apply clamped drag deltas.

    Args:
        mode: Active handle being dragged.
        pr: Rectangle limiting the resulting coordinates.
        x1: Starting left coordinate.
        x2: Starting right coordinate.
        y1: Starting top coordinate.
        y2: Starting bottom coordinate.
        dx: Horizontal pointer displacement from drag start.
        dy: Vertical pointer displacement from drag start.

    Returns:
        Normalized rectangle after moving the selected edge or corner, clamped to `pr`.
    """
    def clamp_x(v: int) -> int:
        """Clamp a horizontal coordinate to the preview rectangle.

        Args:
            v: Horizontal coordinate to clamp.

        Returns:
            Coordinate between `pr.left()` and `pr.right()`.
        """
        return max(pr.left(), min(v, pr.right()))

    def clamp_y(v: int) -> int:
        """Clamp a vertical coordinate to the preview rectangle.

        Args:
            v: Vertical coordinate to clamp.

        Returns:
            Coordinate between `pr.top()` and `pr.bottom()`.
        """
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
    """Clamp a point to the rectangle bounds.

    Args:
        point: Point to constrain.
        r: Rectangle defining the allowed coordinate range.

    Returns:
        Point with x and y independently clamped to `r`.
    """
    return QPoint(
        max(r.left(), min(point.x(), r.right())),
        max(r.top(), min(point.y(), r.bottom())),
    )
