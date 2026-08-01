"""Facade/delegation tests for DetectionService Phase 2 extraction."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.application.services.detection.batch_processor import DetectionBatchProcessReport
from app.application.services.detection.service import DetectionService
from app.shared.exceptions import NullModelNameException, WorkerAlreadyRunningException


class TestDetectionServiceFacade:
    @staticmethod
    def _app_with_session(session):
        app = MagicMock()
        app.sm = MagicMock()
        app.sm.get_session_by_id.return_value = session
        return app

    def test_detect_current_frame_delegates_to_execution_service(self):
        service = DetectionService(MagicMock())
        service._execution_service = MagicMock()
        s_id = MagicMock()

        service.detect_current_frame_and_populate_layer_b_at_current_index(s_id)

        service._execution_service.execute_for_current_frame.assert_called_once_with(s_id)

    def test_on_detection_batch_ready_delegates_to_batch_processor(self):
        service = DetectionService(MagicMock())
        service._batch_processor = MagicMock()
        service._batch_processor.process_batch.return_value = DetectionBatchProcessReport(
            total_frames=2,
            skipped_existing_frames=1,
            written_frames=1,
            written_boxes=3,
        )
        s_id = MagicMock()
        batch = {1: [], 2: []}

        service.on_detection_batch_ready(s_id, batch, 12.5)

        service._batch_processor.process_batch.assert_called_once_with(s_id, batch)

    def test_on_detection_batch_ready_swallows_missing_session(self):
        service = DetectionService(MagicMock())
        service._batch_processor = MagicMock()
        service._batch_processor.process_batch.side_effect = KeyError("closed")

        service.on_detection_batch_ready(MagicMock(), {1: []}, 12.5)

    def test_set_detection_model_none_string_stops_worker_resets_model_and_removes_engine(self):
        session = MagicMock()
        detection_worker = MagicMock()
        session.detection_worker = detection_worker
        app = self._app_with_session(session)
        service = DetectionService(app)
        service._engine_manager = MagicMock()

        service.set_detection_model_for_session_id(MagicMock(), "None", keep_manual=True)

        detection_worker.stop.assert_called_once_with()
        assert session.detection_worker is None
        session.reset_model.assert_called_once_with("None", True)
        service._engine_manager.remove.assert_called_once()

    # def test_start_detection_worker_preserves_worker_setup(self):
    #     app = MagicMock()
    #     session = MagicMock()
    #     session.has_running_detection_worker = False
    #     session.state.settings = MagicMock(model_name_is_null=False, detection_model_name="yolov8n")
    #     session.detection_engine = MagicMock()
    #     app.get_session_by_id.return_value = session
    #     service = DetectionService(app)
    #     service._create_or_update_detection_engine_from_model_name_for_session_id = MagicMock()
    #
    #     detection_worker = MagicMock()
    #     with patch("app.application.services.detection.detection_service.DetectionWorker", return_value=detection_worker) as worker_cls:
    #         s_id = MagicMock()
    #         service.start_detection_worker_for_session_id(s_id)
    #
    #     session.data.clear_all_layers.assert_called_once_with()
    #     service._create_or_update_detection_engine_from_model_name_for_session_id.assert_called_once_with(
    #         model_name="YOLOv8n", s_id=s_id
    #     )
    #     worker_cls.assert_called_once_with(s_id=s_id, detection_engine=session.detection_engine)
    #     detection_worker.batch_ready.connect.assert_called_once_with(service.on_detection_batch_ready)
    #     detection_worker.progress_updated.connect.assert_called_once_with(service.on_detection_progress_updated)
    #     detection_worker.start.assert_called_once_with()
    #     assert session.detection_worker is detection_worker

    def test_start_detection_worker_raises_when_worker_is_already_running(self):
        session = MagicMock()
        session.has_running_detection_worker = True
        session.state.settings = MagicMock(model_name_is_null=False, detection_model_name="YOLOv8n")
        app = self._app_with_session(session)
        service = DetectionService(app)

        with pytest.raises(WorkerAlreadyRunningException):
            service.start_detection_worker_for_session_id(MagicMock())

        session.data.clear_all_layers.assert_not_called()

    def test_start_detection_worker_raises_when_model_is_not_configured(self):
        session = MagicMock()
        session.has_running_detection_worker = False
        session.state.settings = MagicMock(model_name_is_null=True, detection_model_name="None")
        app = self._app_with_session(session)
        service = DetectionService(app)

        with pytest.raises(NullModelNameException):
            service.start_detection_worker_for_session_id(MagicMock())

        session.data.clear_all_layers.assert_not_called()
