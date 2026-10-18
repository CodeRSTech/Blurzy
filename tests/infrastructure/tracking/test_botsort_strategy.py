"""Isolated synthetic tests for the standalone BoT-SORT strategy."""

from __future__ import annotations

import numpy as np
import pytest

from app.domain.detection import BoxSource
from app.domain.views import BBoxViewModel
from app.infrastructure.tracking.botsort_strategy import BotSortStrategy


def _box(x=0, y=0, *, confidence=0.9, label="person", width=20, height=40):
    return BBoxViewModel(
        id="detection",
        source=BoxSource.DETECTION,
        label=label,
        bbox_xyxy=(x, y, x + width, y + height),
        color_hex="#ffffff",
        confidence=confidence,
    )


def _feature(distance=0.0):
    similarity = 1 - distance
    return np.asarray([similarity, np.sqrt(1 - similarity**2)])


def _observed(output):
    return [box for box in output if box.detection_backed]


def test_high_association_uses_global_assignment_and_standard_output():
    strategy = BotSortStrategy()
    first = strategy.update_frame(0, [_box(0), _box(100)])
    second = strategy.update_frame(1, [_box(102), _box(2)])

    assert strategy.uses_appearance is True
    assert [box.id for box in first] == ["track-1", "track-2"]
    assert [box.id for box in second] == ["track-1", "track-2"]
    assert second[0].bbox_xyxy[0] < 5
    assert second[1].bbox_xyxy[0] > 95
    assert all(box.source == BoxSource.TRACKING_BOTSORT for box in second)
    assert all(box.detection_backed and box.time_since_update == 0 for box in second)
    assert second[0].key == "track:1"
    assert second[0].color_hex == first[0].color_hex


def test_minimum_fusion_prefers_appearance_over_nearest_iou():
    strategy = BotSortStrategy(min_iou=0.05)
    a, b = np.eye(2)
    strategy.update_frame(0, [_box(0), _box(30)], embeddings=[a, b])
    # Both detections overlap both predictions, but appearance reverses the
    # nearest-IoU assignment. Crowded observations must not change either EMA.
    output = strategy.update_frame(1, [_box(13, confidence=0.8), _box(17, confidence=0.9)], embeddings=[b, a])

    assert [box.confidence for box in output] == [0.9, 0.8]
    np.testing.assert_array_equal(strategy._tracks[0].appearance, a)
    np.testing.assert_array_equal(strategy._tracks[1].appearance, b)


def test_reid_recovers_nonoverlapping_detection_after_occlusion():
    strategy = BotSortStrategy()
    strategy.update_frame(0, [_box()], embeddings=[_feature()])
    strategy.update_frame(1, [])
    output = strategy.update_frame(2, [_box(150, 50)], embeddings=[_feature(0.2)])

    assert len(output) == 1
    assert output[0].id == "track-1"
    assert output[0].bbox_xyxy == (150, 50, 170, 90)
    assert output[0].detection_backed
    assert output[0].time_since_update == 0


@pytest.mark.parametrize(("distance", "expected"), [(0.25, "track-1"), (0.251, "track-2")])
def test_reid_cosine_threshold(distance, expected):
    strategy = BotSortStrategy()
    strategy.update_frame(0, [_box()], embeddings=[_feature()])
    output = strategy.update_frame(1, [_box(100)], embeddings=[_feature(distance)])
    assert _observed(output)[0].id == expected


@pytest.mark.parametrize(("margin", "recovers"), [(0.079, False), (0.08, True), (0.081, True)])
def test_reid_requires_clear_detection_margin(margin, recovers):
    strategy = BotSortStrategy()
    strategy.update_frame(0, [_box()], embeddings=[_feature()])
    output = strategy.update_frame(
        1,
        [_box(100), _box(200)],
        embeddings=[_feature(0.1), _feature(0.1 + margin)],
    )
    observed = _observed(output)
    assert ("track-1" in {box.id for box in observed}) is recovers
    if recovers:
        assert next(box for box in observed if box.id == "track-1").bbox_xyxy[0] == 100


