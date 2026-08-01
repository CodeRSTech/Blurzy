"""Unit tests for DetectionBatchProcessor batch semantics."""

from __future__ import annotations

from unittest.mock import MagicMock

from app.application.services.detection.batch_processor import DetectionBatchProcessor

from app.domain import VideoDataLayer, DetectionResult, ProcessingSettings


def _make_session(*, has_existing_boxes: bool = False, settings: ProcessingSettings | None = None):
    session = MagicMock()
    session.state.session_settings = settings or ProcessingSettings(
        detection_model_name="YOLOv8n",
        min_detection_confidence=0.5,
        chosen_labels=["person"],
    )
    session.data.has_boxes_for_layer_at_frame_index.return_value = has_existing_boxes
    return session


class TestDetectionBatchProcessor:
    def test_skips_existing_layer_a_frame_data(self):
        repo = MagicMock()
        session = _make_session(has_existing_boxes=True)
        repo.get_session_by_id.return_value = session
        processor = DetectionBatchProcessor(repo)

        report = processor.process_batch(
            MagicMock(),
            {12: [DetectionResult(item_id="1", label="person", bbox_xyxy=(1, 2, 3, 4), confidence=0.9)]},
        )

        session.data.add_boxes_to_layer_at_frame_index.assert_not_called()
        assert report.total_frames == 1
        assert report.skipped_existing_frames == 1
        assert report.written_frames == 0
        assert report.written_boxes == 0

    def test_maps_filters_and_writes_expected_outputs(self):
        repo = MagicMock()
        session = _make_session()
        repo.get_session_by_id.return_value = session
        processor = DetectionBatchProcessor(repo)

        report = processor.process_batch(
            MagicMock(),
            {
                5: [
                    DetectionResult(item_id="1", label="person", bbox_xyxy=(1, 2, 30, 40), confidence=0.9),
                    DetectionResult(item_id="2", label="cat", bbox_xyxy=(5, 6, 35, 45), confidence=0.2),
                ]
            },
        )

        session.data.add_boxes_to_layer_at_frame_index.assert_called_once()
        layer, frame_index, filtered_boxes = session.data.add_boxes_to_layer_at_frame_index.call_args.args
        assert layer == VideoDataLayer.A
        assert frame_index == 5
        assert len(filtered_boxes) == 1
        assert filtered_boxes[0].id == "1"
        assert filtered_boxes[0].label == "person"
        assert filtered_boxes[0].is_detection == True
        assert report.written_frames == 1
        assert report.written_boxes == 1

    def test_returns_expected_report_counts(self):
        repo = MagicMock()
        session = _make_session()
        session.data.has_boxes_for_layer_at_frame_index.side_effect = [False, True, False]
        repo.get_session_by_id.return_value = session
        processor = DetectionBatchProcessor(repo)

        report = processor.process_batch(
            MagicMock(),
            {
                1: [DetectionResult(item_id="1", label="person", bbox_xyxy=(1, 1, 2, 2), confidence=0.9)],
                2: [DetectionResult(item_id="2", label="person", bbox_xyxy=(2, 2, 3, 3), confidence=0.9)],
                3: [DetectionResult(item_id="3", label="person", bbox_xyxy=(3, 3, 4, 4), confidence=0.9)],
            },
        )

        assert report.total_frames == 3
        assert report.skipped_existing_frames == 1
        assert report.written_frames == 2
        assert report.written_boxes == 2
