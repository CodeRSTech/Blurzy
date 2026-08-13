from __future__ import annotations

from typing import TYPE_CHECKING


from PySide6.QtGui import QImage
if TYPE_CHECKING:
    from app.infrastructure.dtypes import RGBFrame





def rgb_frame_to_q_image(frame: RGBFrame) -> QImage:
    height, width, _ = frame.shape
    bytes_per_line = 3 * width
    return QImage(
        frame.data,
        width,
        height,
        bytes_per_line,
        QImage.Format.Format_RGB888,
    ).copy()
