"""Module for box io; provides reusable helpers across application layers.

Layer: Shared utilities.
Context: Provides reusable helpers across application layers at this architectural boundary.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.domain import BBoxViewModel
from app.domain.detection.source import BoxSource

if TYPE_CHECKING:
    from app.domain.base.dtypes import ListOfBoxes


def box_to_dict(box: BBoxViewModel) -> dict[str, object]:
    """Serialize a box view model to a JSON-compatible mapping.

    Args:
        box: Bounding box whose fields are serialized.

    Returns:
        Mapping containing the box ID, source, label, coordinates, color, confidence, and key.
    """
    return {
        "id": box.id,
        "source": box.source.value,
        "label": box.label,
        "bbox_xyxy": list(box.bbox_xyxy),
        "color_hex": box.color_hex,
        "confidence": box.confidence,
        "key": box.key,
    }


def dict_to_box(data: dict[str, object]) -> BBoxViewModel:
    """Build a box view model from its serialized fields.

    Args:
        data: Mapping with `id`, `source`, `label`, `bbox_xyxy`, and `color_hex`; `confidence` and `key` are optional.

    Returns:
        Box view model populated from the mapping.
    """
    return BBoxViewModel(
        id=str(data["id"]),
        source=BoxSource(str(data["source"])),
        label=str(data["label"]),
        bbox_xyxy=tuple(data["bbox_xyxy"]),  # type: ignore[arg-type]
        color_hex=str(data["color_hex"]),
        confidence=data.get("confidence"),  # type: ignore[arg-type]
        key=str(data.get("key", "")),
    )
