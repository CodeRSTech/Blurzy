from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import MagicMock

from app.domain import VideoDataLayer
from app.infrastructure.session.session_data_store import SessionDataStore


@dataclass
class _FakeBox:
    key: str
    confidence: float
    is_manual: bool
    bbox_xyxy: tuple[int, int, int, int] = (0, 0, 10, 10)

    def clone(self) -> "_FakeBox":
        return _FakeBox(
            key=self.key,
            confidence=self.confidence,
            is_manual=self.is_manual,
            bbox_xyxy=self.bbox_xyxy,
        )


class TestSessionDataStore:
    def test_add_and_read_boxes_for_layer_and_frame(self):
        store = SessionDataStore(s_id=MagicMock())
        box = _FakeBox(key="k1", confidence=0.9, is_manual=False)

        store.add_box_to_layer_at_frame_index(VideoDataLayer.B, 3, box)

        boxes = store.get_boxes_for_layer_at_frame_index_as_list(VideoDataLayer.B, 3)
        assert len(boxes) == 1
        assert boxes[0].key == "k1"

    def test_delete_by_id_at_frame_index_returns_true_when_deleted(self):
        store = SessionDataStore(s_id=MagicMock())
        b1 = _FakeBox(key="drop", confidence=0.9, is_manual=False)
        b2 = _FakeBox(key="keep", confidence=0.9, is_manual=False)
        store.add_boxes_to_layer_at_frame_index(VideoDataLayer.B, 1, [b1, b2])

        deleted = store.delete_boxes_from_layer_by_id_at_frame_index(VideoDataLayer.B, ["drop"], 1)

        assert deleted is True
        remaining = store.get_boxes_for_layer_at_frame_index_as_list(VideoDataLayer.B, 1)
        assert [b.key for b in remaining] == ["keep"]

    def test_clear_layer_keep_manual_preserves_manual_boxes(self):
        store = SessionDataStore(s_id=MagicMock())
        manual = _FakeBox(key="m", confidence=0.6, is_manual=True)
        auto = _FakeBox(key="a", confidence=0.6, is_manual=False)
        store.add_boxes_to_layer_at_frame_index(VideoDataLayer.D, 8, [manual, auto])

        store.clear_layer_by_name(VideoDataLayer.D, keep_manual=True)

        boxes = store.get_boxes_for_layer_at_frame_index_as_list(VideoDataLayer.D, 8)
        assert [b.key for b in boxes] == ["m"]

    def test_move_selected_boxes_moves_manual_and_detected_boxes(self):
        store = SessionDataStore(s_id=MagicMock())
        manual = _FakeBox(key="manual", confidence=0.6, is_manual=True)
        detected = _FakeBox(key="detected", confidence=0.9, is_manual=False)
        unselected = _FakeBox(key="unselected", confidence=0.8, is_manual=False)
        store.add_boxes_to_layer_at_frame_index(VideoDataLayer.B, 2, [manual, detected, unselected])

        moved = store.move_boxes_in_layer_at_frame_index_by_delta(
            VideoDataLayer.B,
            2,
            {"manual", "detected"},
            3,
            -2,
        )

        assert moved == 2
        assert manual.bbox_xyxy == (3, -2, 13, 8)
        assert detected.bbox_xyxy == (3, -2, 13, 8)
        assert unselected.bbox_xyxy == (0, 0, 10, 10)

    def test_empty_frame_remains_initialized_after_its_last_box_is_deleted(self):
        store = SessionDataStore(s_id=MagicMock())
        store.add_box_to_layer_at_frame_index(
            VideoDataLayer.B,
            2,
            _FakeBox(key="only-box", confidence=0.9, is_manual=False),
        )

        store.delete_boxes_from_layer_by_id_at_frame_index(VideoDataLayer.B, ["only-box"], 2)

        assert store.has_boxes_for_layer_at_frame_index(VideoDataLayer.B, 2) is False
        assert store.has_frame_for_layer_at_frame_index(VideoDataLayer.B, 2) is True
