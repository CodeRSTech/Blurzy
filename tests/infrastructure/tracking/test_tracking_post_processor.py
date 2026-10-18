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


def test_privacy_antishrink_preserves_top_anchor_for_torso_detections():
    tracked = {
        frame: [_box("track-1", (100, 100, 220, 400))]
        for frame in range(6)
    }
    tracked.update(
        {
            frame: [_box("track-1", (105, 102, 215, 230))]
            for frame in range(6, 11)
        }
    )
    tracked[11] = [_box("track-1", (100, 100, 220, 400))]

    result = TrackingPostProcessor(
        privacy_features_enabled=True,
        resist_box_shrinking=True,
        shrink_resistance=0.85,
        pre_detection_padding_sec=0.0,
        post_detection_padding_sec=0.0,
        box_safety_padding_pct=0.0,
    ).process(tracked, total_frames=12)

    for frame_index in range(6, 11):
        x1, y1, x2, y2 = result[frame_index][0].bbox_xyxy
        assert y1 == 102
        assert y2 > 300
        assert x2 - x1 > 110
    assert result[11][0].bbox_xyxy == (100, 100, 220, 400)


def test_privacy_pre_detection_padding_backfills_configured_frames():
    tracked = {15: [_box("track-1", (100, 100, 140, 180))]}

    result = TrackingPostProcessor(
        privacy_features_enabled=True,
        pre_detection_padding_sec=0.4,
        post_detection_padding_sec=0.0,
        box_safety_padding_pct=0.0,
        fps=25.0,
    ).process(tracked, total_frames=40)

    assert all(result[frame][0].id == "track-1" for frame in range(5, 15))
    assert all(result[frame][0].detection_backed is False for frame in range(5, 15))
    assert all(result[frame][0].time_since_update == 15 - frame for frame in range(5, 15))
    assert result[4] == []


def test_privacy_pre_detection_velocity_is_clamped_before_backward_projection():
    tracked = {
        2: [_box("track-1", (100, 100, 140, 180))],
        3: [_box("track-1", (1000, 1000, 1040, 1080))],
    }

    result = TrackingPostProcessor(
        privacy_features_enabled=True,
        pre_detection_padding_sec=0.04,
        post_detection_padding_sec=0.0,
        box_safety_padding_pct=0.0,
        fps=25.0,
    ).process(tracked, total_frames=4)

    x1, y1, x2, y2 = result[1][0].bbox_xyxy
    assert 90 <= x1 < 100
    assert 80 <= y1 < 100
    assert x2 - x1 == 40
    assert y2 - y1 == 80


def test_privacy_post_detection_hold_keeps_padding_above_confidence_floor():
    tracked = {20: [_box("track-1", (100, 100, 140, 180))]}

    result = TrackingPostProcessor(
        privacy_features_enabled=True,
        pre_detection_padding_sec=0.0,
        post_detection_padding_sec=0.4,
        box_safety_padding_pct=0.0,
        fps=25.0,
        min_confidence=0.1,
    ).process(tracked, total_frames=40)

    assert all(result[frame][0].id == "track-1" for frame in range(21, 31))
    assert all(result[frame][0].detection_backed is False for frame in range(21, 31))
    assert all(result[frame][0].confidence >= 0.1 for frame in range(21, 31))
    assert result[31] == []


def test_privacy_safety_margin_expands_box_around_its_center():
    tracked = {0: [_box("track-1", (10, 20, 30, 60))]}

    result = TrackingPostProcessor(
        privacy_features_enabled=True,
        pre_detection_padding_sec=0.0,
        post_detection_padding_sec=0.0,
        box_safety_padding_pct=0.1,
    ).process(tracked, total_frames=1)

    assert result[0][0].bbox_xyxy == (9, 18, 31, 62)
    assert tracked[0][0].bbox_xyxy == (10, 20, 30, 60)


def test_privacy_padding_uses_maximum_observed_envelope_without_antishrink():
    tracked = {
        0: [_box("track-1", (10, 10, 110, 110))],
        1: [_box("track-1", (30, 40, 90, 80))],
    }

    result = TrackingPostProcessor(
        privacy_features_enabled=True,
        resist_box_shrinking=False,
        pre_detection_padding_sec=0.0,
        post_detection_padding_sec=0.5,
        box_safety_padding_pct=0.0,
        fps=2.0,
    ).process(tracked, total_frames=3)

    assert result[1][0].bbox_xyxy == (30, 40, 90, 80)
    assert result[2][0].bbox_xyxy == (10, 10, 110, 110)
