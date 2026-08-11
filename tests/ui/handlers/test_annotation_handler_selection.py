from __future__ import annotations

from PySide6.QtCore import Qt

from app.ui.handlers.annotation_handler import AnnotationHandler
from app.ui.view_state.bbox_selection_state import BBoxSelectionState


class _FakeKeyEvent:
    def __init__(self, modifiers: Qt.KeyboardModifier, key: Qt.Key) -> None:
        self._modifiers = modifiers
        self._key = key

    def modifiers(self) -> Qt.KeyboardModifier:
        return self._modifiers

    def key(self) -> Qt.Key:
        return self._key


class _StubBottomPanel:
    def __init__(self, keys: list[str]) -> None:
        self._keys = list(keys)
        self.updated = False

    def get_all_box_keys_from_active_tab(self) -> list[str]:
        return list(self._keys)

    def _update_frame_box_buttons_state(self, prefer_shared_selection: bool = False) -> None:
        self.updated = True


class _StubWindow:
    def __init__(self, selection_keys: list[str] | None = None, all_keys: list[str] | None = None) -> None:
        self.bbox_selection_state = BBoxSelectionState()
        if selection_keys is not None:
            self.bbox_selection_state.set_selection(selection_keys)
        self.bottom_panel = _StubBottomPanel(all_keys or [])
        self.selected_s_id = "session-1"
        self.active_tab_index = 0

    @property
    def selected_frame_box_keys(self) -> list[str]:
        return self.bbox_selection_state.get_selected_keys()


def test_get_effective_selection_keys_uses_shared_selection() -> None:
    window = _StubWindow(selection_keys=["box-a"])
    handler = AnnotationHandler.__new__(AnnotationHandler)
    handler._window = window

    assert handler._get_effective_selection_keys("box-b") == ["box-a"]

    window.bbox_selection_state.clear()
    assert handler._get_effective_selection_keys("box-b") == ["box-b"]


def test_selection_shortcut_selects_all_boxes() -> None:
    window = _StubWindow(all_keys=["box-a", "box-b"])
    handler = AnnotationHandler.__new__(AnnotationHandler)
    handler._window = window

    handled = handler.handle_selection_shortcut(_FakeKeyEvent(Qt.KeyboardModifier.ControlModifier, Qt.Key.Key_A))

    assert handled is True
    assert set(window.bbox_selection_state.get_selected_keys()) == {"box-a", "box-b"}
    assert window.bottom_panel.updated is True
