from __future__ import annotations

from dataclasses import dataclass, field

from PySide6.QtCore import QRect, QPoint

from app.ui.qt.data.bbox_drag import DragMode


@dataclass
class BBoxState:
    rect: QRect = field(default_factory=QRect)
    drag_mode: DragMode = DragMode.NONE
    drag_origin: QPoint = field(default_factory=QPoint)
    rect_at_drag_start: QRect = field(default_factory=QRect)

    @property
    def has_valid_rect(self) -> bool:
        return not self.rect.isNull()

    def __repr__(self) -> str:
        return f"_BBoxState(rect={self.rect}, drag_mode={self.drag_mode}, drag_origin={self.drag_origin}, rect_at_drag_start={self.rect_at_drag_start})"

    def __str__(self) -> str:
        return f"BBoxState(rect={self.rect}, drag_mode={self.drag_mode}, drag_origin={self.drag_origin}, rect_at_drag_start={self.rect_at_drag_start})"
