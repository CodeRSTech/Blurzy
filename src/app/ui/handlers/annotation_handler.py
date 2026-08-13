"""Annotation creation and editing handler for bounding detection management."""

# [10-08-26 05:00 PM] `AnnotationHandler` has a lot of responsibilities, we must create a module
# `annotation_handler` or just `annotation` under `src/app/ui/handlers` and move all the related logic there.
# Almost every single one of the responsibilities must be within a separate file (or module) of its own.
# [NOTE] Not very urgent.
#
# [10-08-26 05:08 PM] The Term "Annotation" is rather confusing. We deal specifically with "boxes" here.
# We must check if any other synonyms are there OR, whether `BoxHandler` is just fine.
#
# [10-08-26 05:11 PM] Originally, box/boxes were referred to as `item`/`items` and variables like its key/keys were referred to
# as `item_key`/`item_keys` which IS still present throughtout the codebase and slowly being replaced with the right
# terms. [IMPORTANT] [NOTE] The IDE has powerful tools to do this. Therefore, an AI agent mustn't worry about it.
# [10-08-26 05:18 PM] [UPDATE] All references to `item` in this file have been swapped with `box`.
#
from __future__ import annotations

import time
from typing import TYPE_CHECKING, final, override

from PySide6.QtCore import Qt, Slot, QObject

from PySide6.QtWidgets import QDialog

from app.domain import AnnotationContextActions, Direction, VideoDataLayer, VideoDataLayerGroup
from app.shared.logging_cfg import get_logger
from app.ui.qt.dialogs import LabelDialog
from app.ui.view_state.preview_state import ToolMode
from app.ui.view_state.selection_history_state import CopiedBBoxSnapshot
if TYPE_CHECKING:
    from PySide6.QtGui import QKeyEvent


if TYPE_CHECKING:
    from app.domain.session.session_id import SessionId
    from app.domain.base.dtypes import BBoxXYXYTuple
    from app.ui.uicontroller import UIController

logger = get_logger("UI->AnnotationHandler")


