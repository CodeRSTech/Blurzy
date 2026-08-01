from __future__ import annotations

from dataclasses import dataclass

from app.domain.base.dtypes import BBoxXYXYTuple
from app.domain.detection import BoxSource


@dataclass(slots=True)
class BBoxViewModel:
    """
    Bounding detection display model — binds detection/tracking/manual detection to UI table row.

    Attributes:
        id (str): Display ID, such as ``"yolo-1"`` or ``"track-42"``.
        source (BoxSource): Origin, e.g. ``AnnotationBoxSource.DETECTION``, ``AnnotationBoxSource.MANUAL``.
        label (str): Class name, such as ``"person"`` or ``"car"``.
        bbox_xyxy (BBoxTuple): Coordinates ``(x1, y1, x2, y2)`` in pixels.
        color_hex (str): Display color in ``#RRGGBB`` format.
        confidence: Score from 0.0 to 1.0, or ``None`` for manual boxes.
        key (str): Unique key for selection and editing.

    Note:
        Stored in ``SessionDataStore`` and displayed in the UI table for the
        current frame. ``confidence_txt`` and ``bbox_txt`` expose formatted
        display values, and ``clone()`` provides a fast shallow copy.
    """

    id: str
    source: BoxSource
    label: str
    bbox_xyxy: BBoxXYXYTuple
    color_hex: str
    # [AUDIT] TYPE SAFETY: Type detection doesn't match reality
    # Attribute documented as "Score... or None for manual boxes" (line 28)
    # but type hint is `float` not `float | None`.
    # This creates potential None-checking bugs if confidence is treated as float.
    # Fix: Change to `confidence: float | None` to match actual usage and enable type checking.
    # See confidence_txt property (line 47) which handles None case.
    confidence: float
    key: str = ""

    @property
    def confidence_txt(self) -> str:
        return f"{self.confidence:.2f}" if self.confidence is not None else "N/A"

    @property
    def bbox_txt(self) -> str:
        return f"({self.bbox_xyxy[0]}, {self.bbox_xyxy[1]}), ({self.bbox_xyxy[2]}, {self.bbox_xyxy[3]})"

    @property
    def is_manual(self) -> bool:
        return self.source == BoxSource.MANUAL

    @property
    def is_detection(self) -> bool:
        return self.source == BoxSource.DETECTION

    def clone(self) -> "BBoxViewModel":
        """Create shallow copy (all fields are immutable or copied)."""
        # Explicitly pass the attributes to a new instance.
        # (Adjust these arguments to match your actual class __init__)
        return BBoxViewModel(
            id=self.id,
            source=self.source,
            label=self.label,
            bbox_xyxy=self.bbox_xyxy,
            color_hex=self.color_hex,
            confidence=self.confidence,
            key=self.key
        )
