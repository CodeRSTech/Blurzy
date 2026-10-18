from __future__ import annotations

import numpy as np

from app.domain.detection import BoxSource
from app.domain.views import BBoxViewModel
from app.infrastructure.tracking.deepsort_strategy import DeepSortStrategy


def _box(x: int, *, label: str = "person", confidence: float = 0.9) -> BBoxViewModel:
    return BBoxViewModel(
        id=f"det-{x}",
        source=BoxSource.DETECTION,
        label=label,
        bbox_xyxy=(x, 10, x + 20, 50),
        color_hex="#ffffff",
        confidence=confidence,
    )


def test_deepsort_uses_isolated_gallery_ema_and_caps_gallery() -> None:
    strategy = DeepSortStrategy()
    first = _box(0)
    strategy.update_frame(0, [first], embeddings=[np.asarray([1.0, 0.0])])
    track = strategy._tracks[0]
    assert strategy.uses_appearance
    assert len(track.gallery) == 1

    overlapping = _box(1)
    strategy.update_frame(
        1, [overlapping, _box(0)], embeddings=[np.asarray([0.0, 1.0]), np.asarray([1.0, 0.0])],
    )
    assert len(track.gallery) == 1

    for frame_idx in range(2, 35):
        strategy.update_frame(frame_idx, [_box(0)], embeddings=[np.asarray([1.0, 0.0])])
    assert len(track.gallery) == 30
    np.testing.assert_allclose(track.ema, np.asarray([1.0, 0.0]))


def test_deepsort_wide_radius_reid_keeps_id_at_zero_iou() -> None:
    strategy = DeepSortStrategy()
    descriptor = np.asarray([1.0, 0.0, 0.0])
    first = strategy.update_frame(0, [_box(0)], embeddings=[descriptor])[0]
    strategy.update_frame(1, [_box(5)], embeddings=[descriptor])

    recovered = strategy.update_frame(2, [_box(150)], embeddings=[descriptor])
    detection = next(item for item in recovered if item.detection_backed)
    assert detection.id == first.id
    assert detection.bbox_xyxy == (150, 10, 170, 50)


def test_deepsort_update_frame_extracts_embeddings_from_rgb_frame() -> None:
    class Extractor:
        def __init__(self) -> None:
            self.called = False

        def extract_for_boxes(self, frame, boxes):
            self.called = frame is not None and len(boxes) == 1
            return [np.asarray([0.0, 1.0])]

    extractor = Extractor()
    strategy = DeepSortStrategy(appearance_extractor=extractor)
    frame = np.zeros((64, 64, 3), dtype=np.uint8)
    output = strategy.update_frame(0, [_box(0)], frame=frame)

    assert extractor.called
    assert len(output) == 1
    assert output[0].source == BoxSource.TRACKING_DEEPSORT
    assert output[0].detection_backed
    assert output[0].key == "track:1"
    assert not hasattr(output[0], "embedding")
