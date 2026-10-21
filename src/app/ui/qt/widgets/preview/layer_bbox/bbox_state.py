"""Module for bbox state; implements the Qt presentation components.

Layer: Presentation.
Context: Implements the qt presentation components at this architectural boundary.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from PySide6.QtCore import QRect, QPoint

from app.ui.qt.widgets.preview.layer_bbox.bbox_drag import DragMode


@dataclass
class BBoxState:
    """Represent bbox state.

    Attributes:
        rect: Stored rect value.
        drag_mode: Stored drag mode value.
        drag_origin: Stored drag origin value.
        rect_at_drag_start: Stored rect at drag start value.

Layer: Presentation.
Context: Supports user interaction and delegates application work through presentation contracts.
"""
    rect: QRect = field(default_factory=QRect)
    drag_mode: DragMode = DragMode.NONE
    drag_origin: QPoint = field(default_factory=QPoint)
    rect_at_drag_start: QRect = field(default_factory=QRect)

    @property
    def has_valid_rect(self) -> bool:
        """Return whether the rectangle has positive width and height.

        Returns:
            `True` when the rectangle is non-null and has positive dimensions.
        """
        return not self.rect.isNull() and self.rect.width() > 0 and self.rect.height() > 0

    def __repr__(self) -> str:
        return f"_BBoxState(rect={self.rect}, drag_mode={self.drag_mode}, drag_origin={self.drag_origin}, rect_at_drag_start={self.rect_at_drag_start})"

    def __str__(self) -> str:
        return f"BBoxState(rect={self.rect}, drag_mode={self.drag_mode}, drag_origin={self.drag_origin}, rect_at_drag_start={self.rect_at_drag_start})"
