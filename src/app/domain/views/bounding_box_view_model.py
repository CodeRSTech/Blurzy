"""Module for bounding box view model; defines application concepts without UI or infrastructure dependencies.

See Also:
    - [`Box`][app.domain.detection.box.Box] — domain geometry represented by the view model
    - [`DetectionResult`][app.domain.detection.result.DetectionResult] — detection output converted to this view model

Layer: Domain.
Context: Defines application concepts without ui or infrastructure dependencies at this architectural boundary.
"""

from __future__ import annotations

from typing import TYPE_CHECKING


from dataclasses import dataclass


from app.domain.detection import BoxSource
if TYPE_CHECKING:
    from app.domain.base.dtypes import BBoxXYXYTuple



@dataclass(slots=True)
class BBoxViewModel:
    """
    Bounding detection display model — binds detection/tracking/manual detection to UI table row.

    Attributes:
        id (str): Display ID, such as `"yolo-1"` or `"track-42"`.
        source (BoxSource): Origin, e.g. `AnnotationBoxSource.DETECTION`, `AnnotationBoxSource.MANUAL`.
        label (str): Class name, such as `"person"` or `"car"`.
        bbox_xyxy (BBoxTuple): Coordinates `(x1, y1, x2, y2)` in pixels.
        color_hex (str): Display color in `#RRGGBB` format.
        confidence: Score from 0.0 to 1.0, or `None` for manual boxes.
        key (str): Unique key for selection and editing.
        detection_backed (bool): Whether the tracker observed a detection on this frame.
        time_since_update (int): Number of consecutive frames since a detection matched.

    Note:
        Stored in `SessionDataStore` and displayed in the UI table for the
        current frame. `confidence_txt` and `bbox_txt` expose formatted
        display values, and `clone()` provides a fast shallow copy.


Layer: Domain.
Context: Represents application concepts without UI or infrastructure dependencies.
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
    detection_backed: bool = True
    time_since_update: int = 0

    @property
    def confidence_txt(self) -> str:
        """Format confidence for display in the annotation table.

        Returns:
            Confidence rounded to two decimal places, or `"N/A"` when absent.
        """
        return f"{self.confidence:.2f}" if self.confidence is not None else "N/A"

    @property
    def bbox_txt(self) -> str:
        """Format box coordinates for display.

        Returns:
            Coordinate string in `(x1, y1), (x2, y2)` format.
        """
        return f"({self.bbox_xyxy[0]}, {self.bbox_xyxy[1]}), ({self.bbox_xyxy[2]}, {self.bbox_xyxy[3]})"

    @property
    def is_manual(self) -> bool:
        """Return whether the box was created manually.

        Returns:
            `True` when the box source is manual.
        """
        return self.source == BoxSource.MANUAL

    @property
    def is_detection(self) -> bool:
        """Return whether the box originated from detection.

        Returns:
            `True` when the box source is detection.
        """
        return self.source == BoxSource.DETECTION

    def clone(self) -> "BBoxViewModel":
        """Create an independent shallow copy of this bounding box.


        Returns:
            A box with identical identity, geometry, and tracking observation metadata.


        Note:
            The tuple geometry and scalar metadata are immutable values and are copied
            by assignment; later field replacement does not affect the original.

        Example:
            editable = box.clone()
        """
        # Explicitly pass the attributes to a new instance.
        # (Adjust these arguments to match your actual class __init__)
        return BBoxViewModel(
            id=self.id,
            source=self.source,
            label=self.label,
            bbox_xyxy=self.bbox_xyxy,
            color_hex=self.color_hex,
            confidence=self.confidence,
            key=self.key,
            detection_backed=self.detection_backed,
            time_since_update=self.time_since_update,
        )
