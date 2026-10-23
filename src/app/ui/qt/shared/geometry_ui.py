"""
Module for geometry ui; implements the Qt presentation components.

See Also:
    - [`draw_active_bbox`][app.ui.qt.widgets.preview.layer_bbox.rendering.draw_active_bbox] — draws geometry using widget-space handles
    - [`AnnotationOverlayWidget`][app.ui.qt.widgets.preview.layer_bbox.layer_bbox.AnnotationOverlayWidget] — consumes the geometry helpers

Layer: Presentation.
Context: Implements the qt presentation components at this architectural boundary.
"""

from __future__ import annotations

from typing import TYPE_CHECKING


from PySide6.QtCore import QPoint
if TYPE_CHECKING:
    from PySide6.QtCore import QRect


def get_handle_points_from_rect(rect: QRect) -> list[QPoint]:
    """
    Return the eight corner and edge-midpoint handles of a rectangle.

    Args:
        rect: Rectangle whose handle positions are calculated.

    Returns:
        Points ordered clockwise from the top-left corner, omitting the center.
    """
    x1, y1, x2, y2 = rect.left(), rect.top(), rect.right(), rect.bottom()
    mx, my = (x1 + x2) // 2, (y1 + y2) // 2
    return [
        QPoint(x1, y1),
        QPoint(mx, y1),
        QPoint(x2, y1),
        QPoint(x1, my),
        QPoint(x2, my),
        QPoint(x1, y2),
        QPoint(mx, y2),
        QPoint(x2, y2),
    ]
