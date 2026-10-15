"""Unit tests for DetectionExecutionService current-frame behaviour."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

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
        session.data.has_frame_for_layer_at_frame_index.return_value = False
        repo.get_session_by_id.return_value = session
        engine_manager = MagicMock()
        service = DetectionExecutionService(repo, engine_manager)

        service.execute_for_current_frame(MagicMock())

        engine_manager.create_or_update.assert_not_called()
        session.data.add_boxes_to_layer_at_frame_index.assert_called_once()
        session.data.replace_machine_boxes_at_frame_index.assert_called_once()
        layer, frame_index, selected_boxes = session.data.add_boxes_to_layer_at_frame_index.call_args.args
        assert layer == VideoDataLayer.A
        assert frame_index == 7
        assert len(selected_boxes) == 1
        assert selected_boxes[0].label == "person"
        layer, frame_index, filtered_boxes = (
            session.data.replace_machine_boxes_at_frame_index.call_args.args
        )
        assert layer == VideoDataLayer.B
        assert frame_index == 7
        assert len(filtered_boxes) == 1
        assert filtered_boxes[0].label == "person"
        assert filtered_boxes[0] is selected_boxes[0]

    @pytest.mark.parametrize(
        ("labels", "expected_labels"),
        [
            (None, ["person", "cat", "dog"]),
            (["person"], ["person"]),
            ([], ["person", "cat", "dog", "car"]),
            (["bird"], []),
        ],
    )
    def test_label_selection_filters_layer_a_and_b(self, labels, expected_labels):
        """Verify historical label selection before storage in both layers."""
        engine = MagicMock()
        engine.detect.return_value = [
            DetectionResult(item_id=label, label=label, bbox_xyxy=(1, 2, 30, 40), confidence=0.9)
            for label in ("person", "cat", "dog", "car")
        ] + [
            DetectionResult(item_id="low", label="person", bbox_xyxy=(1, 2, 30, 40), confidence=0.2)
        ]
        session = _make_session(detection_engine=engine)
        session.state.settings = ProcessingSettings(
            detection_model_name="YOLOv8n", min_detection_confidence=0.5
        )
        if labels is not None:
            session.state.settings.chosen_labels = labels
        repo = MagicMock()
        repo.get_session_by_id.return_value = session
        service = DetectionExecutionService(repo, MagicMock())

        service.execute_for_current_frame(MagicMock())

        layer_a, frame_a, selected_boxes = (
            session.data.add_boxes_to_layer_at_frame_index.call_args.args
        )
        layer_b, frame_b, editable_boxes = (
            session.data.replace_machine_boxes_at_frame_index.call_args.args
        )
        assert (layer_a, frame_a) == (VideoDataLayer.A, 7)
        assert (layer_b, frame_b) == (VideoDataLayer.B, 7)
        assert [box.label for box in selected_boxes] == expected_labels
        assert [box.label for box in editable_boxes] == expected_labels
