"""Rendering primitives for drawing active bbox visuals.

This module contains paint-only helpers and does not mutate widget state.
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



def draw_active_bbox(painter: QPainter, rect: QRect) -> None:
    """Draw the active bbox with center marker and drag handles."""
    painter.setPen(QPen(_BOX_COLOR, 2, Qt.PenStyle.SolidLine))
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
