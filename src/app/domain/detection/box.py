"""Base bounding-detection domain dataclass — base core for detection and tracking results."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.domain.base.dtypes import BBoxXYXYTuple


@dataclass(slots=True)
class Box:
    """
    Shared bounding-detection base for detection and tracking domain results.

    Attributes:
        item_id (str): Unique identifier for this detection, e.g. ``"yolo-42"`` or ``"track-7"``.
        label (str): Class name of the annotated object, such as ``"person"`` or ``"car"``.
        bbox_xyxy (BBoxXYXYTuple): Bounding detection ``(x1, y1, x2, y2)`` in pixel coordinates.
        confidence (float): Confidence score from 0.0 to 1.0.
        color_hex (str): Display color in ``#RRGGBB`` format; defaults to gray ``"#808080"``.

    Note:
        Common fields base by ``DetectionResult`` and any future tracking result
        domain types.  Introducing this base eliminates field duplication while
        preserving clean domain → view boundaries.

    Example:

        .. code-block:: python

            detection = Box(
                item_id="yolo-1",
                label="person",
                bbox_xyxy=(10, 20, 100, 200),
                confidence=0.9,
            )
    """

    item_id: str
    label: str
    bbox_xyxy: BBoxXYXYTuple
    confidence: float
    color_hex: str = "#808080"
