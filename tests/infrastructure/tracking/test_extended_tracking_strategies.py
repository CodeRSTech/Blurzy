from __future__ import annotations

import sys
import types

import numpy as np

from app.domain.detection import BoxSource
from app.domain.views.bounding_box_view_model import BBoxViewModel
from app.infrastructure.tracking.bytetrack_strategy import ByteTrackStrategy
from app.infrastructure.tracking.deepsort_strategy import DeepSortStrategy


def _mk_box(*, box_id: str, bbox: tuple[int, int, int, int], conf: float, label: str) -> BBoxViewModel:
    return BBoxViewModel(
        id=box_id,
        source=BoxSource.DETECTION,
        label=label,
        bbox_xyxy=bbox,
        color_hex="#ffffff",
        confidence=conf,
        key=box_id,
    )


def test_bytetrack_strategy_shapes_output_with_fake_backend(monkeypatch):
    fake_mod = types.ModuleType("ultralytics.trackers.byte_tracker")
    fake_results_mod = types.ModuleType("ultralytics.engine.results")

    class FakeBoxes:
        def __init__(self, data, shape):
            self.data = data
            self.orig_shape = shape

        @property
        def conf(self):
            return self.data[:, 4]

        @property
        def cls(self):
            return self.data[:, 5]

        @property
        def xywh(self):
            rows = []
            for row in self.data:
                x1, y1, x2, y2 = row[:4]
                rows.append([(x1 + x2) / 2.0, (y1 + y2) / 2.0, x2 - x1, y2 - y1])
            return np.asarray(rows, dtype=np.float32)

        def __getitem__(self, mask):
            return FakeBoxes(self.data[mask], self.orig_shape)

        def __len__(self):
            return int(self.data.shape[0])

    class FakeByteTracker:
        def __init__(self, *args):
            self.args = args

        def update(self, results):
            assert hasattr(results, "conf")
            return np.asarray([[10, 20, 30, 40, 7, 0.91, 0, 0]], dtype=np.float32)

    fake_mod.BYTETracker = FakeByteTracker
    fake_results_mod.Boxes = FakeBoxes
    monkeypatch.setitem(sys.modules, "ultralytics.trackers.byte_tracker", fake_mod)
    monkeypatch.setitem(sys.modules, "ultralytics.engine.results", fake_results_mod)

    strategy = ByteTrackStrategy(min_iou=0.3, min_confidence=0.2)
    result = strategy.track(
        source_data={0: [_mk_box(box_id="d-1", bbox=(10, 20, 30, 40), conf=0.8, label="person")]},
        total_frames=1,
    )

    assert 0 in result
    assert len(result[0]) == 1
    out = result[0][0]
    assert out.id == "track-7"
    assert out.source == BoxSource.TRACKING_BYTETRACK
    assert out.label == "person"


def test_deepsort_strategy_shapes_output_with_fake_backend(monkeypatch):
    fake_mod = types.ModuleType("deep_sort_realtime.deepsort_tracker")
    seen_init: dict[str, object] = {}
    seen_update: dict[str, object] = {}

    class FakeTrack:
        track_id = 3
        det_class = "car"
        det_conf = 0.87

        @staticmethod
        def is_confirmed():
            return True

        @staticmethod
        def to_ltrb():
            return 5, 6, 25, 26

    class FakeDeepSort:
        def __init__(self, max_age, n_init, max_iou_distance, embedder=None):
            self.max_age = max_age
            self.n_init = n_init
            self.max_iou_distance = max_iou_distance
            self.embedder = embedder
            seen_init["embedder"] = embedder

        def update_tracks(self, raw_detections, embeds=None, frame=None):
            seen_update["raw"] = raw_detections
            seen_update["embeds"] = embeds
            return [FakeTrack()]

    fake_mod.DeepSort = FakeDeepSort
    monkeypatch.setitem(sys.modules, "deep_sort_realtime.deepsort_tracker", fake_mod)

    strategy = DeepSortStrategy(min_iou=0.25, min_confidence=0.2, confidence_decay=0.05)
    result = strategy.track(
        source_data={0: [_mk_box(box_id="d-1", bbox=(5, 6, 25, 26), conf=0.9, label="car")]},
        total_frames=1,
    )

    assert 0 in result
    assert len(result[0]) == 1
    out = result[0][0]
    assert out.id == "track-3"
    assert out.source == BoxSource.TRACKING_DEEPSORT
    assert out.label == "car"
    assert seen_init["embedder"] is None
    assert isinstance(seen_update["embeds"], list)
    assert len(seen_update["embeds"]) == 1


