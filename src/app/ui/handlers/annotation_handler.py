"""Annotation creation and editing handler for bounding detection management."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, final, override

from PySide6.QtCore import Qt, Slot, QObject
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QDialog

from app.domain.detection import AnnotationContextActions
from app.domain.video.direction import Direction
from app.domain.video.layer import VideoDataLayer
from app.domain.video.layer_group import VideoDataLayerGroup
from app.shared.logging_cfg import get_logger
from app.ui.qt.dialogs import LabelDialog

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
            (preview_container.context_action_triggered, self.on_preview_context_action),
            # Bottom panel action row buttons
            (bottom_panel.edit_item_btn.clicked, self.on_edit_selected),
            (bottom_panel.delete_item_btn.clicked, self.on_delete_selected),
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
        Handles the addition of a new drawn detection detection.
    
        This function is triggered when a new detection detection is drawn on the interface. It prompts the user
        to provide a label for the detection via a dialog. If a valid label is provided and accepted, the function
        attempts to add the detection detection, updates the user interface, and triggers the provided rendering
        function to refresh the detection visually.
    
        Args:
            s_id (SessionId): A unique identifier for the current session.
            x1 (int): The x-coordinate of the top-left corner of the detection.
            y1 (int): The y-coordinate of the top-left corner of the detection.
            x2 (int): The x-coordinate of the bottom-right corner of the detection.
            y2 (int): The y-coordinate of the bottom-right corner of the detection.
        """
        dialog = LabelDialog(self._window)
        if dialog.exec() == LabelDialog.DialogCode.Accepted and dialog.get_label():
            label = dialog.get_label()
            try:
                self._app.add_manual_detection_box_at_current_frame_index(s_id, label, (x1, y1, x2, y2))
                self._window.set_status_text("Annotation added.")
                self._controller.render_frame_for_session_id(s_id)
            except Exception as exc:
                self._window.show_error("Add Failed", str(exc))

        # Stay in Add mode so repeated detection creation keeps the toolbar view_state
        # and overlay behavior in sync.

    def handle_existing_box_edit(
            self,
            s_id: SessionId,
            item_key: str,
            new_coords: BBoxXYXYTuple | None = None,
    ) -> None:
        """Handles both visual drags (new_coords) and table 'Edit' clicks (dialog)."""
        tab = self._window.active_tab_index

        item = (
            self._app.get_layer_box_by_key(s_id, VideoDataLayer.D, item_key)
            if tab == VideoDataLayerGroup.TRACKING
            else self._app.get_layer_box_by_key(s_id, VideoDataLayer.B, item_key)
        )
        if item is None:
            return

        label, bbox_xyxy = item.label, item.bbox_xyxy

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
            self._app.update_box_in_layer_at_current_frame(
                s_id=s_id,
                layer_name=VideoDataLayer.B if tab == VideoDataLayerGroup.DETECTION else VideoDataLayer.D,
                item_key=item.key,
                label=label,
                bbox_xyxy=bbox_xyxy,
            )
            self._controller.render_frame_for_session_id(s_id)
        except Exception as exc:
            self._window.show_error("Edit Failed", str(exc))

    def handle_nudge_key(self, event: QKeyEvent) -> bool:
        if event.modifiers() != Qt.KeyboardModifier.NoModifier:
            return False

        key = event.key()
        if key not in (Qt.Key.Key_Up, Qt.Key.Key_Down, Qt.Key.Key_Left, Qt.Key.Key_Right):
            return False

        s_id = self._window.selected_s_id
        item_keys = self._window.selected_frame_box_keys
        if not s_id or not item_keys:
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
            if self._window.active_tab_index == VideoDataLayerGroup.DETECTION:
                moved = self._app.change_current_layer_boxes_by_keys_and_dxdy(s_id=s_id,
                                                                              layer_name=VideoDataLayer.B,
                                                                              item_keys=item_keys, dx=dx,
                                                                              dy=dy)
            else:  # self._window.active_tab_index == DataTab.TRACKING
                moved = self._app.change_current_layer_boxes_by_keys_and_dxdy(s_id=s_id,
                                                                              layer_name=VideoDataLayer.D,
                                                                              item_keys=item_keys, dx=dx,
                                                                              dy=dy)
            if moved > 0:
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
            # ================================================================
            # 1. DELETE BOXES FROM ACTIVE TAB
            # ================================================================
            self._app.delete_boxes_by_keys_and_tab_id_for_current_frame_by_session_id(
                s_id=s_id, keys=keys, tab=self._window.active_tab_index
            )

            # ================================================================
            # 2. RENDER FRAME WITH UPDATED BOXES
            # ================================================================
            self._controller.render_frame_for_session_id(s_id)
        except Exception as exc:
            self._window.show_error("Delete Failed", str(exc))

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
            self._app.add_manual_detection_box_at_current_frame_index(s_id, label, bbox_xyxy)
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
    def on_preview_bbox_edited(self, item_key: str, x1: int, y1: int, x2: int, y2: int) -> None:
        logger.debug("Preview bbox edited ({}, {}, {}, {}) key: {}", x1, y1, x2, y2, item_key)
        s_id = self._window.selected_s_id
        if s_id:
            logger.debug("Session {}: Calling Annotation Handler to handle edited bbox...", s_id)
            self.handle_existing_box_edit(s_id=s_id, item_key=item_key, new_coords=(x1, y1, x2, y2))

    @Slot(str)
    def on_preview_bbox_deleted(self, item_key: str) -> None:
        logger.debug("Preview detection deleted: {})", item_key)
        s_id = self._window.selected_s_id
        if s_id:
            tab = self._window.active_tab_index
            logger.debug("Deleting the detection from the active tab {}", tab)

            self._app.delete_boxes_by_keys_and_tab_id_for_current_frame_by_session_id(s_id=s_id, keys=[item_key],
                                                                                      tab=tab)
            self._controller.render_frame_for_session_id(s_id)

    @Slot(str, str)
    def on_preview_context_action(self, action: str, item_key: str) -> None:
        logger.debug("Preview detection context action: {}, {}", action, item_key)
        s_id: SessionId = self._window.selected_s_id
        if not s_id:
            return

        active_layer = VideoDataLayer.B if self._window.active_tab_index == VideoDataLayerGroup.DETECTION else VideoDataLayer.D
        should_render = False

        if action == AnnotationContextActions.NO_OP.value:
            logger.info("Preview context action is not implemented yet.")
            self._window.set_status_text("Action not implemented yet.")
            return

        # Route the context menu actions directly to the existing backend logic!
        if action == AnnotationContextActions.COPY_NEXT:
            self._app.copy_boxes_to_adjacent_frame_by_direction(
                s_id, active_layer, [item_key], Direction.NEXT
            )
            should_render = True
        elif action == AnnotationContextActions.COPY_PREV:
            self._app.copy_boxes_to_adjacent_frame_by_direction(
                s_id, active_layer, [item_key], Direction.PREV
            )
            should_render = True
        elif action == AnnotationContextActions.DELETE_NEXT:
            # Extract underlying item_id from item_key (e.g. "track:123" -> "123")
            item = self._app.get_layer_box_by_key(s_id, VideoDataLayer.D, item_key)
            if item is None:
                return
            self._app.delete_tracks_by_id_and_direction(s_id, item.id, Direction.NEXT)
            should_render = True
        elif action == AnnotationContextActions.DELETE_PREV:
            item = self._app.get_layer_box_by_key(s_id, VideoDataLayer.D, item_key)
            if item is None:
                return
            self._app.delete_tracks_by_id_and_direction(s_id, item.id, Direction.PREV)
            should_render = True
        else:
            logger.info("Preview context action '{}' is not implemented yet.", action)
            self._window.set_status_text("Action not implemented yet.")
            return

        if should_render:
            self._controller.render_frame_for_session_id(s_id)

    def _delete_occurrences(self, direction: Direction) -> None:
        s_id = self._window.selected_s_id
        keys = self._window.selected_frame_box_keys
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
            # item_key format is "track:track-uid" or "manual:manual-id", we need the raw item_id
            for key in keys:
                item = self._app.get_layer_box_by_key(s_id, VideoDataLayer.D, key)
                if item:
                    self._app.delete_tracks_by_id_and_direction(s_id, item.id, direction)
            self._controller.render_frame_for_session_id(s_id)
        except Exception as exc:
            self._window.show_error("Delete Occurrences Failed", str(exc))

    def copy_to_direction(self, direction: Direction) -> None:
        s_id = self._window.selected_s_id
        keys = self._window.selected_frame_box_keys
        if not s_id or not keys:
            return

        tab = self._window.active_tab_index
        try:
            if tab == VideoDataLayerGroup.DETECTION:
                self._app.copy_boxes_to_adjacent_frame_by_direction(s_id, VideoDataLayer.B, keys, direction)
            elif tab == VideoDataLayerGroup.TRACKING:
                self._app.copy_boxes_to_adjacent_frame_by_direction(s_id, VideoDataLayer.D, keys, direction)
            else:
                raise ValueError(f"Unsupported tab: {tab}")

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
