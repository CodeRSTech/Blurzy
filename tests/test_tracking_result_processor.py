"""Unit tests for TrackingResultProcessor Layer C write parity."""

from __future__ import annotations

from unittest.mock import MagicMock

from app.application.services.tracking.result_processor import TrackingResultProcessor
from app.domain import VideoDataLayer


class TestTrackingResultProcessor:
    def test_overwrite_layer_c_writes_tracking_output_to_layer_c(self):
        repo = MagicMock()
        session = MagicMock()
        repo.get_session_by_id.return_value = session
        processor = TrackingResultProcessor(repo)
        s_id = MagicMock()
        tracked_data = {1: [MagicMock()], 2: []}

        processor.overwrite_layer_c(s_id, tracked_data)

        session.data.overwrite_layer_with_dict_of_boxes.assert_called_once_with(VideoDataLayer.C, tracked_data)