def test_deepsort_strategy_emits_coasted_predictions(monkeypatch):
    fake_mod = types.ModuleType("deep_sort_realtime.deepsort_tracker")

    class FakeTrack:
        track_id = 3
        det_class = "person"
        det_conf = 0.8
        time_since_update = 1

        @staticmethod
        def is_confirmed():
            return True

        @staticmethod
        def to_ltrb():
            return 5, 6, 25, 26

    class FakeDeepSort:
        def __init__(self, **kwargs):
            pass

        @staticmethod
        def update_tracks(raw_detections, embeds=None, frame=None):
            return [FakeTrack()]

    fake_mod.DeepSort = FakeDeepSort
    monkeypatch.setitem(sys.modules, "deep_sort_realtime.deepsort_tracker", fake_mod)

    result = DeepSortStrategy().track(
        source_data={0: [_mk_box(box_id="d-1", bbox=(5, 6, 25, 26), conf=0.9, label="person")]},
        total_frames=1,
    )

    assert len(result[0]) == 1
    assert result[0][0].detection_backed is False
    assert result[0][0].time_since_update == 1
    assert result[0][0].confidence == 0.75


def test_bytetrack_strategy_handles_empty_frame(monkeypatch):
    fake_mod = types.ModuleType("ultralytics.trackers.byte_tracker")
    fake_results_mod = types.ModuleType("ultralytics.engine.results")

    class FakeBoxes:
        def __init__(self, data, shape):
            self.data = data
            self.orig_shape = shape

        @property
        def conf(self):
            return self.data[:, 4] if self.data.size else np.asarray([], dtype=np.float32)

        @property
        def cls(self):
            return self.data[:, 5] if self.data.size else np.asarray([], dtype=np.float32)

        @property
        def xywh(self):
            return np.empty((0, 4), dtype=np.float32)

        def __getitem__(self, mask):
            return FakeBoxes(self.data[mask], self.orig_shape)

        def __len__(self):
            return int(self.data.shape[0])

    class FakeByteTracker:
        def __init__(self, *args):
            self.args = args

        @staticmethod
        def update(results):
            return np.asarray([], dtype=np.float32)

    fake_mod.BYTETracker = FakeByteTracker
    fake_results_mod.Boxes = FakeBoxes
    monkeypatch.setitem(sys.modules, "ultralytics.trackers.byte_tracker", fake_mod)
    monkeypatch.setitem(sys.modules, "ultralytics.engine.results", fake_results_mod)

    strategy = ByteTrackStrategy()
    result = strategy.track(source_data={0: []}, total_frames=1)
    assert result == {0: []}


def test_bytetrack_strategy_emits_unmatched_detection_on_birth_frame(monkeypatch):
    fake_mod = types.ModuleType("ultralytics.trackers.byte_tracker")
    fake_results_mod = types.ModuleType("ultralytics.engine.results")

    class FakeBoxes:
        def __init__(self, data, shape):
            self.data = data
            self.orig_shape = shape

        @property
        def conf(self):
            return self.data[:, 4]

        @property
        def cls(self):
            return self.data[:, 5]

        @property
        def xywh(self):
            return np.asarray([[20, 30, 20, 20]], dtype=np.float32)

        def __len__(self):
            return int(self.data.shape[0])

    class FakeByteTracker:
        def __init__(self, *args):
            pass

        @staticmethod
        def update(results):
            return np.asarray([[10, 20, 30, 40, 7, 0.91, 0, -1]], dtype=np.float32)

    fake_mod.BYTETracker = FakeByteTracker
    fake_results_mod.Boxes = FakeBoxes
    monkeypatch.setitem(sys.modules, "ultralytics.trackers.byte_tracker", fake_mod)
    monkeypatch.setitem(sys.modules, "ultralytics.engine.results", fake_results_mod)

    strategy = ByteTrackStrategy()
    result = strategy.track(
        source_data={0: [_mk_box(box_id="d-1", bbox=(10, 20, 30, 40), conf=0.25, label="person")]},
        total_frames=1,
    )

    assert len(result[0]) == 1
    assert result[0][0].detection_backed is True
    assert result[0][0].time_since_update == 0
    assert result[0][0].confidence == 0.25