@final
class AnnotationHandler(QObject):
    """
    Manages detection creation, editing, and deletion operations.

    Responsibilities:
        - Handle manual bounding detection drawing and labeling.
        - Edit existing annotations (move, resize, relabel).
        - Delete annotations (single or in direction).
        - Copy annotations to adjacent frames.
        - Handle keyboard nudge commands for detection positioning.
        - Route context menu actions (copy, delete in direction).

    Note:
        Signal flow:
            Receives signals from the preview container (bbox drawn, edited, deleted).
            Receives signals from the bottom panel (edit, delete, copy buttons).
            Handles keyboard events for detection nudging with acceleration.
            Emits frame render requests after detection changes.
    """

    def __init__(self, controller: UIController) -> None:
        super().__init__()
        self.setParent(controller)

        self._controller = controller
        self._window = controller.window
        self._app = controller.app

        # [AUDIT] ENCAPSULATION: Keyboard acceleration view_state scattered across 3 attributes
        # Three separate view_state variables manage a single concern (keyboard acceleration):
        #   - _last_move_key: which key was pressed
        #   - _last_move_ts: when it was pressed
        #   - _move_repeat_count: how many repeats
        # This creates high coupling within the handler and is error-prone.
        # Recommendation: Extract into KeyboardAccelerator class:
        #
        # class KeyboardAccelerator:
        #     def __init__(self):
        #         self.last_key = None
        #         self.last_ts = 0.0
        #         self.repeat_count = 0
        #     def is_accelerated(self, key, ts): ...
        #     def reset(self): ...
        #
        # Usage: self._accelerator = KeyboardAccelerator()
        # Benefits: Encapsulates logic, improves cohesion, easier to test
        # Keyboard nudge acceleration view_state.
        self._last_move_key: int | None = None
        self._last_move_ts: float = 0.0
        self._move_repeat_count: int = 0

        self._connect_signals()

    @override
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}>"

    @override
    def __str__(self) -> str:
        return f"{self.__class__.__name__}"

    def _connect_signals(self):
        # [AUDIT] DRY VIOLATION: Signal connection pattern repeated across handlers
        # This same for-loop pattern appears in DetectionHandler, TrackingHandler, SessionHandler.
        # Each handler duplicates the signal-to-slot binding boilerplate.
        # Recommendation: Extract into utility class to reduce maintenance burden:
        #
        # class SignalConnector:
        #     @staticmethod
        #     def connect_many(handler, signal_slot_pairs):
        #         for signal, slot in signal_slot_pairs:
        #             signal.connect(slot)
        #
        # Usage:
        #     SignalConnector.connect_many(self, [
        #         (preview.bbox_drawn, self.on_bbox_drawn),
        #         ...
        #     ])
        #
        # Benefits:
        #   - Reduces boilerplate in each handler
        #   - Single place to add error handling (e.g., duplicate connection detection)
        #   - Improves maintainability
        preview_container = self._controller.window.preview_container
        bottom_panel = self._controller.window.bottom_panel

        for signal, slot in [
            (preview_container.bbox_drawn, self.on_preview_bbox_drawn),
            (preview_container.bbox_edited, self.on_preview_bbox_edited),
            (preview_container.bbox_deleted, self.on_preview_bbox_deleted),
            (preview_container.bbox_selected, self.on_preview_bbox_selected),  # New: canvas selection
            (preview_container.bbox_selection_requested, self.on_preview_bbox_selection_requested),
            (preview_container.bbox_selection_cleared, self.on_preview_bbox_selection_cleared),
            (preview_container.bbox_marquee_selected, self.on_preview_bbox_marquee_selected),
            (preview_container.bboxes_moved, self.on_preview_bboxes_moved),
            (preview_container.context_action_triggered, self.on_preview_context_action),
            # Bottom panel action row buttons
            (bottom_panel.edit_box_btn.clicked, self.on_edit_selected),
            (bottom_panel.relabel_box_btn.clicked, self.on_relabel_selected),
            (bottom_panel.delete_box_btn.clicked, self.on_delete_selected),
            (bottom_panel.delete_next_occurrences_btn.clicked, self.on_delete_next_occurrences),
            (bottom_panel.delete_prev_occurrences_btn.clicked, self.on_delete_prev_occurrences),
            (bottom_panel.copy_to_prev_btn.clicked, self.on_copy_to_prev),
            (bottom_panel.copy_to_next_btn.clicked, self.on_copy_to_next),
            # Reset actions are exposed in the Edit menu but routed to these same buttons.
            (bottom_panel.reset_frame_btn.clicked, self.on_reset_frame),
            (bottom_panel.reset_all_btn.clicked, self.on_reset_all),
            (bottom_panel.reset_tracker_frame_btn.clicked, self.on_reset_tracker_frame),
            (bottom_panel.reset_all_trackers_btn.clicked, self.on_reset_all_trackers),
        ]:
            signal.connect(slot)

    def handle_new_drawn_box(self, s_id: SessionId, x1: int, y1: int, x2: int, y2: int) -> None:
        """
        Handles the addition of a new drawn box.
    
        This function is triggered when a new box is drawn on the interface. It prompts the user
        to provide a label for the box via a dialog. If a valid label is provided and accepted, the function
        attempts to add the box, updates the user interface, and triggers the provided rendering
        function to refresh the box visually.
    
        Args:
            s_id (SessionId): A unique identifier for the current session.
            x1 (int): The x-coordinate of the top-left corner of the box.
            y1 (int): The y-coordinate of the top-left corner of the box.
            x2 (int): The x-coordinate of the bottom-right corner of the box.
            y2 (int): The y-coordinate of the bottom-right corner of the box.
        """
        dialog = LabelDialog(self._window)
        if dialog.exec() == LabelDialog.DialogCode.Accepted and dialog.get_label():
            label = dialog.get_label()
            try:
                before_boxes = self._get_current_frame_boxes_snapshot() if self._can_record_mutation() else []
                before_selection = list(self._window.selected_frame_box_keys)
                self._app.add_manual_detection_box_at_current_frame_index(s_id, label, (x1, y1, x2, y2))
                if self._can_record_mutation():
                    self._record_current_frame_mutation(before_boxes, before_selection)
                self._window.set_status_text("Box added.")
                self._controller.render_frame_for_session_id(s_id)
            except Exception as exc:
                self._window.show_error("Add Failed", str(exc))

        # Stay in Add mode so repeated box creation keeps the toolbar view_state
        # and overlay behavior in sync.

    def handle_existing_box_edit(
            self,
            s_id: SessionId,
            box_key: str,
            new_coords: BBoxXYXYTuple | None = None,
    ) -> None:
        """Handles both visual drags (new_coords) and table 'Edit' clicks (dialog)."""
        tab = self._window.active_tab_index

        box = (
            self._app.get_layer_box_by_key(s_id, VideoDataLayer.D, box_key)
            if tab == VideoDataLayerGroup.TRACKING
            else self._app.get_layer_box_by_key(s_id, VideoDataLayer.B, box_key)
        )
        if box is None:
            return

        label, bbox_xyxy = box.label, box.bbox_xyxy

        if new_coords:
            bbox_xyxy = new_coords  # It was visually dragged
        else:
            # It was clicked via "Edit Selected" button, show dialog
            dialog = self._controller.create_edit_annotation_dialogue(
                initial_label=label, initial_bbox_xyxy=bbox_xyxy
            )
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return
            label, bbox_xyxy = dialog.get_annotation_data()

        try:
            before_boxes = self._get_current_frame_boxes_snapshot() if self._can_record_mutation() else []
            before_selection = list(self._window.selected_frame_box_keys)
            self._app.update_box_in_layer_at_current_frame(
                s_id=s_id,
                layer_name=VideoDataLayer.B if tab == VideoDataLayerGroup.DETECTION else VideoDataLayer.D,
                box_key=box.key,
                label=label,
                bbox_xyxy=bbox_xyxy,
            )
            if self._can_record_mutation():
                self._record_current_frame_mutation(before_boxes, before_selection)
            self._controller.render_frame_for_session_id(s_id)
        except Exception as exc:
            self._window.show_error("Edit Failed", str(exc))

    def _get_effective_selection_keys(self, fallback_box_key: str | None = None) -> list[str]:
        """Return the current shared selection, falling back to a clicked box key if needed."""
        selected_keys = self._window.selected_frame_box_keys
        if selected_keys:
            return selected_keys
        if fallback_box_key:
            return [fallback_box_key]
        return []

    def _apply_selection_keys(self, keys: list[str], *, record_history: bool) -> None:
        before_keys = self._window.selected_frame_box_keys
        self._window.bbox_selection_state.set_selection(keys)
        logger.debug("Selection changed from {} to {}.", before_keys, keys)
        logger.trace("Synchronizing {} selected box keys to table and overlay.", len(keys))
        self._window.bottom_panel._update_frame_box_buttons_state(prefer_shared_selection=True)
        self._window.preview_container.set_selected_bbox_keys(keys)

        if not record_history:
            return

        s_id = self._window.selected_s_id
        if not s_id:
            return

        self._window.selection_history_state.record_selection_change(
            session_id=str(s_id),
            tab_index=int(self._window.active_tab_index),
            before_keys=before_keys,
            after_keys=keys,
        )

    def _get_current_frame_boxes_snapshot(self, frame_index: int | None = None) -> list:
        """Clone active-tab boxes so a mutation can be restored exactly."""
        s_id = self._window.selected_s_id
        if not s_id:
            return []
        if frame_index is None:
            frame_boxes = self._app.get_tab_frame_boxes_for_session_id(s_id, self._window.active_tab_index)
            return [box.clone() for box in frame_boxes.frame_data_boxes]
        return self._app.get_tab_frame_boxes_at_frame_index(s_id, self._window.active_tab_index, frame_index)

    def _can_record_mutation(self) -> bool:
        return all(
            hasattr(self._app, attribute)
            for attribute in (
                "get_tab_frame_boxes_for_session_id",
                "get_tab_frame_boxes_at_frame_index",
                "get_session_by_id",
            )
        )

    def _record_current_frame_mutation(
            self,
            before_boxes: list,
            before_selection: list[str],
            frame_index: int | None = None,
    ) -> None:
        s_id = self._window.selected_s_id
        if not s_id:
            return
        if frame_index is None:
            frame_index = self._app.get_session_by_id(s_id).state.playback.current_frame_index
        after_boxes = self._get_current_frame_boxes_snapshot(frame_index)
        after_selection = self._window.selected_frame_box_keys
        self._window.selection_history_state.record_box_mutation(
            session_id=str(s_id),
            tab_index=int(self._window.active_tab_index),
            frame_index=frame_index,
            before_boxes=before_boxes,
            after_boxes=after_boxes,
            before_selection=before_selection,
            after_selection=after_selection,
        )
        logger.trace(
            "Recorded frame mutation at frame {}: {} boxes -> {} boxes.",
            frame_index,
            len(before_boxes),
            len(after_boxes),
        )

    def _restore_box_mutation(self, entry, use_after_state: bool) -> None:
        s_id = self._window.selected_s_id
        if not s_id:
            return
        boxes = list(entry.after_boxes if use_after_state else entry.before_boxes)
        selection = list(entry.after_selection if use_after_state else entry.before_selection)
        self._app.replace_tab_frame_boxes(
            s_id=s_id,
            tab=self._window.active_tab_index,
            frame_index=entry.frame_index,
            boxes=boxes,
        )
        self._apply_selection_keys(selection, record_history=False)
        self._controller.render_frame_for_session_id(s_id)

    def _undo_selection_shortcut(self) -> bool:
        s_id = self._window.selected_s_id
        if not s_id:
            return True

        mutation = self._window.selection_history_state.undo_box_mutation(
            session_id=str(s_id),
            tab_index=int(self._window.active_tab_index),
        )
        if mutation is not None:
            logger.debug("Undoing box mutation for frame {}.", mutation.frame_index)
            self._restore_box_mutation(mutation, use_after_state=False)
            return True

        restored_keys = self._window.selection_history_state.undo_selection(
            session_id=str(s_id),
            tab_index=int(self._window.active_tab_index),
        )
        if restored_keys is None:
            self._window.set_status_text("Nothing to undo.")
            return True

        self._apply_selection_keys(restored_keys, record_history=False)
        return True

    def _redo_selection_shortcut(self) -> bool:
        s_id = self._window.selected_s_id
        if not s_id:
            return True

        mutation = self._window.selection_history_state.redo_box_mutation(
            session_id=str(s_id),
            tab_index=int(self._window.active_tab_index),
        )
        if mutation is not None:
            logger.debug("Redoing box mutation for frame {}.", mutation.frame_index)
            self._restore_box_mutation(mutation, use_after_state=True)
            return True

        restored_keys = self._window.selection_history_state.redo_selection(
            session_id=str(s_id),
            tab_index=int(self._window.active_tab_index),
        )
        if restored_keys is None:
            self._window.set_status_text("Nothing to redo.")
            return True

        self._apply_selection_keys(restored_keys, record_history=False)
        return True

    def _copy_selected_boxes_to_clipboard(self) -> bool:
        s_id = self._window.selected_s_id
        selected_keys = self._window.selected_frame_box_keys
        if not s_id or not selected_keys:
            self._window.set_status_text("No selected boxes to copy.")
            return True

        frame_boxes_vm = self._app.get_tab_frame_boxes_for_session_id(s_id, self._window.active_tab_index)
        by_key = {box.key: box for box in frame_boxes_vm.frame_data_boxes}

        copied_boxes: list[CopiedBBoxSnapshot] = []
        for key in selected_keys:
            box = by_key.get(key)
            if box is None:
                continue
            copied_boxes.append(
                CopiedBBoxSnapshot(
                    label=box.label,
                    bbox_xyxy=box.bbox_xyxy,
                    color_hex=box.color_hex,
                )
            )

        if not copied_boxes:
            self._window.set_status_text("No selected boxes to copy.")
            return True

        self._window.selection_history_state.set_clipboard_boxes(
            boxes=copied_boxes,
            tab_index=int(self._window.active_tab_index),
        )
        self._window.set_status_text(f"Copied {len(copied_boxes)} box(es).")
        return True

    def _paste_clipboard_to_current_frame(self) -> bool:
        s_id = self._window.selected_s_id
        if not s_id:
            return True

        if not self._window.selection_history_state.has_clipboard_boxes:
            self._window.set_status_text("Clipboard is empty.")
            return True

        copied_boxes = self._window.selection_history_state.get_clipboard_boxes()
        if not copied_boxes:
            self._window.set_status_text("Clipboard is empty.")
            return True

        try:
            before_boxes = self._get_current_frame_boxes_snapshot() if self._can_record_mutation() else []
            before_selection = self._window.selected_frame_box_keys
            pasted_keys = self._app.add_manual_boxes_to_current_frame(
                s_id=s_id,
                tab=self._window.active_tab_index,
                boxes=[(box.label, box.bbox_xyxy, box.color_hex) for box in copied_boxes],
            )
            self._apply_selection_keys(pasted_keys, record_history=False)
            if self._can_record_mutation():
                self._record_current_frame_mutation(before_boxes, before_selection)
            self._controller.render_frame_for_session_id(s_id)
            self._window.set_status_text(f"Pasted {len(copied_boxes)} box(es).")
        except Exception as exc:
            self._window.show_error("Paste Failed", str(exc))

        return True

    def _duplicate_selected_boxes_to_current_frame(self, keys: list[str]) -> bool:
        s_id = self._window.selected_s_id
        if not s_id or not keys:
            self._window.set_status_text("No selected boxes to duplicate.")
            return True

        frame_boxes_vm = self._app.get_tab_frame_boxes_for_session_id(s_id, self._window.active_tab_index)
        by_key = {box.key: box for box in frame_boxes_vm.frame_data_boxes}
        duplicates = [
            (box.label, box.bbox_xyxy, box.color_hex)
            for key in keys
            if (box := by_key.get(key)) is not None
        ]
        if not duplicates:
            self._window.set_status_text("No selected boxes to duplicate.")
            return True

        try:
            before_boxes = self._get_current_frame_boxes_snapshot() if self._can_record_mutation() else []
            before_selection = list(self._window.selected_frame_box_keys)
            created_keys = self._app.add_manual_boxes_to_current_frame(
                s_id=s_id,
                tab=self._window.active_tab_index,
                boxes=duplicates,
            )
            self._apply_selection_keys(created_keys, record_history=False)
            if self._can_record_mutation():
                self._record_current_frame_mutation(before_boxes, before_selection)
            self._controller.render_frame_for_session_id(s_id)
            self._window.set_status_text(f"Duplicated {len(created_keys)} box(es) on the current frame.")
        except Exception as exc:
            self._window.show_error("Duplicate Failed", str(exc))
        return True

    def handle_delete_key(self, event: QKeyEvent) -> bool:
        if event.modifiers() != Qt.KeyboardModifier.NoModifier:
            return False
        if event.key() != Qt.Key.Key_Delete:
            return False

        s_id = self._window.selected_s_id
        keys = self._window.selected_frame_box_keys
        if not s_id or not keys:
            return True

        self.on_delete_selected()
        return True

    def handle_selection_shortcut(self, event: QKeyEvent) -> bool:
        if event.modifiers() != Qt.KeyboardModifier.ControlModifier:
            return False

        key = event.key()
        if key == Qt.Key.Key_A:
            all_keys = self._window.bottom_panel.get_all_box_keys_from_active_tab()
            self._apply_selection_keys(all_keys, record_history=True)
            return True
        if key == Qt.Key.Key_D:
            self._apply_selection_keys([], record_history=True)
            return True
        if key == Qt.Key.Key_I:
            all_keys = self._window.bottom_panel.get_all_box_keys_from_active_tab()
            current_keys = set(self._window.selected_frame_box_keys)
            inverted = [key for key in all_keys if key not in current_keys]
            self._apply_selection_keys(inverted, record_history=True)
            return True
        if key == Qt.Key.Key_Z:
            return self._undo_selection_shortcut()
        if key == Qt.Key.Key_Y:
            return self._redo_selection_shortcut()
        if key == Qt.Key.Key_C:
            return self._copy_selected_boxes_to_clipboard()
        if key == Qt.Key.Key_V:
            return self._paste_clipboard_to_current_frame()
        if key == Qt.Key.Key_X:
            if self._copy_selected_boxes_to_clipboard():
                self.on_delete_selected()
            return True

        return False

    def handle_nudge_key(self, event: QKeyEvent) -> bool:
        if event.modifiers() != Qt.KeyboardModifier.NoModifier:
            return False

        key = event.key()
        if key not in (Qt.Key.Key_Up, Qt.Key.Key_Down, Qt.Key.Key_Left, Qt.Key.Key_Right):
            return False

        s_id = self._window.selected_s_id
        box_keys = self._window.selected_frame_box_keys
        if not s_id or not box_keys:
            return True

        delta = self._get_nudge_delta(key)
        dx, dy = 0, 0
        if key == Qt.Key.Key_Left:
            dx = -delta
        elif key == Qt.Key.Key_Right:
            dx = delta
        elif key == Qt.Key.Key_Up:
            dy = -delta
        elif key == Qt.Key.Key_Down:
            dy = delta

        try:
            before_boxes = self._get_current_frame_boxes_snapshot() if self._can_record_mutation() else []
            before_selection = list(box_keys)
            if self._window.active_tab_index == VideoDataLayerGroup.DETECTION:
                moved = self._app.change_current_layer_boxes_by_keys_and_dxdy(s_id=s_id,
                                                                              layer_name=VideoDataLayer.B,
                                                                              box_keys=box_keys, dx=dx,
                                                                              dy=dy)
            else:  # self._window.active_tab_index == DataTab.TRACKING
                moved = self._app.change_current_layer_boxes_by_keys_and_dxdy(s_id=s_id,
                                                                              layer_name=VideoDataLayer.D,
                                                                              box_keys=box_keys, dx=dx,
                                                                              dy=dy)
            if moved > 0:
                if self._can_record_mutation():
                    self._record_current_frame_mutation(before_boxes, before_selection)
                self._controller.render_frame_for_session_id(s_id)
        except Exception as exc:
            self._window.show_error("Move Failed", str(exc))

        return True

    @Slot()
    def on_edit_selected(self) -> None:
        """
        Open edit dialog for the selected detection if exactly one detection is selected,
        allow user to modify label and coordinates.
        """
        s_id = self._window.selected_s_id
        keys = self._window.selected_frame_box_keys
        if not s_id or len(keys) != 1:
            return

        # ====================================================================
        # 1. EDIT SELECTED BOX
        # ====================================================================
        self.handle_existing_box_edit(s_id, keys[0])

    @Slot()
    def on_delete_selected(self) -> None:
        """
        Delete the currently selected boxes.

        Flow:

        ``on_delete_selected()`` `[this slot]`:
         |
         | ├── Get selected session and detection keys
         | ├── Delete boxes from the active tab (Detection or Tracking)
         | └──> Render frame with updated boxes
        """
        s_id = self._window.selected_s_id
        keys = self._window.selected_frame_box_keys
        if not s_id or not keys:
            return

        try:
            before_boxes = self._get_current_frame_boxes_snapshot()
            before_selection = list(keys)
            # ================================================================
            # 1. DELETE BOXES FROM ACTIVE TAB
            # ================================================================
            self._app.delete_boxes_by_keys_and_tab_id_for_current_frame_by_session_id(
                s_id=s_id, box_keys=keys, tab=self._window.active_tab_index
            )
            logger.debug("Deleted {} selected boxes; clearing their shared selection.", len(keys))
            logger.trace("Deleted box keys: {}", keys)
            self._apply_selection_keys([], record_history=True)
            self._record_current_frame_mutation(before_boxes, before_selection)

            # ================================================================
            # 2. RENDER FRAME WITH UPDATED BOXES
            # ================================================================
            self._controller.render_frame_for_session_id(s_id)
        except Exception as exc:
            self._window.show_error("Delete Failed", str(exc))

    @Slot()
    def on_relabel_selected(self) -> None:
        """Relabel the currently selected boxes using a dialog."""
        s_id = self._window.selected_s_id
        keys = self._window.selected_frame_box_keys
        if not s_id or not keys:
           return

        current_label = ""
        if len(keys) == 1:
           layer_name = VideoDataLayer.B if self._window.active_tab_index == VideoDataLayerGroup.DETECTION else VideoDataLayer.D
           box = self._app.get_layer_box_by_key(s_id, layer_name, keys[0])
           if box is not None:
               current_label = box.label

        dialog = LabelDialog(self._window, initial_label=current_label)
        if dialog.exec() != QDialog.DialogCode.Accepted:
           return

        new_label = dialog.get_label()
        if not new_label:
           return

        try:
           before_boxes = self._get_current_frame_boxes_snapshot()
           before_selection = list(keys)
           layer_name = VideoDataLayer.B if self._window.active_tab_index == VideoDataLayerGroup.DETECTION else VideoDataLayer.D
           for key in keys:
               box = self._app.get_layer_box_by_key(s_id, layer_name, key)
               if box is None:
                   continue
               self._app.update_box_in_layer_at_current_frame(
                   s_id=s_id,
                   layer_name=layer_name,
                   box_key=key,
                   label=new_label,
                   bbox_xyxy=box.bbox_xyxy,
               )
           self._record_current_frame_mutation(before_boxes, before_selection)
           self._controller.render_frame_for_session_id(s_id)
        except Exception as exc:
           self._window.show_error("Relabel Failed", str(exc))

    @Slot()
    def on_copy_to_next(self) -> None:
        """
        Copy selected annotations to the next frame.
        """
        self.copy_to_direction(direction=Direction.NEXT)

    @Slot()
    def on_copy_to_prev(self) -> None:
        """
        Copy selected annotations to the previous frame.
        """
        self.copy_to_direction(direction=Direction.PREV)

    @Slot()
    def on_reset_frame(self) -> None:
        s_id = self._window.selected_s_id
        if not s_id:
            return
        try:
            idx = self._app.get_session_by_id(s_id).state.playback.current_frame_index
            self._app.reset_frame_for_layer(s_id, VideoDataLayer.B, idx)
            self._controller.render_frame_for_session_id(s_id)
        except Exception as exc:
            self._window.show_error("Reset Failed", str(exc))

    @Slot()
    def on_reset_all(self) -> None:
        s_id = self._window.selected_s_id
        if not s_id:
            return
        try:
            self._app.reset_all_for_layer(s_id, VideoDataLayer.B)
            self._controller.render_frame_for_session_id(s_id)
        except Exception as exc:
            self._window.show_error("Reset All Failed", str(exc))

    @Slot()
    def on_reset_tracker_frame(self) -> None:
        s_id = self._window.selected_s_id
        if not s_id:
            return
        try:
            idx = self._app.get_session_by_id(s_id).state.playback.current_frame_index
            self._app.reset_frame_for_layer(s_id, VideoDataLayer.D, idx)
            self._controller.render_frame_for_session_id(s_id)
        except Exception as exc:
            self._window.show_error("Reset Tracker Frame Failed", str(exc))

    @Slot()
    def on_reset_all_trackers(self) -> None:
        s_id = self._window.selected_s_id
        if not s_id:
            return
        try:
            self._app.reset_all_for_layer(s_id, VideoDataLayer.D)
            self._controller.render_frame_for_session_id(s_id)
        except Exception as exc:
            self._window.show_error("Reset All Trackers Failed", str(exc))

    @Slot()
    def on_delete_next_occurrences(self) -> None:
        self._delete_occurrences(direction=Direction.NEXT)

    @Slot()
    def on_delete_prev_occurrences(self) -> None:
        self._delete_occurrences(direction=Direction.PREV)

    @Slot(object, str, int, int, int, int)
    def _on_bbox_drawn(self, s_id: SessionId, label: str, x1: int, y1: int, x2: int, y2: int) -> None:
        preview = self._window.preview_container
        # Disconnect immediately — one-shot behaviour
        try:
            _ = preview.bbox_drawn.disconnect()
        except RuntimeError:
            logger.opt(exception=True).info(
                "Failed to disconnect bbox_drawn signal from preview_container!"
            )

        bbox_xyxy = (x1, y1, x2, y2)
        try:
            before_boxes = self._get_current_frame_boxes_snapshot() if self._can_record_mutation() else []
            before_selection = list(self._window.selected_frame_box_keys)
            self._app.add_manual_detection_box_at_current_frame_index(s_id, label, bbox_xyxy)
            if self._can_record_mutation():
                self._record_current_frame_mutation(before_boxes, before_selection)
            self._controller.render_frame_for_session_id(s_id)
            self._window.set_status_text("Annotation added.")
        except Exception as exc:
            self._window.show_error("Add Failed", str(exc))

    @Slot(int, int, int, int)
    def on_preview_bbox_drawn(self, x1: int, y1: int, x2: int, y2: int) -> None:
        logger.debug("Preview bbox drawn: ({}, {}), ({}, {})", x1, y1, x2, y2)
        s_id = self._window.selected_s_id
        if s_id:
            logger.debug("Session {}: Calling Annotation Handler to handle drawn bbox...", s_id)
            self.handle_new_drawn_box(s_id, x1, y1, x2, y2)

    # NEW: Moved few slots from the controller to here.
    @Slot(str, int, int, int, int)
    def on_preview_bbox_edited(self, box_key: str, x1: int, y1: int, x2: int, y2: int) -> None:
        logger.debug("Preview bbox edited ({}, {}, {}, {}) key: {}", x1, y1, x2, y2, box_key)
        s_id = self._window.selected_s_id
        if s_id:
            logger.debug("Session {}: Calling Annotation Handler to handle edited bbox...", s_id)
            self.handle_existing_box_edit(s_id=s_id, box_key=box_key, new_coords=(x1, y1, x2, y2))

    @Slot(str)
    def on_preview_bbox_deleted(self, box_key: str) -> None:
        logger.debug("Preview detection deleted: {})", box_key)
        s_id = self._window.selected_s_id
        if s_id:
            tab = self._window.active_tab_index
            logger.debug("Deleting the detection from the active tab {}", tab)
            before_boxes = self._get_current_frame_boxes_snapshot() if self._can_record_mutation() else []
            before_selection = list(self._window.selected_frame_box_keys)

            self._app.delete_boxes_by_keys_and_tab_id_for_current_frame_by_session_id(s_id=s_id, box_keys=[box_key],
                                                                                      tab=tab)
            remaining_selection = [key for key in before_selection if key != box_key]
            self._apply_selection_keys(remaining_selection, record_history=True)
            if self._can_record_mutation():
                self._record_current_frame_mutation(before_boxes, before_selection)
            self._controller.render_frame_for_session_id(s_id)

    @Slot(str)
    def on_preview_bbox_selected(self, box_key: str) -> None:
        """Handle canvas-originated selection and sync to table and shared state."""
        logger.debug("Canvas bbox selected: {}", box_key)
        self._apply_selection_keys([box_key], record_history=True)

    @Slot(str, bool)
    def on_preview_bbox_selection_requested(self, box_key: str, additive: bool) -> None:
        """Apply a canvas click to the shared selection, toggling when Ctrl is held."""
        if not additive:
            self._apply_selection_keys([box_key], record_history=True)
            return

        selected_keys = self._window.selected_frame_box_keys
        if box_key in selected_keys:
            selected_keys = [key for key in selected_keys if key != box_key]
        else:
            selected_keys.append(box_key)
        self._apply_selection_keys(selected_keys, record_history=True)

    @Slot()
    def on_preview_bbox_selection_cleared(self) -> None:
        """Clear shared selection after a click on empty canvas space."""
        self._apply_selection_keys([], record_history=True)

    @Slot(list)
    def on_preview_bbox_marquee_selected(self, box_keys: list[str]) -> None:
        """Add marquee-contained boxes to the current shared selection."""
        selected_keys = list(self._window.selected_frame_box_keys)
        selected_key_set = set(selected_keys)
        selected_keys.extend(key for key in box_keys if key not in selected_key_set)
        self._apply_selection_keys(selected_keys, record_history=True)

    @Slot(list, int, int)
    def on_preview_bboxes_moved(self, box_keys: list[str], dx: int, dy: int) -> None:
        """Apply an overlay group-drag delta to every selected editable box."""
        s_id = self._window.selected_s_id
        if not s_id or not box_keys:
            return

        layer_name = (
            VideoDataLayer.B
            if self._window.active_tab_index == VideoDataLayerGroup.DETECTION
            else VideoDataLayer.D
        )
        logger.debug("Moving {} selected boxes by ({}, {}).", len(box_keys), dx, dy)
        logger.trace("Group move layer={} keys={}", layer_name, box_keys)
        try:
            before_boxes = self._get_current_frame_boxes_snapshot() if self._can_record_mutation() else []
            before_selection = list(self._window.selected_frame_box_keys)
            moved = self._app.change_current_layer_boxes_by_keys_and_dxdy(
                s_id=s_id,
                layer_name=layer_name,
                box_keys=box_keys,
                dx=dx,
                dy=dy,
            )
            logger.trace("Group move updated {} boxes.", moved)
            if moved:
                if self._can_record_mutation():
                    self._record_current_frame_mutation(before_boxes, before_selection)
                self._controller.render_frame_for_session_id(s_id)
        except Exception as exc:
            self._window.show_error("Move Failed", str(exc))

    @Slot(str, str)
    def on_preview_context_action(self, action: str, box_key: str) -> None:
        logger.debug("Preview detection context action: {}, {}", action, box_key)
        s_id: SessionId = self._window.selected_s_id
        if not s_id:
            return

        should_render = False

        if action == AnnotationContextActions.NO_OP.value:
            logger.info("Preview context action is not implemented yet.")
            self._window.set_status_text("Action not implemented yet.")
            return

        selected_keys = self._get_effective_selection_keys(box_key or None)
        if selected_keys:
            self._apply_selection_keys(selected_keys, record_history=False)
        elif box_key:
            selected_keys = [box_key]
            self._apply_selection_keys(selected_keys, record_history=False)

        if action == AnnotationContextActions.SELECT_ALL.value:
            self._apply_selection_keys(
                self._window.bottom_panel.get_all_box_keys_from_active_tab(),
                record_history=True,
            )
            return
        if action == AnnotationContextActions.SELECT_NONE.value:
            self._apply_selection_keys([], record_history=True)
            return
        if action == AnnotationContextActions.SELECT_INVERSE.value:
            all_keys = self._window.bottom_panel.get_all_box_keys_from_active_tab()
            current_keys = set(self._window.selected_frame_box_keys)
            inverted = [key for key in all_keys if key not in current_keys]
            self._apply_selection_keys(inverted, record_history=True)
            return

        # Route the context menu actions directly to the existing backend logic!
        if action == AnnotationContextActions.COPY.value:
            logger.trace("Copying selected boxes from context menu: {}", selected_keys)
            self._copy_selected_boxes_to_clipboard()
            return
        if action == AnnotationContextActions.PASTE.value:
            logger.trace("Pasting clipboard boxes from context menu.")
            self._paste_clipboard_to_current_frame()
            return
        if action == AnnotationContextActions.COPY_CURRENT.value:
            logger.trace("Duplicating selected boxes on current frame: {}", selected_keys)
            self._duplicate_selected_boxes_to_current_frame(selected_keys)
            return
        if action == AnnotationContextActions.ADD_BBOX_HERE.value:
            logger.debug("Switching preview to add mode from context menu.")
            self._window.transport_panel.add_mode_btn.setChecked(True)
            self._window.preview_container.set_tool_mode(ToolMode.ADD)
            self._window.set_status_text("Add mode enabled. Click and drag to place a new box.")
            return
        if action == AnnotationContextActions.COPY_NEXT.value:
            self.copy_to_direction(Direction.NEXT, selected_keys)
            return
        elif action == AnnotationContextActions.COPY_PREV.value:
            self.copy_to_direction(Direction.PREV, selected_keys)
            return
        elif action == AnnotationContextActions.DELETE_ALL_BBOXES.value:
            all_keys = self._window.bottom_panel.get_all_box_keys_from_active_tab()
            self._apply_selection_keys(all_keys, record_history=False)
            self.on_delete_selected()
            return
        elif action == AnnotationContextActions.DELETE.value:
            self._window.bbox_selection_state.set_selection(selected_keys)
            self.on_delete_selected()
            return
        elif action == AnnotationContextActions.DELETE_NEXT.value:
            if not selected_keys:
                return
            for key in selected_keys:
                box = self._app.get_layer_box_by_key(s_id, VideoDataLayer.D, key)
                if box is None:
                    continue
                self._app.delete_tracks_by_id_and_direction(s_id, box.id, Direction.NEXT)
            should_render = True
        elif action == AnnotationContextActions.DELETE_PREV.value:
            if not selected_keys:
                return
            for key in selected_keys:
                box = self._app.get_layer_box_by_key(s_id, VideoDataLayer.D, key)
                if box is None:
                    continue
                self._app.delete_tracks_by_id_and_direction(s_id, box.id, Direction.PREV)
            should_render = True
        elif action == AnnotationContextActions.RELABEL.value:
            self._window.bbox_selection_state.set_selection(selected_keys)
            self.on_relabel_selected()
            return
        elif action == AnnotationContextActions.RESET_FRAME.value:
            if self._window.active_tab_index == VideoDataLayerGroup.TRACKING:
                self.on_reset_tracker_frame()
            else:
                self.on_reset_frame()
            return
        elif action == AnnotationContextActions.RESET_ALL.value:
            if self._window.active_tab_index == VideoDataLayerGroup.TRACKING:
                self.on_reset_all_trackers()
            else:
                self.on_reset_all()
            return
        else:
            logger.info("Preview context action '{}' is not implemented yet.", action)
            self._window.set_status_text("Action not implemented yet.")
            return

        if should_render:
            self._controller.render_frame_for_session_id(s_id)

    def _delete_occurrences(self, direction: Direction, keys: list[str] | None = None) -> None:
        s_id = self._window.selected_s_id
        keys = self._window.selected_frame_box_keys if keys is None else keys
        if not s_id or not keys:
            return

        tab = self._window.active_tab_index
        if tab != 1:
            self._window.show_error(
                "Operation Invalid",
                "This action is only available in the Tracking tab.",
            )
            return

        try:
            # box_key format is "track:track-uid" or "manual:manual-id", we need the raw box_id
            for key in keys:
                box = self._app.get_layer_box_by_key(s_id, VideoDataLayer.D, key)
                if box:
                    self._app.delete_tracks_by_id_and_direction(s_id, box.id, direction)
            self._controller.render_frame_for_session_id(s_id)
        except Exception as exc:
            self._window.show_error("Delete Occurrences Failed", str(exc))

    def copy_to_direction(self, direction: Direction, keys: list[str] | None = None) -> None:
        s_id = self._window.selected_s_id
        keys = self._window.selected_frame_box_keys if keys is None else keys
        if not s_id or not keys:
            return

        tab = self._window.active_tab_index
        try:
            current_frame_index = self._app.get_session_by_id(s_id).state.playback.current_frame_index
            target_frame_index = current_frame_index + (1 if direction == Direction.NEXT else -1)
            if target_frame_index < 0:
                return
            before_boxes = self._get_current_frame_boxes_snapshot(target_frame_index)
            before_selection = list(keys)
            if tab == VideoDataLayerGroup.DETECTION:
                self._app.copy_boxes_to_adjacent_frame_by_direction(s_id, VideoDataLayer.B, keys, direction)
            elif tab == VideoDataLayerGroup.TRACKING:
                self._app.copy_boxes_to_adjacent_frame_by_direction(s_id, VideoDataLayer.D, keys, direction)
            else:
                raise ValueError(f"Unsupported tab: {tab}")

            self._record_current_frame_mutation(before_boxes, before_selection, target_frame_index)
            self._controller.render_frame_for_session_id(s_id)
        except Exception as exc:
            self._window.show_error("Duplicate Failed", str(exc))

    def _get_nudge_delta(self, key: int) -> int:
        now = time.monotonic()
        if key != self._last_move_key or (now - self._last_move_ts) > 0.35:
            self._move_repeat_count = 0

        self._move_repeat_count += 1
        self._last_move_key = key
        self._last_move_ts = now

        if self._move_repeat_count <= 4:
            return 1
        if self._move_repeat_count <= 8:
            return 2
        if self._move_repeat_count <= 12:
            return 4
        return 8
