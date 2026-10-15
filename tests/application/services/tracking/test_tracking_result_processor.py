"""Unit tests for TrackingResultProcessor Layer C write parity."""

from __future__ import annotations

from unittest.mock import MagicMock

from app.application.services.tracking.result_processor import TrackingResultProcessor
from app.domain import ProcessingSettings, VideoDataLayer


class TestTrackingResultProcessor:
    def test_overwrite_layer_c_writes_tracking_output_to_layer_c(self):
        repo = MagicMock()
        session = MagicMock()
        session.state.settings = ProcessingSettings(min_tracker_confidence=0.5)
        session.state.metadata.frame_count = 3
        session.data.has_frame_for_layer_at_frame_index.return_value = False
        repo.get_session_by_id.return_value = session
        processor = TrackingResultProcessor(repo)
        s_id = MagicMock()
        tracked_box = MagicMock()
        tracked_box.confidence = 0.8
        tracked_box.clone.return_value = MagicMock()
        tracked_data = {1: [tracked_box], 2: []}

        processor.overwrite_layer_c(s_id, tracked_data)

        session.data.overwrite_layer_with_dict_of_boxes.assert_called_once_with(VideoDataLayer.C, tracked_data)
        session.data.replace_machine_boxes_for_frames.assert_called_once()
        layer, data, frame_count, filter_fn = (
            session.data.replace_machine_boxes_for_frames.call_args.args
        )
        assert layer == VideoDataLayer.D
        assert data == tracked_data
        assert frame_count == 3
        assert filter_fn(tracked_box) is True

    def test_refreshes_initialized_layer_d_frames(self):
        repo = MagicMock()
        session = MagicMock()
        session.state.settings = ProcessingSettings(min_tracker_confidence=0.5)
        session.state.metadata.frame_count = 2
        repo.get_session_by_id.return_value = session
        processor = TrackingResultProcessor(repo)

        processor.overwrite_layer_c(MagicMock(), {1: [MagicMock(confidence=0.9)]})

        session.data.replace_machine_boxes_for_frames.assert_called_once()
