from __future__ import annotations

from dataclasses import dataclass, field
import importlib
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock


class _QObjectStub:
    def __init__(self, *args, **kwargs):
        pass


_qtcore_module = sys.modules.get("PySide6.QtCore")
if isinstance(_qtcore_module, MagicMock):
    _qtcore_module.QObject = _QObjectStub

for _module_name in (
    "app.infrastructure.session.session_data_store",
    "app.infrastructure.session.session",
):
    _module = sys.modules.get(_module_name)
    if _module is not None:
        importlib.reload(_module)

from app.domain import VideoDataLayer  # noqa: E402
from app.infrastructure.session.session_data_store import SessionDataStore  # noqa: E402


@dataclass
class _FakeBox:
    key: str
    confidence: float
    is_manual: bool
    id: str = "box-1"
    source: object = field(default_factory=lambda: SimpleNamespace(value="Detection"))
    label: str = "person"
    bbox_xyxy: tuple[int, int, int, int] = (0, 0, 10, 10)
    color_hex: str = "#00ff00"

    def clone(self) -> "_FakeBox":
        return _FakeBox(
            key=self.key,
            confidence=self.confidence,
            is_manual=self.is_manual,
            id=self.id,
            source=self.source,
            label=self.label,
            bbox_xyxy=self.bbox_xyxy,
            color_hex=self.color_hex,
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

    def test_project_payload_round_trip_restores_boxes(self):
        store = SessionDataStore(s_id=MagicMock())
        box = _FakeBox(key="persisted", confidence=0.8, is_manual=False)
        store.add_box_to_layer_at_frame_index(VideoDataLayer.C, 4, box)

        payload = store.to_project_payload()

        restored = SessionDataStore(s_id=MagicMock())
        restored.load_project_payload(payload)

        boxes = restored.get_boxes_for_layer_at_frame_index_as_list(VideoDataLayer.C, 4)
        assert len(boxes) == 1
        assert boxes[0].key == "persisted"

    def test_machine_refresh_preserves_manual_boxes_and_replaces_all_frames_under_one_lock(self):
        class CountingLock:
            def __init__(self):
                import threading

                self._lock = threading.RLock()
                self.acquisitions = 0

            def __enter__(self):
                self.acquisitions += 1
                self._lock.acquire()
                return self

            def __exit__(self, exc_type, exc_value, traceback):
                self._lock.release()

        store = SessionDataStore(s_id=MagicMock())
        manual = _FakeBox(key="manual", confidence=0.7, is_manual=True)
        stale_machine = _FakeBox(key="stale", confidence=0.8, is_manual=False)
        replacement = _FakeBox(key="new", confidence=0.9, is_manual=False)
        store.add_boxes_to_layer_at_frame_index(VideoDataLayer.D, 0, [manual, stale_machine])
        store.add_box_to_layer_at_frame_index(
            VideoDataLayer.D,
            1,
            _FakeBox(key="stale-empty", confidence=0.8, is_manual=False),
        )
        lock = CountingLock()
        store._lock = lock

        store.replace_machine_boxes_for_frames(VideoDataLayer.D, {0: [replacement]}, 3)

        assert lock.acquisitions == 1
        frame_zero = store.get_boxes_for_layer_at_frame_index_as_list(VideoDataLayer.D, 0)
        assert [box.key for box in frame_zero] == ["manual", "new"]
        assert frame_zero[0] is manual
        assert frame_zero[1] is not replacement
        assert store.get_boxes_for_layer_at_frame_index_as_list(VideoDataLayer.D, 1) == []
        assert store.get_boxes_for_layer_at_frame_index_as_list(VideoDataLayer.D, 2) == []