def test_bytetrack_adapts_thresholds_and_births_prefiltered_detections(monkeypatch):
    fake_mod = types.ModuleType("ultralytics.trackers.byte_tracker")
    fake_results_mod = types.ModuleType("ultralytics.engine.results")

    class FakeBoxes:
        def __init__(self, data, shape):
            self.data = data
            self.orig_shape = shape

        @property
        def conf(self):
            return self.data[:, 4]

        @property
        def cls(self):
            return self.data[:, 5]

        @property
        def xywh(self):
            return np.asarray(
                [
                    [(row[0] + row[2]) / 2, (row[1] + row[3]) / 2, row[2] - row[0], row[3] - row[1]]
                    for row in self.data
                ],
                dtype=np.float32,
            )

        def __len__(self):
            return int(self.data.shape[0])

    class FakeByteTracker:
        def __init__(self, args, *unused):
            self.args = args

        @staticmethod
        def update(results):
            return np.asarray([], dtype=np.float32)

    fake_mod.BYTETracker = FakeByteTracker
    fake_results_mod.Boxes = FakeBoxes
    monkeypatch.setitem(sys.modules, "ultralytics.trackers.byte_tracker", fake_mod)
    monkeypatch.setitem(sys.modules, "ultralytics.engine.results", fake_results_mod)

    strategy = ByteTrackStrategy(min_confidence=0.1, min_detection_confidence=0.25)
    result = strategy.track(
        source_data={
            0: [
                _mk_box(box_id="d-1", bbox=(10, 10, 30, 30), conf=0.25, label="person"),
                _mk_box(box_id="d-2", bbox=(50, 10, 70, 30), conf=0.45, label="person"),
            ]
        },
        total_frames=1,
    )

    assert strategy._tracker_args.track_low_thresh == 0.1
    assert strategy._tracker_args.track_high_thresh == 0.3
    assert len(result[0]) == 2
    assert all(box.detection_backed and box.time_since_update == 0 for box in result[0])


def test_bytetrack_routes_low_confidence_box_through_second_stage(monkeypatch):
    fake_mod = types.ModuleType("ultralytics.trackers.byte_tracker")
    fake_results_mod = types.ModuleType("ultralytics.engine.results")

    class FakeBoxes:
        def __init__(self, data, shape):
            self.data = data
            self.orig_shape = shape

        @property
        def conf(self):
            return self.data[:, 4]

        @property
        def cls(self):
            return self.data[:, 5]

        @property
        def xywh(self):
            return np.asarray(
                [
                    [(row[0] + row[2]) / 2, (row[1] + row[3]) / 2, row[2] - row[0], row[3] - row[1]]
                    for row in self.data
                ],
                dtype=np.float32,
            )

        def __len__(self):
            return int(self.data.shape[0])

    class FakeByteTracker:
        def __init__(self, args, *unused):
            self.args = args
            self.frame_idx = 0
            self.thresholds = []

        def update(self, results):
            self.thresholds.append(
                (self.args.track_low_thresh, self.args.track_high_thresh)
            )
            self.frame_idx += 1
            if self.frame_idx == 1:
                return np.asarray([[10, 10, 30, 30, 7, 0.4, 0, 0]], dtype=np.float32)
            return np.asarray([[11, 10, 31, 30, 7, 0.15, 0, 0]], dtype=np.float32)

    fake_mod.BYTETracker = FakeByteTracker
    fake_results_mod.Boxes = FakeBoxes
    monkeypatch.setitem(sys.modules, "ultralytics.trackers.byte_tracker", fake_mod)
    monkeypatch.setitem(sys.modules, "ultralytics.engine.results", fake_results_mod)

    strategy = ByteTrackStrategy(min_confidence=0.1, min_detection_confidence=0.25)
    result = strategy.track(
        source_data={
            0: [_mk_box(box_id="d-1", bbox=(10, 10, 30, 30), conf=0.4, label="person")],
            1: [
                _mk_box(box_id="d-2", bbox=(11, 10, 31, 30), conf=0.15, label="person"),
                _mk_box(box_id="d-3", bbox=(40, 10, 60, 30), conf=0.4, label="person"),
            ],
        },
        total_frames=2,
    )

    engine = strategy._engine
    assert engine.thresholds == [(0.1, 0.35), (0.1, 0.225)]
    assert result[1][0].id == "track-7"
    assert result[1][0].detection_backed is True
    assert result[1][0].time_since_update == 0


