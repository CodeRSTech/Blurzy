from __future__ import annotations

from app.infrastructure.tracking.hungarian_tracker import HungarianIoUTracker, TrackInput


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

    def test_reset_clears_tracks_and_resets_uid_sequence(self):
        tracker = HungarianIoUTracker()
        tracker.update([TrackInput(bbox_xyxy=(0, 0, 10, 10), confidence=0.8, label="person")])
        tracker.reset()

        states = tracker.update([TrackInput(bbox_xyxy=(20, 20, 30, 30), confidence=0.8, label="car")])
        assert len(states) == 1
        assert states[0].uid == 1