def test_reid_rejects_ambiguous_competing_tracks():
    strategy = BotSortStrategy()
    strategy.update_frame(0, [_box(0), _box(100)], embeddings=[_feature(), _feature()])
    output = strategy.update_frame(1, [_box(200)], embeddings=[_feature()])
    assert [box.id for box in _observed(output)] == ["track-3"]


def test_reid_is_wide_radius_not_unbounded():
    strategy = BotSortStrategy()
    strategy.update_frame(0, [_box()], embeddings=[_feature()])
    output = strategy.update_frame(1, [_box(1000)], embeddings=[_feature()])
    assert [box.id for box in _observed(output)] == ["track-2"]


def test_low_confidence_recovery_never_contaminates_appearance():
    strategy = BotSortStrategy()
    original = _feature()
    strategy.update_frame(0, [_box()], embeddings=[original])
    low = strategy.update_frame(1, [_box(2, confidence=0.18)], embeddings=[np.asarray([0.0, 1.0])])
    assert len(low) == 1
    assert low[0].id == "track-1"
    assert low[0].detection_backed
    assert low[0].confidence == 0.18
    np.testing.assert_array_equal(strategy._tracks[0].appearance, original)

    output = strategy.update_frame(2, [_box(120)], embeddings=[original])
    assert [box.id for box in _observed(output)] == ["track-1"]


def test_low_confidence_never_starts_track_or_uses_reid():
    strategy = BotSortStrategy()
    assert strategy.update_frame(0, [_box(confidence=0.3)], embeddings=[_feature()]) == []
    strategy.update_frame(1, [_box()], embeddings=[_feature()])
    output = strategy.update_frame(2, [_box(100, confidence=0.3)], embeddings=[_feature()])
    assert len(output) == 1
    assert not output[0].detection_backed


def test_high_threshold_respects_min_confidence_and_zero_is_not_missing():
    strategy = BotSortStrategy(min_confidence=0.7, confidence_decay=0)
    assert strategy.update_frame(0, [_box(confidence=0.69)]) == []
    output = strategy.update_frame(1, [_box(confidence=0.7)])
    assert output[0].id == "track-1"
    assert strategy.update_frame(2, [_box(confidence=0.0)])[0].detection_backed is False


def test_low_detections_do_not_steal_high_detection_matches():
    strategy = BotSortStrategy()
    strategy.update_frame(0, [_box()])
    output = strategy.update_frame(1, [_box(confidence=0.2), _box(2, confidence=0.8)])
    assert len(output) == 1
    assert output[0].confidence == 0.8
    assert output[0].detection_backed


def test_ema_updates_only_for_isolated_high_detections():
    strategy = BotSortStrategy()
    initial = _feature()
    changed = _feature(0.2)
    strategy.update_frame(0, [_box()], embeddings=[initial])
    strategy.update_frame(1, [_box(1)], embeddings=[changed])
    expected = 0.9 * initial + 0.1 * changed
    expected /= np.linalg.norm(expected)
    np.testing.assert_allclose(strategy._tracks[0].appearance, expected)

    strategy.update_frame(
        2,
        [_box(2), _box(3, confidence=0.05)],
        embeddings=[np.asarray([0.0, 1.0]), changed],
    )
    np.testing.assert_allclose(strategy._tracks[0].appearance, expected)


def test_crowded_birth_does_not_initialize_appearance():
    strategy = BotSortStrategy()
    strategy.update_frame(0, [_box(), _box(1)], embeddings=list(np.eye(2)))
    assert all(track.appearance is None for track in strategy._tracks)


@pytest.mark.parametrize(("offset", "updates"), [(11, False), (12, False), (13, True)])
def test_isolation_iou_threshold_is_strict(offset, updates):
    strategy = BotSortStrategy()
    initial = _feature()
    strategy.update_frame(0, [_box()], embeddings=[initial])
    strategy.update_frame(
        1,
        [_box(), _box(offset, confidence=0.05)],
        embeddings=[_feature(0.2), None],
    )
    assert (not np.array_equal(strategy._tracks[0].appearance, initial)) is updates


