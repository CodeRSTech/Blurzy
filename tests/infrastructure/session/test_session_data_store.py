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

    def clone(self) -> "_FakeBox":
        return _FakeBox(key=self.key, confidence=self.confidence, is_manual=self.is_manual)


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
