from __future__ import annotations

from unittest.mock import MagicMock

import numpy as np

from app.domain.detection import BoxSource
from app.domain.export import ProcessingSettings
from app.domain.views import BBoxViewModel
from app.infrastructure.tracking import track_worker as track_worker_module
from app.infrastructure.tracking.track_worker import TrackingWorker


def test_worker_runs_bounded_post_processing_before_exposing_results():
    state = MagicMock()
    state.metadata.frame_count = 4
    state.settings = ProcessingSettings()
    source = {
        0: [
            BBoxViewModel(
                id="d-1",
                source=BoxSource.DETECTION,
                label="person",
                bbox_xyxy=(0, 0, 10, 10),
                color_hex="#ffffff",
                confidence=0.9,
                key="d-1",
            )
        ],
        3: [
            BBoxViewModel(
                id="d-1",
                source=BoxSource.DETECTION,
                label="person",
                bbox_xyxy=(3, 0, 13, 10),
                color_hex="#ffffff",
                confidence=0.9,
                key="d-1",
            )
        ],
    }
    worker = TrackingWorker("dummy", source, state)
    errors: list[str] = []
    worker.error_occurred.connect(errors.append)

    worker.run()

    tracked = worker.get_tracked_data()
    assert errors == []
    assert worker.is_complete()
    assert tracked[1][0].id == "d-1"
    assert tracked[2][0].id == "d-1"


def test_worker_opens_and_closes_dedicated_reader_for_existing_video(monkeypatch):
    frame = np.zeros((16, 16, 3), dtype=np.uint8)
    reader_state: dict[str, object] = {}
    strategy_state: dict[str, object] = {}

    class FakeReader:
        frame_count = 1

        def __init__(self, path: str) -> None:
            reader_state["path"] = path

        @staticmethod
        def read_next_frame():
            return 0, frame

        @staticmethod
        def close():
            reader_state["closed"] = True

    class CaptureStrategy:
        uses_appearance = True

        def update_frame(self, frame_idx, frame_boxes, *, frame=None, embeddings=None):
            strategy_state["frame"] = frame
            strategy_state["embeddings"] = embeddings
            return frame_boxes

    monkeypatch.setattr(track_worker_module.os.path, "isfile", lambda path: True)
    monkeypatch.setattr(track_worker_module, "VideoReader", FakeReader)
    monkeypatch.setattr(track_worker_module, "_STRATEGY_MAP", {"capture": CaptureStrategy})
    state = MagicMock()
    state.s_id.path = "video.mp4"
    state.metadata.frame_count = 1
    state.settings = ProcessingSettings(reid_embedding_dim=128)

    worker = TrackingWorker(
        "capture",
        {
            0: [
                BBoxViewModel(
                    id="d-1",
                    source=BoxSource.DETECTION,
                    label="person",
                    bbox_xyxy=(0, 0, 10, 10),
                    color_hex="#ffffff",
                    confidence=0.9,
                    key="d-1",
                )
            ]
        },
        state,
    )
    errors: list[str] = []
    worker.error_occurred.connect(errors.append)
    worker.run()

    assert errors == []
    assert reader_state == {"path": "video.mp4", "closed": True}
    assert strategy_state["frame"] is frame
    assert strategy_state["embeddings"][0].shape == (128,)
    assert worker.is_complete()


def test_worker_uses_frame_less_fallback_for_missing_synthetic_path(monkeypatch):
    monkeypatch.setattr(track_worker_module.os.path, "isfile", lambda path: False)

    def unexpected_reader(path: str):
        raise AssertionError(f"reader must not open for missing path {path!r}")

    monkeypatch.setattr(track_worker_module, "VideoReader", unexpected_reader)
    state = MagicMock()
    state.s_id.path = "test.mp4"
    state.metadata.frame_count = 1
    state.settings = ProcessingSettings()

    worker = TrackingWorker("dummy", {0: []}, state)
    errors: list[str] = []
    worker.error_occurred.connect(errors.append)
    worker.run()

    assert errors == []
    assert worker.is_complete()
