from __future__ import annotations

from types import SimpleNamespace

from PySide6.QtCore import Qt

from app.domain import AnnotationContextActions, VideoDataLayer
from app.ui.handlers.annotation_handler import AnnotationHandler
from app.ui.view_state.preview_state import ToolMode
from app.ui.view_state.bbox_selection_state import BBoxSelectionState
from app.ui.view_state.selection_history_state import SelectionHistoryState


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
        self.edit_box_btn = SimpleNamespace(clicked=SimpleNamespace(connect=lambda slot: None))
        self.relabel_box_btn = SimpleNamespace(clicked=SimpleNamespace(connect=lambda slot: None))
        self.delete_box_btn = SimpleNamespace(clicked=SimpleNamespace(connect=lambda slot: None))
        self.delete_next_occurrences_btn = SimpleNamespace(clicked=SimpleNamespace(connect=lambda slot: None))
        self.delete_prev_occurrences_btn = SimpleNamespace(clicked=SimpleNamespace(connect=lambda slot: None))
        self.copy_to_prev_btn = SimpleNamespace(clicked=SimpleNamespace(connect=lambda slot: None))
        self.copy_to_next_btn = SimpleNamespace(clicked=SimpleNamespace(connect=lambda slot: None))
        self.reset_frame_btn = SimpleNamespace(clicked=SimpleNamespace(connect=lambda slot: None))
        self.reset_all_btn = SimpleNamespace(clicked=SimpleNamespace(connect=lambda slot: None))
        self.reset_tracker_frame_btn = SimpleNamespace(clicked=SimpleNamespace(connect=lambda slot: None))
        self.reset_all_trackers_btn = SimpleNamespace(clicked=SimpleNamespace(connect=lambda slot: None))

    def get_all_box_keys_from_active_tab(self) -> list[str]:
        return list(self._keys)

    def _update_frame_box_buttons_state(self, prefer_shared_selection: bool = False) -> None:
        self.updated = True


class _StubPreviewContainer:
    def __init__(self) -> None:
        self.selected_keys: list[str] = []
        self.mode = None

    def set_selected_bbox_keys(self, keys: list[str]) -> None:
        self.selected_keys = list(keys)

    def set_tool_mode(self, mode) -> None:
        self.mode = mode


class _StubWindow:
    def __init__(self, selection_keys: list[str] | None = None, all_keys: list[str] | None = None) -> None:
        self.bbox_selection_state = BBoxSelectionState()
        self.selection_history_state = SelectionHistoryState()
        if selection_keys is not None:
            self.bbox_selection_state.set_selection(selection_keys)
        self.bottom_panel = _StubBottomPanel(all_keys or [])
        self.preview_container = _StubPreviewContainer()
        self.selected_s_id = "session-1"
        self.active_tab_index = 0
        self.transport_panel = SimpleNamespace(
            add_mode_btn=SimpleNamespace(setChecked=lambda checked: setattr(self, "_add_mode_checked", checked)),
            tool_group=SimpleNamespace(checkedId=lambda: 1),
        )
        self._status_text = ""

    @property
    def selected_frame_box_keys(self) -> list[str]:
        return self.bbox_selection_state.get_selected_keys()

    def set_status_text(self, text: str) -> None:
        self._status_text = text


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


def test_selection_shortcut_undo_restores_previous_selection() -> None:
    window = _StubWindow(selection_keys=["box-a"], all_keys=["box-a", "box-b"])
    handler = AnnotationHandler.__new__(AnnotationHandler)
    handler._window = window

    handled_select_all = handler.handle_selection_shortcut(
        _FakeKeyEvent(Qt.KeyboardModifier.ControlModifier, Qt.Key.Key_A)
    )
    handled_undo = handler.handle_selection_shortcut(
        _FakeKeyEvent(Qt.KeyboardModifier.ControlModifier, Qt.Key.Key_Z)
    )

    assert handled_select_all is True
    assert handled_undo is True
    assert window.bbox_selection_state.get_selected_keys() == ["box-a"]


