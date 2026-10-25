"""
Rendering primitives for drawing active bbox visuals.

This module contains paint-only helpers and does not mutate widget state.

See Also:
    - [`BBoxViewModel`][app.domain.views.bounding_box_view_model.BBoxViewModel] — provides box geometry and style
    - [`get_handle_points_from_rect`][app.ui.qt.shared.geometry_ui.get_handle_points_from_rect] — computes resize-handle positions


Layer: Presentation.
Context: Contains concrete Qt presentation components and supporting utilities.
"""

from __future__ import annotations

from typing import TYPE_CHECKING


from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QBrush, QColor, QFontMetrics, QPen

from app.ui.qt.shared.geometry_ui import get_handle_points_from_rect
from app.ui.qt.widgets.preview.layer_bbox.constants import (
    _BOX_COLOR,
    _CENTER_COLOR,
    _HANDLE_BORDER,
    _HANDLE_COLOR,
    _HANDLE_DRAW_R,
)
if TYPE_CHECKING:
    from PySide6.QtGui import QPainter


def scale_bbox_border_width(border_width: int, displayed_video_height: int) -> int:
    """Scale the configured outline against the displayed video canvas.

    Args:
        border_width: Configured reference width at a 480-pixel video height.
        displayed_video_height: Current fitted/zoomed video height in widget pixels.

    Returns:
        Visible pen width clamped to the range 1–12 widget pixels.
    """
    if displayed_video_height <= 0:
        return max(1, min(12, border_width))
    scaled_width = int(border_width * displayed_video_height / 480 + 0.5)
    return max(1, min(12, scaled_width))


def draw_bbox_outline(
    painter: QPainter,
    rect: QRect,
    color: QColor,
    border_width: int,
) -> None:
    """Draw a canvas-space box with a dark halo for contrast over busy footage.

    Args:
        painter: Active painter, whose state is restored before returning.
        rect: Projected box geometry in widget pixels.
        color: Annotation color shared with the table swatch.
        border_width: Canvas-scaled outline width.
    """
    painter.save()
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.setPen(QPen(QColor(0, 0, 0, 200), border_width + 2))
    painter.drawRect(rect)
    painter.setPen(QPen(color, border_width))
    painter.drawRect(rect)
    painter.restore()


def draw_bbox_caption(painter: QPainter, rect: QRect, color: QColor, caption: str, viewport: QRect) -> None:
    """Draw an opaque caption at UI font size, bounded by the visible canvas.

    Args:
        painter: Active painter, whose state is restored before returning.
        rect: Projected box geometry in widget pixels.
        color: Annotation color used for the caption's leading stripe.
        caption: Display ID, label, and confidence; long text is elided.
        viewport: Visible canvas used to bound caption size and placement.

    Note:
        Paint captions after all outlines so intersecting boxes do not draw
        lines through text. Caption font size does not grow during zoom.
    """
    painter.save()
    font = painter.font()
    font.setBold(True)
    painter.setFont(font)
    metrics = QFontMetrics(font)
    text = metrics.elidedText(caption, Qt.TextElideMode.ElideRight, min(280, viewport.width() - 16))
    tag_width = min(viewport.width(), metrics.horizontalAdvance(text) + 14)
    tag_height = metrics.height() + 6
    tag_x = max(viewport.left(), min(rect.left(), viewport.right() - tag_width + 1))
    tag_y = rect.top() - tag_height
    if tag_y < viewport.top():
        tag_y = rect.top()
    tag_y = max(viewport.top(), min(tag_y, viewport.bottom() - tag_height + 1))
    tag_rect = QRect(tag_x, tag_y, tag_width, tag_height)
    painter.fillRect(tag_rect, QColor("#151a22"))
    painter.fillRect(QRect(tag_x, tag_y, 3, tag_height), color)
    painter.setPen(QColor("#ffffff"))
    painter.drawText(tag_rect.adjusted(8, 0, -4, 0), Qt.AlignmentFlag.AlignVCenter, text)
    painter.restore()


def draw_active_bbox(painter: QPainter, rect: QRect, border_width: int = 2) -> None:
    """
    Draw the active bbox with center marker and drag handles.

    Args:
        painter: Active Qt painter to draw with.
        rect: Bounding-box rectangle in widget coordinates.
        border_width: Width of the outline pen in pixels.
    """
    painter.setPen(QPen(_BOX_COLOR, border_width, Qt.PenStyle.SolidLine))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawRect(rect)

    cx, cy = rect.center().x(), rect.center().y()
    painter.setPen(QPen(_BOX_COLOR, 1))
    painter.setBrush(QBrush(_CENTER_COLOR))
    center_radius = _HANDLE_DRAW_R + 2
    painter.drawEllipse(QPoint(cx, cy), center_radius, center_radius)

    for pt in get_handle_points_from_rect(rect):
        painter.setPen(QPen(_HANDLE_BORDER, 1))
        painter.setBrush(QBrush(_HANDLE_COLOR))
        painter.drawEllipse(pt, _HANDLE_DRAW_R, _HANDLE_DRAW_R)


def draw_selected_bbox(painter: QPainter, rect: QRect, border_width: int = 2) -> None:
    """
    Draw a selection outline without edit handles.

    Args:
        painter: Active Qt painter to draw with.
        rect: Bounding-box rectangle in widget coordinates.
        border_width: Width of the outline pen in pixels.
    """
    painter.setPen(QPen(_BOX_COLOR, border_width, Qt.PenStyle.SolidLine))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawRect(rect)
