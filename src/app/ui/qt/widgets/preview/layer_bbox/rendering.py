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


from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QBrush, QPen

from app.ui.qt.shared.geometry_ui import get_handle_points_from_rect
from app.ui.qt.widgets.preview.layer_bbox.constants import (
    _BOX_COLOR,
    _CENTER_COLOR,
    _HANDLE_BORDER,
    _HANDLE_COLOR,
    _HANDLE_DRAW_R,
)
if TYPE_CHECKING:
    from PySide6.QtCore import QRect
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
