from __future__ import annotations

from typing import TYPE_CHECKING


from PySide6.QtCore import QPoint
if TYPE_CHECKING:
    from PySide6.QtCore import QRect



def get_handle_points_from_rect(rect: QRect) -> list[QPoint]:
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