def test_bytetrack_uses_predicted_center_fallback_when_iou_drops(monkeypatch):
    fake_mod = types.ModuleType("ultralytics.trackers.byte_tracker")
    fake_results_mod = types.ModuleType("ultralytics.engine.results")

    class FakeBoxes:
        def __init__(self, data, shape):
            self.data = data
            self.orig_shape = shape

        @property
        def conf(self):
            return self.data[:, 4]

        @property
        def cls(self):
            return self.data[:, 5]

        @property
        def xywh(self):
            return np.asarray(
                [
                    [(row[0] + row[2]) / 2, (row[1] + row[3]) / 2, row[2] - row[0], row[3] - row[1]]
                    for row in self.data
                ],
                dtype=np.float32,
            )

        def __len__(self):
            return int(self.data.shape[0])

    class FakeByteTracker:
        def __init__(self, args, *unused):
            self.frame_idx = 0

        def update(self, results):
            self.frame_idx += 1
            if self.frame_idx == 1:
                return np.asarray([[0, 0, 20, 40, 7, 0.9, 0, 0]], dtype=np.float32)
            return np.asarray([[25, 0, 45, 40, 8, 0.9, 0, 0]], dtype=np.float32)

    fake_mod.BYTETracker = FakeByteTracker
    fake_results_mod.Boxes = FakeBoxes
    monkeypatch.setitem(sys.modules, "ultralytics.trackers.byte_tracker", fake_mod)
    monkeypatch.setitem(sys.modules, "ultralytics.engine.results", fake_results_mod)

    result = ByteTrackStrategy().track(
        source_data={
            0: [_mk_box(box_id="d-1", bbox=(0, 0, 20, 40), conf=0.9, label="person")],
            1: [_mk_box(box_id="d-2", bbox=(25, 0, 45, 40), conf=0.9, label="person")],
        },
        total_frames=2,
    )

    assert result[0][0].id == "track-7"
    assert result[1][0].id == "track-7"
    assert result[1][0].bbox_xyxy == (25, 0, 45, 40)


def test_deepsort_strategy_handles_empty_frame(monkeypatch):
    fake_mod = types.ModuleType("deep_sort_realtime.deepsort_tracker")

    class FakeDeepSort:
        def __init__(self, max_age, n_init, max_iou_distance, embedder=None):
            self.embedder = embedder

        @staticmethod
        def update_tracks(raw_detections, embeds=None, frame=None):
            assert raw_detections == []
            assert embeds == []
            return []

    fake_mod.DeepSort = FakeDeepSort
    monkeypatch.setitem(sys.modules, "deep_sort_realtime.deepsort_tracker", fake_mod)

    strategy = DeepSortStrategy()
    result = strategy.track(source_data={0: []}, total_frames=1)
    assert result == {0: []}
