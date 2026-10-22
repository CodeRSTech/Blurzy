"""Module for constants; implements the Qt presentation components.

See Also:
    - [`AnnotationOverlayWidget`][app.ui.qt.widgets.preview.layer_bbox.layer_bbox.AnnotationOverlayWidget]
    - [`rendering`][app.ui.qt.widgets.preview.layer_bbox.rendering]

Layer: Presentation.
Context: Implements the qt presentation components at this architectural boundary.
"""

from __future__ import annotations

from PySide6.QtGui import QColor

_BOX_COLOR = QColor(255, 80, 80)
_CENTER_COLOR = QColor(255, 255, 255, 180)
_HANDLE_BORDER = QColor(200, 40, 40)
_HANDLE_COLOR = QColor(255, 255, 255)
_HANDLE_DRAW_R = 5
_HANDLE_RADIUS = 6
_MIN_BBOX_PX = 4
