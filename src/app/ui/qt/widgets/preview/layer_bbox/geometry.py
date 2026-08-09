"""Geometry and coordinate-space helpers for bbox overlay interactions.

This module converts between image space and widget space, and provides proximity
lookup for selecting the nearest bbox around the cursor.
"""

from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, QSize

from app.domain.base.dtypes import BBoxXYXYTuple


def image_rect_to_widget_space(
    x1: int,
    y1: int,
    x2: int,
    y2: int,
    pixmap_rect: QRect,
    image_size: QSize | None,
) -> QRect:
    """Convert image-space coordinates into a widget-space rectangle."""
    if pixmap_rect.width() == 0 or image_size is None:
        return QRect()

    sx = pixmap_rect.width() / image_size.width()
    sy = pixmap_rect.height() / image_size.height()
    return QRect(
        QPoint(int((x1 * sx) + pixmap_rect.left()), int((y1 * sy) + pixmap_rect.top())),
        QPoint(int((x2 * sx) + pixmap_rect.left()), int((y2 * sy) + pixmap_rect.top())),
    ).normalized()


def widget_rect_to_image_space(
    rect: QRect,
    pixmap_rect: QRect,
    image_size: QSize | None,
) -> BBoxXYXYTuple:
    """Convert a widget-space rectangle into clamped image-space coordinates."""
    if pixmap_rect.width() == 0 or image_size is None:
        return 0, 0, 0, 0

    sx = image_size.width() / pixmap_rect.width()
    sy = image_size.height() / pixmap_rect.height()
    return (
        max(0, int((rect.left() - pixmap_rect.left()) * sx)),
        max(0, int((rect.top() - pixmap_rect.top()) * sy)),
        min(image_size.width(), int((rect.right() - pixmap_rect.left()) * sx)),
        min(image_size.height(), int((rect.bottom() - pixmap_rect.top()) * sy)),
    )


def find_bbox_at_pos(
    active_bboxes: dict[str, BBoxXYXYTuple],
    pos: QPoint,
    pixmap_rect: QRect,
    image_size: QSize | None,
    snap_radius_sq: int = 2500,
) -> tuple[str | None, QRect | None]:
    """Find a bbox at the cursor or snap to the nearest bbox center within radius."""
    closest_id: str | None = None
    closest_rect: QRect | None = None
    min_dist = float("inf")

    for bbox_id, (x1, y1, x2, y2) in active_bboxes.items():
        rect = image_rect_to_widget_space(x1, y1, x2, y2, pixmap_rect, image_size)
        if rect.isNull():
            continue

        if rect.contains(pos):
            return bbox_id, rect

        cx, cy = rect.center().x(), rect.center().y()
        dist = (pos.x() - cx) ** 2 + (pos.y() - cy) ** 2
        if dist < min_dist:
            min_dist = dist
            closest_id = bbox_id
            closest_rect = rect

    if min_dist < snap_radius_sq:
        return closest_id, closest_rect

    return None, None

