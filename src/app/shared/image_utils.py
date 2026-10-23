"""
Module for image utils; provides reusable helpers across application layers.

See Also:
    - [`UIHandler`][app.ui.handlers.ui_handler.UIHandler] — converts displayed frames for the UI
    - [`VideoDisplayWidget`][app.ui.qt.widgets.preview.layer_video.VideoDisplayWidget] — presents video frames

Layer: Shared utilities.
Context: Provides reusable helpers across application layers at this architectural boundary.
"""

from __future__ import annotations

from typing import TYPE_CHECKING


from PySide6.QtGui import QImage
if TYPE_CHECKING:
    from app.infrastructure.dtypes import RGBFrame




def rgb_frame_to_q_image(frame: RGBFrame) -> QImage:
    """
    Copy an RGB frame into a Qt image.

    Args:
        frame: Three-channel RGB pixel array.

    Returns:
        Independent Qt image copy in RGB888 format.
    """
    height, width, _ = frame.shape
    bytes_per_line = 3 * width
    return QImage(
        frame.data,
        width,
        height,
        bytes_per_line,
        QImage.Format.Format_RGB888,
    ).copy()
