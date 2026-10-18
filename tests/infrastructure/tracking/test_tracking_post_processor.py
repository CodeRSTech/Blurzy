from __future__ import annotations

import numpy as np

from app.domain.detection import BoxSource
from app.domain.views import BBoxViewModel
from app.infrastructure.tracking.post_processor import TrackingPostProcessor


def _box(
    track_id: str,
    bbox: tuple[int, int, int, int],
    *,
    label: str = "person",
) -> BBoxViewModel:
    return BBoxViewModel(
        id=track_id,
        source=BoxSource.TRACKING_HUNGARIAN,
        label=label,
        bbox_xyxy=bbox,
        color_hex="#123456",
        confidence=0.9,
        key=f"track:{track_id}",
    )


def test_links_compatible_tracklets_and_interpolates_only_the_gap():
    tracked = {
        0: [_box("track-1", (0, 0, 10, 10))],
        1: [_box("track-1", (2, 0, 12, 10))],
        4: [_box("track-2", (8, 0, 18, 10))],
        5: [_box("track-2", (10, 0, 20, 10))],
    }

    result = TrackingPostProcessor().process(tracked)

    assert [result[index][0].id for index in (0, 1, 2, 3, 4, 5)] == [
        "track-1",
        "track-1",
        "track-1",
        "track-1",
        "track-1",
        "track-1",
    ]
    assert result[2][0].bbox_xyxy[0] in range(4, 7)
    assert result[3][0].bbox_xyxy[0] in range(6, 9)
    assert tracked[4][0].id == "track-2"


def test_interpolates_a_gap_inside_one_reassociated_track_id():
    tracked = {
        0: [_box("track-1", (0, 0, 10, 10))],
        1: [_box("track-1", (2, 0, 12, 10))],
        4: [_box("track-1", (8, 0, 18, 10))],
        5: [_box("track-1", (10, 0, 20, 10))],
    }

    result = TrackingPostProcessor().process(tracked)

    assert result[2][0].id == "track-1"
    assert result[3][0].id == "track-1"


def test_does_not_link_across_long_gaps_and_limits_unbridged_tail():
    tracked = {
        0: [_box("track-1", (0, 0, 10, 10))],
        1: [_box("track-1", (2, 0, 12, 10))],
        27: [_box("track-2", (54, 0, 64, 10))],
    }

    result = TrackingPostProcessor().process(tracked)

    assert result[1][0].id == "track-1"
    assert result[27][0].id == "track-2"
    assert result[2][0].detection_backed is False
    assert result[7][0].detection_backed is False
    assert result[8] == []
    assert result[26] == []


def test_does_not_link_different_labels():
    tracked = {
        0: [_box("track-1", (0, 0, 10, 10), label="person")],
        1: [_box("track-2", (2, 0, 12, 10), label="car")],
    }

    result = TrackingPostProcessor().process(tracked)

    assert result[0][0].id == "track-1"
    assert result[1][0].id == "track-2"


def test_rejects_equally_plausible_tracklet_targets():
    tracked = {
        0: [_box("track-1", (0, 0, 10, 10))],
        1: [_box("track-1", (0, 0, 10, 10))],
        2: [],
        3: [_box("track-2", (0, 0, 10, 10)), _box("track-3", (0, 0, 10, 10))],
        4: [_box("track-2", (0, 0, 10, 10)), _box("track-3", (0, 0, 10, 10))],
    }

    result = TrackingPostProcessor().process(tracked)

    assert [box.id for box in result[3]] == ["track-2", "track-3"]
    assert result[2][0].detection_backed is False


def test_causal_mode_emits_normal_decay_coasts_without_offline_stitching():
    tracked = {
        0: [_box("track-1", (0, 0, 10, 10))],
        1: [_box("track-1", (2, 0, 12, 10))],
        4: [_box("track-1", (8, 0, 18, 10))],
    }
    processor = TrackingPostProcessor(
        offline_stitching_enabled=False,
        confidence_decay=0.05,
        min_confidence=0.1,
    )

    result = processor.process(tracked, total_frames=5)

    assert result[2][0].detection_backed is False
    assert result[2][0].bbox_xyxy == (4, 0, 14, 10)
    assert result[2][0].confidence == 0.85
    assert result[3][0].time_since_update == 2
    assert result[4][0].detection_backed is True


