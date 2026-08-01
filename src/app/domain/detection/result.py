"""Detection result — output from YOLO object detection model."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, override

from app.domain.detection.source import BoxSource
from app.domain.detection.box import Box
from app.shared.logging_cfg import get_logger

if TYPE_CHECKING:
    from app.domain.views import BBoxViewModel

logger = get_logger("Domain->Detection")


@dataclass(slots=True)
class DetectionResult(Box):
    """
    Single object detection result from YOLO model inference.

    All bounding-detection fields (``item_id``, ``label``, ``bbox_xyxy``, ``confidence``,
    ``color_hex``) are inherited from :class:`BaseBox`.  See that class for field
    documentation.

    Note:
        Created from raw YOLO output, stored in Layer A as immutable machine
        data, then filtered into Layer B for user review and export. Use
        ``to_frame_box_view_model()`` to convert the detection into a
        ``BBoxViewModel`` for UI display.

    Example:

        .. code-block:: python

            detection = DetectionResult(
                item_id="yolo-42",
                label="person",
                bbox_xyxy=(100, 200, 300, 400),  # (x1, y1, x2, y2)
                confidence=0.95,
                color_hex="#808080"
            )

            box_view = detection.to_frame_box_view_model()
    """

    def to_frame_box_view_model(self) -> BBoxViewModel:
        from app.domain.views.bounding_box_view_model import BBoxViewModel  # lazy — avoids circular import
        return BBoxViewModel(
            id=self.item_id,
            source=BoxSource.DETECTION,
            label=self.label,
            bbox_xyxy=self.bbox_xyxy,
            color_hex=self.color_hex,
            confidence=self.confidence,
            key=f"det:{self.item_id}"  # <-- Allows Detection Boxes to Be Selected, Edited, Deleted, or Duplicated
        )

    def __post_init__(self) -> None:
        logger.trace("Created detection result {}", self)

    # @override
    # def __repr__(self) -> str:
    #    return f"DetectionResult(bbox_xyxy={self.bbox_xyxy}, confidence={self.confidence:.2f}, label={self.label}, item_id={self.item_id})"

    @override
    def __str__(self) -> str:
        return f"DetectionResult<id={self.item_id}, lbl={self.label})>, (x1,y1,x2,y2)={self.bbox_xyxy}, cnf={self.confidence:.2f}>"

    @override
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, DetectionResult):
            return NotImplemented
        return self.bbox_xyxy == other.bbox_xyxy and self.label == other.label and self.item_id == other.item_id
