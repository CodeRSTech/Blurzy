"""State-transition helpers for bbox interaction flows.

These functions are intentionally side-effect-light and operate on ``BBoxState`` so
the widget facade can remain thin and easier to test.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from PySide6.QtCore import QPoint, QRect

from app.ui.qt.widgets.preview.layer_bbox.bbox_drag import DragMode
from app.ui.qt.widgets.preview.layer_bbox.bbox_mouse_release import MouseReleaseOutcome

if TYPE_CHECKING:
    from app.ui.qt.widgets.preview.layer_bbox.bbox_state import BBoxState


BBoxLookupFn = Callable[[QPoint], tuple[str | None, QRect | None]]
HitTestHandleFn = Callable[[QPoint], DragMode]
ClampPointFn = Callable[[QPoint], QPoint]
ClampRectFn = Callable[[QRect], QRect]
ApplyHandleDragFn = Callable[[QRect, DragMode, QPoint], QRect]


def begin_add_drag(state: BBoxState, clamped_pos: QPoint) -> None:
    """Initialize state for drawing a new bbox."""
    state.rect = QRect(clamped_pos, clamped_pos).normalized()
    state.drag_mode = DragMode.DRAW
    state.drag_origin = clamped_pos


def try_start_panning(
    is_panning: bool,
    button_is_left: bool,
    is_ctrl_pressed: bool,
    pos: QPoint,
) -> tuple[bool, QPoint | None]:
    """Start panning when Ctrl+Left is pressed."""
    if not is_panning and button_is_left and is_ctrl_pressed:
        return True, pos
    return False, None


def update_panning(
    is_panning: bool,
    last_pan_pos: QPoint,
    pos: QPoint,
) -> tuple[bool, QPoint, QPoint | None]:
    """Update panning delta while dragging the viewport."""
    if not is_panning:
        return False, last_pan_pos, None

    delta = pos - last_pan_pos
    return True, pos, delta


def stop_panning(is_panning: bool) -> bool:
    """Return True when panning was active and should be cancelled on release."""
    return is_panning


def try_begin_existing_edit_drag(
    state: BBoxState,
    pos: QPoint,
    hit_test_handle: HitTestHandleFn,
) -> bool:
    """Start handle-resize or move drag when the active bbox is already selected."""
    if not state.has_valid_rect:
        return False

    drag_mode = hit_test_handle(pos)
    if drag_mode != DragMode.NONE:
        state.drag_mode = drag_mode
        state.drag_origin = pos
        state.rect_at_drag_start = QRect(state.rect)
        return True

    if state.rect.contains(pos):
        state.drag_mode = DragMode.MOVE
        state.drag_origin = pos
        state.rect_at_drag_start = QRect(state.rect)
        return True

    return False


def try_select_bbox_for_edit(
    state: BBoxState,
    pos: QPoint,
    get_bbox_at_pos: BBoxLookupFn,
) -> str | None:
    """Pick a bbox under cursor and initialize drag-ready state for edit mode."""
    bbox_id, bbox_rect = get_bbox_at_pos(pos)
    if not bbox_id or not bbox_rect:
        return None

    state.rect = bbox_rect
    state.drag_mode = DragMode.MOVE if bbox_rect.contains(pos) else DragMode.NONE
    state.drag_origin = pos
    state.rect_at_drag_start = QRect(state.rect)
    return bbox_id


def update_drag_rect(
    state: BBoxState,
    pos: QPoint,
    clamp_point: ClampPointFn,
    clamp_rect: ClampRectFn,
    apply_handle_drag: ApplyHandleDragFn,
) -> bool:
    """Apply draw/move/resize updates for the current drag state."""
    if state.drag_mode == DragMode.NONE:
        return False

    clamped = clamp_point(pos)
    if state.drag_mode == DragMode.DRAW:
        state.rect = QRect(state.drag_origin, clamped).normalized()
    elif state.drag_mode == DragMode.MOVE:
        delta = pos - state.drag_origin
        moved = state.rect_at_drag_start.translated(delta)
        state.rect = clamp_rect(moved.normalized())
    else:
        state.rect = apply_handle_drag(
            state.rect_at_drag_start,
            state.drag_mode,
            pos - state.drag_origin,
        )

    return True


def finalize_release(
    state: BBoxState,
    editing_bbox_id: str | None,
    min_bbox_px: int,
    widget_rect_to_image_space: Callable[[QRect], tuple[int, int, int, int]],
) -> tuple[MouseReleaseOutcome, tuple[str, int, int, int, int] | tuple[int, int, int, int] | None]:
    """Finalize mouse release into ``cancel``/``draw``/``edit``/``none`` outcomes."""
    drag_mode = state.drag_mode
    rect = state.rect

    if drag_mode == DragMode.DRAW and (rect.width() < min_bbox_px or rect.height() < min_bbox_px):
        return MouseReleaseOutcome.CANCEL, None

    if drag_mode == DragMode.DRAW:
        x1, y1, x2, y2 = widget_rect_to_image_space(rect)
        return MouseReleaseOutcome.DRAW, (x1, y1, x2, y2)

    if drag_mode != DragMode.NONE and editing_bbox_id is not None:
        x1, y1, x2, y2 = widget_rect_to_image_space(rect)
        return MouseReleaseOutcome.EDIT, (editing_bbox_id, x1, y1, x2, y2)

    return MouseReleaseOutcome.NONE, None
