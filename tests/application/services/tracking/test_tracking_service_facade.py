"""Facade/delegation tests for TrackingService Phase 4 extraction."""

from __future__ import annotations

from unittest.mock import MagicMock
from types import SimpleNamespace
from threading import RLock

import pytest

from app.application.services.tracking.service import TrackingService
from app.domain import VideoDataLayer
from app.shared.exceptions import InvalidSessionIdException


class TestTrackingServiceFacade:
    def test_detection_coverage_counts_empty_results_but_not_absent_or_out_of_range_frames(self):
        service = TrackingService(MagicMock())
        data = MagicMock()
        data.data_lock = RLock()
        data.get_all_boxes_for_layer_as_dict_of_lists.return_value = {0: [], 2: [object()], -1: [], 4: []}
        service._app_adapter = MagicMock()
        service._app_adapter.get_session_by_id.return_value = SimpleNamespace(
            data=data, state=SimpleNamespace(metadata=SimpleNamespace(frame_count=4))
        )

        assert service.get_detection_frame_coverage("video") == (2, 4)
        data.get_all_boxes_for_layer_as_dict_of_lists.assert_called_once_with(VideoDataLayer.A)

    def test_start_background_tracking_delegates_to_manager(self):
        service = TrackingService(MagicMock())
        service._worker_manager = MagicMock()
        s_id = MagicMock()

        service.start_background_tracking(s_id, "hungarian", "a")

        service._worker_manager.start.assert_called_once_with(s_id, "hungarian", "a")

    def test_start_background_tracking_rejects_invalid_session_id(self):
        service = TrackingService(MagicMock())
        service._worker_manager = MagicMock()

        with pytest.raises(InvalidSessionIdException):
            service.start_background_tracking("", "hungarian", "a")

        service._worker_manager.start.assert_not_called()

    def test_sync_tracking_cache_delegates_to_manager_and_processor(self):
        service = TrackingService(MagicMock())
        service._worker_manager = MagicMock()
        service._result_processor = MagicMock()
        s_id = MagicMock()
        tracked_data = {1: [MagicMock()]}
        service._worker_manager.get_tracked_data.return_value = tracked_data

        service.sync_tracking_cache(s_id)

        service._worker_manager.get_tracked_data.assert_called_once_with(s_id)
        service._result_processor.overwrite_layer_c.assert_called_once_with(s_id, tracked_data)

    def test_sync_tracking_cache_rejects_invalid_session_id(self):
        service = TrackingService(MagicMock())
        service._worker_manager = MagicMock()
        service._result_processor = MagicMock()

        with pytest.raises(InvalidSessionIdException):
            service.sync_tracking_cache("")

        service._worker_manager.get_tracked_data.assert_not_called()
        service._result_processor.overwrite_layer_c.assert_not_called()
