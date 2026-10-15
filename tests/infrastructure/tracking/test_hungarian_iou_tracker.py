from __future__ import annotations

from app.domain.detection import BoxSource
from app.domain.views import BBoxViewModel
from app.infrastructure.tracking.hungarian_tracker import HungarianIoUTracker, TrackInput
from app.infrastructure.tracking.tracking_strategy import HungarianStrategy


class TestHungarianIoUTracker:
    def test_update_with_no_tracks_and_no_detections_returns_empty(self):
        tracker = HungarianIoUTracker()
        assert tracker.update([]) == []

    def test_unmatched_detection_spawns_new_track(self):
        tracker = HungarianIoUTracker()
        states = tracker.update([TrackInput(bbox_xyxy=(0, 0, 10, 10), confidence=0.8, label="person")])

        assert len(states) == 1
        assert states[0].uid == 1
        assert states[0].label == "person"

    def test_second_frame_matching_preserves_uid(self):
        tracker = HungarianIoUTracker(iou_threshold=0.1)
        first = tracker.update([TrackInput(bbox_xyxy=(0, 0, 10, 10), confidence=0.8, label="person")])
        second = tracker.update([TrackInput(bbox_xyxy=(1, 1, 11, 11), confidence=0.8, label="person")])

        assert len(first) == 1
        assert len(second) == 1
        assert second[0].uid == first[0].uid
        assert second[0].observed

    def test_unmatched_tracks_coast_internally_without_being_observed(self):
        tracker = HungarianIoUTracker()
        first = tracker.update(
            [TrackInput(bbox_xyxy=(0, 0, 10, 10), confidence=0.8, label="person")]
        )

        coasted = tracker.update([])

        assert first[0].observed
        assert len(coasted) == 1
        assert not coasted[0].observed
        assert coasted[0].uid == first[0].uid

    def test_hungarian_strategy_emits_tagged_coast_boxes(self):
        detection = BBoxViewModel(
            id="d-1",
            source=BoxSource.DETECTION,
            label="person",
            bbox_xyxy=(0, 0, 10, 10),
            color_hex="#ffffff",
            confidence=0.9,
            key="d-1",
        )

        result = HungarianStrategy().track({0: [detection]}, total_frames=3)

        assert len(result[0]) == 1
        assert result[1][0].detection_backed is False
        assert result[1][0].time_since_update == 1
        assert result[2][0].detection_backed is False
        assert result[2][0].time_since_update == 2

    def test_reset_clears_tracks_and_resets_uid_sequence(self):
        tracker = HungarianIoUTracker()
        tracker.update([TrackInput(bbox_xyxy=(0, 0, 10, 10), confidence=0.8, label="person")])
        tracker.reset()

        states = tracker.update([TrackInput(bbox_xyxy=(20, 20, 30, 30), confidence=0.8, label="car")])
        assert len(states) == 1
        assert states[0].uid == 1
