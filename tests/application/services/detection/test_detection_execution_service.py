"""Unit tests for DetectionExecutionService current-frame behaviour."""

from __future__ import annotations

from unittest.mock import MagicMock

from app.application.services.detection.execution import DetectionExecutionService
from app.domain import VideoDataLayer, DetectionResult, ProcessingSettings


def _make_session(*, model_name: str = "YOLOv8n", frame=object(), detection_engine=None):
    session = MagicMock()
    session.state.settings = ProcessingSettings(
        detection_model_name=model_name,
        min_detection_confidence=0.5,
        chosen_labels=["person"],
    )
    session.state.playback.current_frame_index = 7
    session.get_current_frame.return_value = frame
    session.detection_engine = detection_engine
    return session


class TestDetectionExecutionService:
    def test_null_model_is_no_op(self):
        repo = MagicMock()
        session = _make_session(model_name="None")
        repo.get_session_by_id.return_value = session
        engine_manager = MagicMock()
        service = DetectionExecutionService(repo, engine_manager)

        service.execute_for_current_frame(MagicMock())

        engine_manager.create_or_update.assert_not_called()
        session.get_current_frame.assert_not_called()
        session.data.add_boxes_to_layer_at_frame_index.assert_not_called()

    def test_missing_frame_is_no_op(self):
        repo = MagicMock()
        session = _make_session(frame=None, detection_engine=None)
        repo.get_session_by_id.return_value = session
        engine_manager = MagicMock()
        service = DetectionExecutionService(repo, engine_manager)

        service.execute_for_current_frame(MagicMock())

        engine_manager.create_or_update.assert_called_once()
        session.data.add_boxes_to_layer_at_frame_index.assert_not_called()

    def test_valid_frame_writes_filtered_layer_data(self):
        repo = MagicMock()
        detection_engine = MagicMock()
        detection_engine.detect.return_value = [
            DetectionResult(item_id="1", label="person", bbox_xyxy=(1, 2, 10, 12), confidence=0.9),
            DetectionResult(item_id="2", label="cat", bbox_xyxy=(5, 6, 11, 13), confidence=0.2),
        ]
        session = _make_session(detection_engine=detection_engine)
        repo.get_session_by_id.return_value = session
        engine_manager = MagicMock()
        service = DetectionExecutionService(repo, engine_manager)

        service.execute_for_current_frame(MagicMock())

        engine_manager.create_or_update.assert_not_called()
        session.data.add_boxes_to_layer_at_frame_index.assert_called_once()
        layer, frame_index, filtered_boxes = session.data.add_boxes_to_layer_at_frame_index.call_args.args
        assert layer == VideoDataLayer.A
        assert frame_index == 7
        assert len(filtered_boxes) == 1
        assert filtered_boxes[0].label == "person"
