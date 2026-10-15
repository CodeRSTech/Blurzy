from __future__ import annotations

from app.domain.detection import BoxSource
from app.domain.views import BBoxViewModel
from app.infrastructure.tracking.box_deduplication import suppress_nested_same_class_boxes


def _box(
    box_id: str,
    coords: tuple[int, int, int, int],
    *,
    confidence: float,
    label: str = "person",
) -> BBoxViewModel:
    return BBoxViewModel(
        id=box_id,
        source=BoxSource.DETECTION,
        label=label,
        bbox_xyxy=coords,
        color_hex="#ffffff",
        confidence=confidence,
        key=box_id,
    )


def test_suppresses_frame_172_torso_and_keeps_separate_person_with_union_coverage():
    full_body = _box("torch-0", (682, 447, 1573, 2137), confidence=1.0)
    torso = _box("torch-4", (676, 458, 1539, 1322), confidence=0.99)
    second_person = _box("torch-3", (1594, 204, 2208, 1642), confidence=0.99)
    second_person_head = _box("torch-13", (1742, 209, 2101, 792), confidence=0.87)

    result = suppress_nested_same_class_boxes(
        [torso, second_person_head, second_person, full_body]
    )

    assert [box.id for box in result] == ["torch-0", "torch-3"]
    assert result[0].bbox_xyxy == (676, 447, 1573, 2137)
    assert result[1].bbox_xyxy == (1594, 204, 2208, 1642)
    assert full_body.bbox_xyxy == (682, 447, 1573, 2137)


def test_manual_boxes_are_retained_and_same_label_independent_boxes_stay_separate():
    manual = BBoxViewModel(
        id="manual",
        source=BoxSource.MANUAL,
        label="person",
        bbox_xyxy=(0, 0, 20, 40),
        color_hex="#00ff00",
        confidence=1.0,
        key="manual",
    )
    detector_a = _box("a", (100, 100, 150, 200), confidence=0.9)
    detector_b = _box("b", (300, 100, 350, 200), confidence=0.8)

    result = suppress_nested_same_class_boxes([detector_a, manual, detector_b])

    assert [box.id for box in result] == ["manual", "a", "b"]
    assert result[0].source == BoxSource.MANUAL
