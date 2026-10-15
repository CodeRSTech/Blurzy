"""Unit tests for DetectionBatchProcessor batch semantics."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.application.services.detection.batch_processor import DetectionBatchProcessor
from app.application.services.detection.execution import DetectionExecutionService

from app.domain import VideoDataLayer, DetectionResult, ProcessingSettings, BoxSource
from app.infrastructure.session.session_data_store import SessionDataStore


def _make_session(*, has_existing_boxes: bool = False, settings: ProcessingSettings | None = None):
    session = MagicMock()
    session.state.settings = settings or ProcessingSettings(
        detection_model_name="YOLOv8n",
        min_detection_confidence=0.5,
        chosen_labels=["person"],
    )
    session.data.has_boxes_for_layer_at_frame_index.return_value = has_existing_boxes
    session.data.has_frame_for_layer_at_frame_index.return_value = False
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
        session.data.replace_machine_boxes_at_frame_index.assert_called_once()
        layer, frame_index, selected_boxes = session.data.add_boxes_to_layer_at_frame_index.call_args.args
        assert layer == VideoDataLayer.A
        assert frame_index == 5
        assert len(selected_boxes) == 1
        assert selected_boxes[0].id == "1"
        _, _, editable_boxes = session.data.replace_machine_boxes_at_frame_index.call_args.args
        assert len(editable_boxes) == 1
        assert editable_boxes[0].id == "1"
        assert editable_boxes[0].label == "person"
        assert editable_boxes[0].is_detection
        assert editable_boxes[0] is selected_boxes[0]
        assert report.written_frames == 1
        assert report.written_boxes == 1

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
        settings = ProcessingSettings(min_detection_confidence=0.5)
        if labels is not None:
            settings.chosen_labels = labels
        session = _make_session(settings=settings)
        repo = MagicMock()
        repo.get_session_by_id.return_value = session
        processor = DetectionBatchProcessor(repo)
        detections = [
            DetectionResult(item_id=label, label=label, bbox_xyxy=(1, 2, 30, 40), confidence=0.9)
            for label in ("person", "cat", "dog", "car")
        ]
        detections.append(
            DetectionResult(item_id="low", label="person", bbox_xyxy=(1, 2, 30, 40), confidence=0.2)
        )

        report = processor.process_batch(MagicMock(), {0: detections})

        layer_a, frame_a, selected_boxes = (
            session.data.add_boxes_to_layer_at_frame_index.call_args.args
        )
        layer_b, frame_b, editable_boxes = (
            session.data.replace_machine_boxes_at_frame_index.call_args.args
        )
        assert (layer_a, frame_a) == (VideoDataLayer.A, 0)
        assert (layer_b, frame_b) == (VideoDataLayer.B, 0)
        assert [box.label for box in selected_boxes] == expected_labels
        assert [box.label for box in editable_boxes] == expected_labels
        assert report.written_boxes == len(expected_labels)

    def test_refreshes_initialized_layer_b_machine_boxes(self):
        repo = MagicMock()
        session = _make_session()
        session.data.has_frame_for_layer_at_frame_index.return_value = True
        repo.get_session_by_id.return_value = session
        processor = DetectionBatchProcessor(repo)

        processor.process_batch(
            MagicMock(),
            {
                5: [
                    DetectionResult(
                        item_id="1", label="person", bbox_xyxy=(1, 2, 30, 40), confidence=0.9
                    )
                ]
            },
        )

        session.data.add_boxes_to_layer_at_frame_index.assert_called_once()
        session.data.replace_machine_boxes_at_frame_index.assert_called_once()
        assert session.data.add_boxes_to_layer_at_frame_index.call_args.args[0] == VideoDataLayer.A

    @pytest.mark.parametrize("mode", ["batch", "current"])
    @pytest.mark.parametrize("labels", [["person"], ["bird"]])
    def test_filtered_storage_preserves_manual_boxes_on_visited_frame_zero(self, mode, labels):
        """Verify selected storage and manual-safe refresh through the real store."""
        session = _make_session()
        session.state.settings.chosen_labels = labels
        session.state.playback.current_frame_index = 0
        session.data = SessionDataStore(s_id=MagicMock())
        manual = DetectionResult(
            item_id="manual", label="car", bbox_xyxy=(1, 2, 30, 40), confidence=0.9
        ).to_frame_box_view_model()
        manual.source = BoxSource.MANUAL
        stale = DetectionResult(
            item_id="stale", label="car", bbox_xyxy=(1, 2, 30, 40), confidence=0.9
        ).to_frame_box_view_model()
        session.data.add_boxes_to_layer_at_frame_index(VideoDataLayer.A, 0, [])
        session.data.add_boxes_to_layer_at_frame_index(VideoDataLayer.B, 0, [manual, stale])
        detections = [
            DetectionResult(item_id=label, label=label, bbox_xyxy=(1, 2, 30, 40), confidence=0.9)
            for label in ("person", "car")
        ]
        repo = MagicMock()
        repo.get_session_by_id.return_value = session

        if mode == "batch":
            DetectionBatchProcessor(repo).process_batch(MagicMock(), {0: detections})
        else:
            session.detection_engine.detect.return_value = detections
            DetectionExecutionService(repo, MagicMock()).execute_for_current_frame(MagicMock())

        stored = session.data.get_boxes_for_layer_at_frame_index_as_list(VideoDataLayer.A, 0)
        editable = session.data.get_boxes_for_layer_at_frame_index_as_list(VideoDataLayer.B, 0)
        expected = ["person"] if "person" in labels else []
        assert [box.label for box in stored] == expected
        assert [box.label for box in editable if not box.is_manual] == expected
        assert [box for box in editable if box.is_manual] == [manual]
        if stored:
            assert stored[0] is not next(box for box in editable if not box.is_manual)

    def test_marks_layer_b_frame_initialized_when_all_raw_detections_are_filtered(self):
        repo = MagicMock()
        session = _make_session()
        repo.get_session_by_id.return_value = session
        processor = DetectionBatchProcessor(repo)

        processor.process_batch(
            MagicMock(),
            {
                5: [
                    DetectionResult(
                        item_id="1", label="person", bbox_xyxy=(1, 2, 30, 40), confidence=0.2
                    )
                ]
            },
        )

        session.data.add_boxes_to_layer_at_frame_index.assert_called_once()
        session.data.replace_machine_boxes_at_frame_index.assert_called_once_with(
            VideoDataLayer.B, 5, []
        )
        session.data.add_boxes_to_layer_at_frame_index.assert_called_once_with(
            VideoDataLayer.A, 5, []
        )

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
