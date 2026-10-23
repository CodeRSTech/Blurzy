"""
Module for frame overlay; provides reusable helpers across application layers.

See Also:
    - [`UIHandler`][app.ui.handlers.ui_handler.UIHandler] — composes overlays for displayed frames
    - [`BBoxViewModel`][app.domain.views.bounding_box_view_model.BBoxViewModel] — provides annotation geometry and styling

Layer: Shared utilities.
Context: Provides reusable helpers across application layers at this architectural boundary.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import cv2

from app.shared.logging_cfg import get_logger

if TYPE_CHECKING:
    from app.infrastructure.dtypes import RGBFrame, ListOfBoxes

logger = get_logger("Shared->Frame Overlay")


def draw_frame_overlays(
        frame: RGBFrame,
        boxes: ListOfBoxes | None,
        border_width: int = 2,
) -> RGBFrame:
    """
    Draw preview box borders and labels onto a copy of an RGB frame.

    Args:
        frame: RGB frame to annotate.
        boxes: Boxes displayed in the current editor tab, or `None` for none.
        border_width: Border width in pixels from 1 to 10.

    Returns:
        A frame with overlays, or the original frame if there are no boxes.

    Raises:
        ValueError: If `border_width` is outside the inclusive range 1..10.

    Note:
        This helper is editor-only; exported video rendering never calls it.

    Example:
        preview = draw_frame_overlays(frame, tracked_boxes, border_width=3)
    """
    if not 1 <= border_width <= 10:
        raise ValueError("border_width must be between 1 and 10.")
    if not boxes:
        return frame

    result = frame.copy()

    if not boxes:
        return result

    for item in boxes:
        # 1. Unpack the tuple directly! No string parsing needed.
        x1, y1, x2, y2 = item.bbox_xyxy

        color = _hex_to_rgb(item.color_hex)
        _ = cv2.rectangle(result, (x1, y1), (x2, y2), color, border_width)

        label = f"{item.id}:{item.label} {item.confidence_txt}"
        _ = cv2.putText(
            result,
            label,
            (x1, max(15, y1 - 6)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            color,
            1,
            cv2.LINE_AA,
        )

    return result


def _hex_to_rgb(color_hex: str) -> tuple[int, int, int]:
    value = color_hex.lstrip("#")
    if len(value) != 6:
        return 0, 255, 0

    try:
        r = int(value[0:2], 16)
        g = int(value[2:4], 16)
        b = int(value[4:6], 16)
    except ValueError:
        return 0, 255, 0

    return r, g, b
