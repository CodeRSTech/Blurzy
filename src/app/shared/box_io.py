from __future__ import annotations

from typing import TYPE_CHECKING

from app.domain import BBoxViewModel
from app.domain.detection.source import BoxSource

if TYPE_CHECKING:
    from app.domain.base.dtypes import ListOfBoxes


def box_to_dict(box: BBoxViewModel) -> dict[str, object]:
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
    return BBoxViewModel(
        id=str(data["id"]),
        source=BoxSource(str(data["source"])),
        label=str(data["label"]),
        bbox_xyxy=tuple(data["bbox_xyxy"]),  # type: ignore[arg-type]
        color_hex=str(data["color_hex"]),
        confidence=data.get("confidence"),  # type: ignore[arg-type]
        key=str(data.get("key", "")),
    )