def test_canvas_ctrl_click_toggles_selected_box() -> None:
    window = _StubWindow(selection_keys=["box-a"])
    handler = AnnotationHandler.__new__(AnnotationHandler)
    handler._window = window

    handler.on_preview_bbox_selection_requested("box-b", True)
    assert set(window.bbox_selection_state.get_selected_keys()) == {"box-a", "box-b"}

    handler.on_preview_bbox_selection_requested("box-a", True)
    assert window.bbox_selection_state.get_selected_keys() == ["box-b"]


def test_canvas_marquee_adds_boxes_to_existing_selection() -> None:
    window = _StubWindow(selection_keys=["box-a"])
    handler = AnnotationHandler.__new__(AnnotationHandler)
    handler._window = window

    handler.on_preview_bbox_marquee_selected(["box-b", "box-c"])

    assert set(window.bbox_selection_state.get_selected_keys()) == {"box-a", "box-b", "box-c"}


def test_group_drag_moves_every_emitted_box_key() -> None:
    window = _StubWindow()
    move_calls: list[dict[str, object]] = []
    render_calls: list[str] = []
    app = SimpleNamespace(
        change_current_layer_boxes_by_keys_and_dxdy=lambda **kwargs: move_calls.append(kwargs) or 2,
    )
    controller = SimpleNamespace(render_frame_for_session_id=lambda s_id: render_calls.append(s_id))
    handler = AnnotationHandler.__new__(AnnotationHandler)
    handler._window = window
    handler._app = app
    handler._controller = controller

    handler.on_preview_bboxes_moved(["box-a", "box-b"], 4, -3)

    assert move_calls == [
        {
            "s_id": "session-1",
            "layer_name": VideoDataLayer.B,
            "box_keys": ["box-a", "box-b"],
            "dx": 4,
            "dy": -3,
        }
    ]
    assert render_calls == ["session-1"]


def test_context_menu_copy_and_paste_use_clipboard_methods() -> None:
    window = _StubWindow(selection_keys=["box-a"])
    clipboard_calls: list[str] = []
    handler = AnnotationHandler.__new__(AnnotationHandler)
    handler._window = window
    handler._copy_selected_boxes_to_clipboard = lambda: clipboard_calls.append("copy") or True
    handler._paste_clipboard_to_current_frame = lambda: clipboard_calls.append("paste") or True

    handler.on_preview_context_action(AnnotationContextActions.COPY.value, "box-a")
    handler.on_preview_context_action(AnnotationContextActions.PASTE.value, "")

    assert clipboard_calls == ["copy", "paste"]


def test_context_menu_copy_current_duplicates_selection_on_current_frame() -> None:
    window = _StubWindow(selection_keys=["box-a"])
    duplicate_calls: list[list[str]] = []
    handler = AnnotationHandler.__new__(AnnotationHandler)
    handler._window = window
    handler._duplicate_selected_boxes_to_current_frame = lambda keys: duplicate_calls.append(list(keys)) or True

    handler.on_preview_context_action(AnnotationContextActions.COPY_CURRENT.value, "box-a")

    assert duplicate_calls == [["box-a"]]


def test_context_menu_delete_all_uses_active_table_keys() -> None:
    window = _StubWindow(all_keys=["box-a", "box-b"])
    deleted: list[bool] = []
    handler = AnnotationHandler.__new__(AnnotationHandler)
    handler._window = window
    handler.on_delete_selected = lambda: deleted.append(True)

    handler.on_preview_context_action(AnnotationContextActions.DELETE_ALL_BBOXES.value, "")

    assert set(window.bbox_selection_state.get_selected_keys()) == {"box-a", "box-b"}
    assert deleted == [True]


def test_context_menu_add_bbox_here_switches_to_add_mode() -> None:
    window = _StubWindow()
    controller = SimpleNamespace(window=window)
    handler = AnnotationHandler.__new__(AnnotationHandler)
    handler._window = window
    handler._controller = controller

    handler.on_preview_context_action(AnnotationContextActions.ADD_BBOX_HERE.value, "")

    assert window.preview_container.mode == ToolMode.ADD
    assert window._status_text == "Add mode enabled. Click and drag to place a new box."
