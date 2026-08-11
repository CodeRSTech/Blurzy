"""Context menu builders for ``AnnotationOverlayWidget``.

Why this module exists:
- Keeps UI label text near its emitted backend action string.
- Centralizes QAction->action-name mapping to avoid long ``if/elif`` chains.
- Preserves placeholder selection entries as explicit no-op actions.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.domain.detection import AnnotationContextActions

if TYPE_CHECKING:
    from PySide6.QtGui import QAction
    from PySide6.QtWidgets import QMenu
def build_no_hit_action_map(menu: QMenu) -> dict[QAction, str]:
    """Build context menu actions used when right-clicking empty canvas space."""
    action_select_all = menu.addAction("Select All")
    action_select_none = menu.addAction("Deselect All")
    action_select_inverse = menu.addAction("Invert Selection")
    action_relabel = menu.addAction("Relabel Selected")
    menu.addSeparator()
    action_create_bbox_here = menu.addAction("Add Bounding Box Here")
    action_remove_all_boxes = menu.addAction("Remove All Bounding Boxes")
    menu.addSeparator()
    action_reset_current_frame = menu.addAction("Reset Current Frame")
    action_reset_all_frames = menu.addAction("Reset All Frames")

    return {
        action_select_all: AnnotationContextActions.SELECT_ALL.value,
        action_select_none: AnnotationContextActions.SELECT_NONE.value,
        action_select_inverse: AnnotationContextActions.SELECT_INVERSE.value,
        action_relabel: AnnotationContextActions.RELABEL.value,
        action_create_bbox_here: AnnotationContextActions.ADD_BBOX_HERE.value,
        action_remove_all_boxes: AnnotationContextActions.DELETE_ALL_BBOXES.value,
        action_reset_current_frame: AnnotationContextActions.RESET_FRAME.value,
        action_reset_all_frames: AnnotationContextActions.RESET_ALL.value,
    }


def build_hit_action_map(menu: QMenu, tracker_actions_enabled: bool) -> dict[QAction, str]:
    """Build context menu actions used when right-clicking over an existing bbox."""
    action_select_all = menu.addAction("Select All")
    action_select_none = menu.addAction("Deselect All")
    action_select_inverse = menu.addAction("Invert Selection")
    action_relabel = menu.addAction("Relabel Selected")
    action_dup_next = menu.addAction("Duplicate to Next Frame")
    action_dup_prev = menu.addAction("Duplicate to Previous Frame")
    action_dup_current = menu.addAction("Duplicate to Current Frame")
    menu.addSeparator()
    action_copy = menu.addAction("Copy")
    action_paste = menu.addAction("Paste")
    menu.addSeparator()
    action_delete = menu.addAction("Delete")

    action_names: dict[QAction, str] = {
        action_select_all: AnnotationContextActions.SELECT_ALL.value,
        action_select_none: AnnotationContextActions.SELECT_NONE.value,
        action_select_inverse: AnnotationContextActions.SELECT_INVERSE.value,
        action_relabel: AnnotationContextActions.RELABEL.value,
        action_dup_next: AnnotationContextActions.COPY_NEXT.value,
        action_dup_prev: AnnotationContextActions.COPY_PREV.value,
        action_dup_current: AnnotationContextActions.COPY_CURRENT.value,
        action_copy: AnnotationContextActions.COPY.value,
        action_paste: AnnotationContextActions.PASTE.value,
        action_delete: AnnotationContextActions.DELETE.value,
    }

    if tracker_actions_enabled:
        menu.addSeparator()
        action_del_next = menu.addAction("Delete Next Occurrences")
        action_del_prev = menu.addAction("Delete Previous Occurrences")
        action_names[action_del_next] = AnnotationContextActions.DELETE_NEXT.value
        action_names[action_del_prev] = AnnotationContextActions.DELETE_PREV.value

    return action_names


def resolve_selected_action(chosen: QAction | None, action_names: dict[QAction, str]) -> str | None:
    """Resolve the selected QAction into a context action string payload."""
    if chosen is None:
        return None
    return action_names.get(chosen)


