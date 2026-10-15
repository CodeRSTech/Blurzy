from __future__ import annotations

from unittest.mock import MagicMock

from app.domain.detection import BoxSource
from app.domain.export import ProcessingSettings
from app.domain.views import BBoxViewModel
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

    worker.run()

    tracked = worker.get_tracked_data()
    assert worker.is_complete()
    assert tracked[1][0].id == "d-1"
    assert tracked[2][0].id == "d-1"
