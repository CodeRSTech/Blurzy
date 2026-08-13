"""Right-click context menu actions for detection editing (add, copy, delete, select, reset)."""

from __future__ import annotations

from enum import Enum


class AnnotationContextActions(str, Enum):
    """
    Right-click context menu and keyboard actions for detection editing.

    Note:
        Includes single-detection actions such as add, edit, and delete; multi-detection
        actions such as copy, directional delete, and delete-all; selection
        actions such as select all, none, and inverse; and reset actions for
        reverting Layer B or Layer D view_state. Clipboard operations are also
        included. ``AnnotationHandler`` routes each action to the appropriate
        service method.
    """
    ADD_BBOX_HERE = "add_bbox_here"
    COPY = "copy"
    COPY_CURRENT = "copy_current"
    COPY_NEXT = "copy_next"
    COPY_PREV = "copy_prev"
    DELETE = "delete"
    DELETE_ALL_BBOXES = "delete_all_bboxes"
    DELETE_NEXT = "delete_next"
    DELETE_PREV = "delete_prev"
    EDIT = "edit"
    NO_OP = "noop"
    PASTE = "paste"
    RESET_FRAME = "reset_current_frame"
    RESET_ALL = "reset_all_frames"
    RESET_TRACKER_FRAME = "reset_tracker_frame"
    RESET_ALL_TRACKERS = "reset_all_trackers"
    RELABEL = "relabel"
    SELECT_ALL = "select_all"
    SELECT_NONE = "select_none"
    SELECT_INVERSE = "select_inverse"