def test_causal_mode_keeps_tracker_prediction_and_filters_low_confidence_coast():
    observed = _box("track-1", (0, 0, 10, 10))
    predicted = _box("track-1", (50, 0, 60, 10))
    predicted.detection_backed = False
    predicted.time_since_update = 1
    predicted.confidence = 0.7
    below_floor = _box("track-2", (100, 0, 110, 10))
    below_floor.detection_backed = False
    below_floor.time_since_update = 1
    below_floor.confidence = 0.05

    result = TrackingPostProcessor(
        offline_stitching_enabled=False,
        min_confidence=0.1,
    ).process({0: [observed], 1: [predicted, below_floor]}, total_frames=2)

    assert [box.id for box in result[1]] == ["track-1"]
    assert result[1][0].bbox_xyxy == (50, 0, 60, 10)
    assert result[1][0].confidence == 0.7


def test_offline_unbridged_tail_uses_double_decay_and_six_frame_cap():
    tracked = {0: [_box("track-1", (0, 0, 10, 10))]}
    processor = TrackingPostProcessor(
        confidence_decay=0.05,
        min_confidence=0.1,
        max_unbridged_coast=6,
    )

    result = processor.process(tracked, total_frames=10)

    assert result[1][0].confidence == 0.8
    assert result[6][0].confidence == 0.3
    assert result[7] == []


def test_gsi_smoothness_changes_blended_gap_trajectory():
    tracked = {
        0: [_box("track-1", (0, 0, 10, 10))],
        1: [_box("track-1", (2, 0, 12, 10))],
        5: [_box("track-2", (10, 0, 20, 10))],
        6: [_box("track-2", (14, 0, 24, 10))],
    }
    tight = TrackingPostProcessor(gsi_smoothness=1.0).process(tracked, total_frames=7)
    smooth = TrackingPostProcessor(gsi_smoothness=10.0).process(tracked, total_frames=7)

    assert tight[2][0].id == smooth[2][0].id == "track-1"
    assert tight[2][0].bbox_xyxy != smooth[2][0].bbox_xyxy


def test_strong_appearance_stitches_tracklets_after_reversal():
    tracked = {
        0: [_box("track-1", (0, 0, 10, 10))],
        1: [_box("track-1", (2, 0, 12, 10))],
        4: [_box("track-2", (100, 0, 110, 10))],
        5: [_box("track-2", (98, 0, 108, 10))],
    }
    appearance = {
        frame: {track_id: np.asarray([1.0, 0.0], dtype=np.float32)}
        for frame, track_id in ((0, "track-1"), (1, "track-1"), (4, "track-2"), (5, "track-2"))
    }

    result = TrackingPostProcessor().process(
        tracked,
        appearance_embeddings_by_frame=appearance,
    )

    assert result[4][0].id == "track-1"
    assert result[2][0].detection_backed is False


def test_appearance_disagreement_rejects_geometrically_linkable_tracklets():
    tracked = {
        0: [_box("track-1", (0, 0, 10, 10))],
        1: [_box("track-1", (2, 0, 12, 10))],
        4: [_box("track-2", (8, 0, 18, 10))],
        5: [_box("track-2", (10, 0, 20, 10))],
    }
    appearance = {
        0: {"track-1": np.asarray([1.0, 0.0], dtype=np.float32)},
        1: {"track-1": np.asarray([1.0, 0.0], dtype=np.float32)},
        4: {"track-2": np.asarray([0.0, 1.0], dtype=np.float32)},
        5: {"track-2": np.asarray([0.0, 1.0], dtype=np.float32)},
    }

    result = TrackingPostProcessor().process(
        tracked,
        appearance_embeddings_by_frame=appearance,
    )

    assert result[0][0].id == "track-1"
    assert result[4][0].id == "track-2"