def test_class_labels_gate_motion_and_reid():
    strategy = BotSortStrategy()
    strategy.update_frame(0, [_box()], embeddings=[_feature()])
    output = strategy.update_frame(1, [_box(label="car")], embeddings=[_feature()])
    assert [(box.id, box.label) for box in _observed(output)] == [("track-2", "car")]


def test_coasting_confidence_age_motion_and_expiry():
    strategy = BotSortStrategy(confidence_decay=0.1, min_confidence=0.2, max_age=2)
    strategy.update_frame(0, [_box()])
    observed = strategy.update_frame(1, [_box(5)])[0]
    coast = strategy.update_frame(2, [])[0]
    assert not coast.detection_backed
    assert coast.time_since_update == 1
    assert coast.confidence == 0.8
    assert coast.source == BoxSource.TRACKING_BOTSORT
    assert coast.bbox_xyxy[0] > observed.bbox_xyxy[0]
    assert strategy.update_frame(3, [])[0].time_since_update == 2
    assert strategy.update_frame(4, []) == []
    assert strategy._tracks == []


def test_confidence_floor_and_skipped_frames_expire_tracks():
    strategy = BotSortStrategy(confidence_decay=0.2, min_confidence=0.3)
    strategy.update_frame(0, [_box(confidence=0.8)])
    coast = strategy.update_frame(2, [])[0]
    assert coast.time_since_update == 2
    assert coast.confidence == 0.4
    assert strategy.update_frame(3, []) == []
    assert strategy.update_frame(4, [_box()])[0].id == "track-2"


def test_zero_decay_still_has_bounded_coasting_and_no_expired_reid():
    strategy = BotSortStrategy(confidence_decay=0, max_age=2)
    strategy.update_frame(0, [_box()], embeddings=[_feature()])
    assert strategy.update_frame(2, [])[0].confidence == 0.9
    assert strategy.update_frame(3, []) == []
    assert strategy.update_frame(4, [_box(100)], embeddings=[_feature()])[0].id == "track-2"


def test_direct_xywh_kalman_state_tracks_independent_width_and_height():
    strategy = BotSortStrategy()
    for index in range(6):
        strategy.update_frame(index, [_box(index * 2, width=20 + index * 4, height=40 - index * 2)])
    state = strategy._tracks[0]
    assert state.mean.shape == (8,)
    assert state.covariance.shape == (8, 8)
    assert state.mean[6] > 0
    assert state.mean[7] < 0
    assert state.mean[2] == pytest.approx(40, abs=2)
    assert state.mean[3] == pytest.approx(30, abs=2)
    assert np.linalg.eigvalsh(state.covariance).min() >= -1e-10


def test_small_predicted_boxes_do_not_collapse_during_integer_rounding():
    strategy = BotSortStrategy()
    strategy.update_frame(0, [_box(width=1, height=1)])
    # A subpixel Kalman prediction can place both edges on rounding ties.
    strategy._tracks[0].mean[:4] = [2, 2, 1, 1]
    output = strategy.update_frame(1, [])[0]
    left, top, right, bottom = output.bbox_xyxy
    assert right > left
    assert bottom > top


def test_synthetic_zigzag_and_occlusion_preserve_identity():
    strategy = BotSortStrategy(confidence_decay=0.02)
    positions = [(0, 0), (15, 5), (35, 15), None, None, (90, -10), (65, 20), (110, 0)]
    for index, position in enumerate(positions):
        boxes = [] if position is None else [_box(*position)]
        embeddings = [] if position is None else [_feature()]
        output = strategy.update_frame(index, boxes, embeddings=embeddings)
        assert len(output) == 1
        assert output[0].id == "track-1"
        assert output[0].detection_backed is (position is not None)


def test_batch_matches_incremental_and_resets_ids():
    data = {0: [_box()], 2: [_box(100)]}
    vectors = {0: [_feature()], 2: [_feature()]}
    batch = BotSortStrategy()
    incremental = BotSortStrategy()
    result = batch.track(data, total_frames=5, embeddings_by_frame=vectors)
    expected = {
        index: incremental.update_frame(index, data.get(index, []), embeddings=vectors.get(index)) for index in range(5)
    }
    assert result == expected
    assert batch.track(data, embeddings_by_frame=vectors) == {index: result[index] for index in range(3)}
    assert batch.track({}) == {}
    assert batch.track({}, total_frames=2) == {0: [], 1: []}


