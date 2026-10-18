from __future__ import annotations

import numpy as np
import pytest

from app.domain.detection import BoxSource
from app.domain.views import BBoxViewModel
from app.infrastructure.tracking.botsort_strategy import BotSortStrategy
from app.infrastructure.tracking.deepsort_strategy import DeepSortStrategy


def _box(x: int, *, width: int = 20, color: str = "red") -> BBoxViewModel:
    return BBoxViewModel(
        id=f"det-{color}-{x}",
        source=BoxSource.DETECTION,
        label="person",
        bbox_xyxy=(x, 10, x + width, 50),
        color_hex="#ffffff",
        confidence=0.9,
    )


def _embedding(color: str) -> np.ndarray:
    return np.asarray([1.0, 0.0], dtype=np.float32) if color == "red" else np.asarray([0.0, 1.0], dtype=np.float32)


@pytest.mark.parametrize("strategy_type", [DeepSortStrategy, BotSortStrategy])
def test_zigzag_runner_keeps_identity_through_three_missed_frames(strategy_type):
    strategy = strategy_type()
    output = []
    positions = [0, 5, 10, None, None, None, -20, -10]
    for frame_idx, position in enumerate(positions):
        detections = [] if position is None else [_box(position)]
        embeddings = [] if position is None else [_embedding("red")]
        output.extend(strategy.update_frame(frame_idx, detections, embeddings=embeddings))

    observed_ids = {box.id for box in output if box.detection_backed}
    assert observed_ids == {"track-1"}
    assert any(box.time_since_update == 3 for box in output)


@pytest.mark.parametrize("strategy_type", [DeepSortStrategy, BotSortStrategy])
def test_crossing_paths_keep_distinct_subject_ids_without_contaminating_prototypes(strategy_type):
    strategy = strategy_type()
    first_red = _box(0, color="red")
    first_blue = _box(80, color="blue")
    strategy.update_frame(0, [first_red, first_blue], embeddings=[_embedding("red"), _embedding("blue")])
    strategy.update_frame(
        1,
        [_box(5, color="red"), _box(75, color="blue")],
        embeddings=[_embedding("red"), _embedding("blue")],
    )
    crossing = strategy.update_frame(
        2,
        [_box(35, color="red"), _box(40, color="blue")],
        embeddings=[_embedding("red"), _embedding("blue")],
    )

    assert {box.id for box in crossing if box.detection_backed} == {"track-1", "track-2"}
    # The crossing detections overlap, so neither prototype may incorporate the
    # ambiguous appearance vectors while identities are passing one another.
    if strategy_type is DeepSortStrategy:
        prototypes = [track.ema.copy() for track in strategy._tracks]
        strategy.update_frame(
            3,
            [_box(75, color="blue"), _box(5, color="red")],
            embeddings=[_embedding("blue"), _embedding("red")],
        )
        assert np.allclose(prototypes[0], _embedding("red"))
        assert np.allclose(prototypes[1], _embedding("blue"))
    else:
        prototypes = [track.appearance.copy() for track in strategy._tracks]
        strategy.update_frame(
            3,
            [_box(75, color="blue"), _box(5, color="red")],
            embeddings=[_embedding("blue"), _embedding("red")],
        )
        assert np.allclose(prototypes[0], _embedding("red"))
        assert np.allclose(prototypes[1], _embedding("blue"))

    final_observed = [box for box in strategy.update_frame(
        4,
        [_box(80, color="blue"), _box(0, color="red")],
        embeddings=[_embedding("blue"), _embedding("red")],
    ) if box.detection_backed]
    assert [(box.id, box.bbox_xyxy[0] < 20) for box in final_observed] == [
        ("track-1", True),
        ("track-2", False),
    ]