@pytest.mark.parametrize("dense", [False, True])
def test_frame_extraction_and_explicit_embeddings_precedence(dense):
    class Extractor:
        def __init__(self):
            self.calls = []

        def extract_for_boxes(self, frame, boxes):
            self.calls.append((frame, boxes))
            return [_feature() for _ in boxes]

    extractor = Extractor()
    strategy = BotSortStrategy(appearance_extractor=extractor)
    frames = [np.zeros((60, 200, 3), dtype=np.uint8) for _ in range(2)]
    result = strategy.track(
        {0: [_box()], 1: [_box(100)]},
        frames=frames if dense else dict(enumerate(frames)),
        embeddings_by_frame={1: [_feature()]},
    )
    assert [box.id for box in result[1]] == ["track-1"]
    assert len(extractor.calls) == 1
    assert extractor.calls[0][0] is frames[0]


def test_default_rgb_extractor_recovers_relocated_object():
    strategy = BotSortStrategy()
    frame = np.zeros((60, 200, 3), dtype=np.uint8)
    frame[:40, :20] = (200, 60, 30)
    frame[:40, 100:120] = (200, 60, 30)
    strategy.update_frame(0, [_box()], frame=frame)
    output = strategy.update_frame(1, [_box(100)], frame=frame)
    assert [box.id for box in output] == ["track-1"]
    assert output[0].detection_backed


def test_skipped_predictions_equal_processing_empty_frames():
    sparse, dense = BotSortStrategy(), BotSortStrategy()
    for strategy in (sparse, dense):
        strategy.update_frame(0, [_box()])
        strategy.update_frame(1, [_box(4)])
    for index in range(2, 5):
        dense_output = dense.update_frame(index, [])
    assert sparse.update_frame(4, []) == dense_output
    np.testing.assert_allclose(sparse._tracks[0].covariance, dense._tracks[0].covariance)


@pytest.mark.parametrize("embeddings", [[_feature(), _feature()], [np.asarray([np.nan, 0])], [np.zeros((2, 2))]])
def test_invalid_embeddings_do_not_advance_state(embeddings):
    strategy = BotSortStrategy()
    with pytest.raises(ValueError):
        strategy.update_frame(0, [_box()], embeddings=embeddings)
    assert strategy.update_frame(0, [_box()])[0].id == "track-1"


def test_missing_and_zero_embeddings_fall_back_to_motion_without_fake_reid():
    strategy = BotSortStrategy()
    strategy.update_frame(0, [_box()], embeddings=[np.zeros(2)])
    assert strategy.update_frame(1, [_box(1)], embeddings=[None])[0].id == "track-1"
    output = strategy.update_frame(2, [_box(100)])
    assert [box.id for box in _observed(output)] == ["track-2"]


def test_indices_embedding_dimensions_and_input_boxes_are_validated():
    strategy = BotSortStrategy()
    strategy.update_frame(0, [_box()], embeddings=[_feature()])
    with pytest.raises(ValueError, match="strictly increasing"):
        strategy.update_frame(0, [])
    with pytest.raises(ValueError, match="dimensions"):
        strategy.update_frame(1, [_box()], embeddings=[np.ones(3)])
    with pytest.raises(ValueError, match="positive dimensions"):
        strategy.update_frame(1, [_box(width=0)])
    assert strategy.update_frame(1, [_box()])[0].id == "track-1"


@pytest.mark.parametrize(
    "kwargs",
    [
        {"min_iou": -0.1},
        {"min_confidence": 1.1},
        {"confidence_decay": -1},
        {"confidence_decay": float("nan")},
        {"max_age": -1},
        {"ema_alpha": 1},
    ],
)
def test_invalid_configuration_is_explicit(kwargs):
    with pytest.raises(ValueError):
        BotSortStrategy(**kwargs)
