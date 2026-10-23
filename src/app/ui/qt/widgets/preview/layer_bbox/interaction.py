"""
State-transition helpers for bbox interaction flows.

These functions are intentionally side-effect-light and operate on `BBoxState` so
the widget facade can remain thin and easier to test.

See Also:
    - [`BBoxState`][app.ui.qt.widgets.preview.layer_bbox.bbox_state.BBoxState] — holds gesture and selection state
    - [`MouseReleaseOutcome`][app.ui.qt.widgets.preview.layer_bbox.bbox_mouse_release.MouseReleaseOutcome] — describes release handling results

Layer: Presentation.
Context: Contains concrete Qt presentation components and supporting utilities.
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
    """
    Initialize state for drawing a new bbox.

    Args:
        state: Mutable drag state to initialize.
        clamped_pos: Pointer position clamped to the drawable image area.

    Side Effects:
        Sets the initial zero-size rectangle, draw mode, and drag origin on `state`.
    """
    state.rect = QRect(clamped_pos, clamped_pos).normalized()
    state.drag_mode = DragMode.DRAW
    state.drag_origin = clamped_pos


def try_start_panning(
    is_panning: bool,
    button_is_left: bool,
    is_ctrl_pressed: bool,
    pos: QPoint,
) -> tuple[bool, QPoint | None]:
    """
    Start panning when Ctrl+Left is pressed.

    Args:
        is_panning: Whether a pan gesture is already active.
        button_is_left: Whether the pressed mouse button is the left button.
        is_ctrl_pressed: Whether Ctrl is held.
        pos: Pointer position at the start of the gesture.

    Returns:
        `(True, pos)` when panning should start; otherwise `(False, None)`.
    """
    if not is_panning and button_is_left and is_ctrl_pressed:
        return True, pos
    return False, None


def update_panning(
    is_panning: bool,
    last_pan_pos: QPoint,
    pos: QPoint,
) -> tuple[bool, QPoint, QPoint | None]:
    """
    Update panning delta while dragging the viewport.

    Args:
        is_panning: Whether a pan gesture is active.
        last_pan_pos: Pointer position from the previous pan update.
        pos: Current pointer position.

    Returns:
        `(True, pos, delta)` while panning, or `(False, last_pan_pos, None)` otherwise.
    """
    if not is_panning:
        return False, last_pan_pos, None

    delta = pos - last_pan_pos
    return True, pos, delta


def stop_panning(is_panning: bool) -> bool:
    """
    Return True when panning was active and should be cancelled on release.

    Args:
        is_panning: Whether panning was active before the mouse release.

    Returns:
        The input state, used by the caller to decide whether to cancel panning.
    """
    return is_panning


def try_begin_existing_edit_drag(
    state: BBoxState,
    pos: QPoint,
    hit_test_handle: HitTestHandleFn,
) -> bool:
    """
    Start handle-resize or move drag when the active bbox is already selected.

    Args:
        state: Current bbox rectangle and drag state.
        pos: Pointer position used to identify a handle or interior hit.
        hit_test_handle: Callback returning the handle drag mode at `pos`.

    Returns:
        `True` if a resize or move drag started; otherwise `False`.

    Side Effects:
        On a hit, stores the drag mode, origin, and starting rectangle in `state`.
    """
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
    """
    Pick a bbox under cursor and initialize drag-ready state for edit mode.

    Args:
        state: Mutable bbox drag state to initialize.
        pos: Pointer position used to select a box.
        get_bbox_at_pos: Lookup callback returning a box key and widget rectangle.

    Returns:
        Selected box key, or `None` when no box is found.

    Side Effects:
        On a hit, stores the selected rectangle and drag origin in `state`.
    """
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
    """
    Apply draw/move/resize updates for the current drag state.

    Args:
        state: Mutable rectangle and drag mode being updated.
        pos: Current pointer position.
        clamp_point: Callback constraining the pointer to the drawable image area.
        clamp_rect: Callback constraining a moved rectangle to the image bounds.
        apply_handle_drag: Callback resizing the starting rectangle for the active handle.

    Returns:
        `True` if a draw, move, or resize operation updated the rectangle.

    Side Effects:
        Updates `state.rect` when `state.drag_mode` is not `NONE`.
    """
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
    """
    Finalize mouse release into `cancel`/`draw`/`edit`/`none` outcomes.

    Args:
        state: Current rectangle and drag mode to finalize.
        editing_bbox_id: Key of the box being edited, or `None` for a new box.
        min_bbox_px: Minimum widget-space width and height accepted for a new box.
        widget_rect_to_image_space: Callback converting the final rectangle to image coordinates.

    Returns:
        Outcome and payload: a coordinate tuple for a new box, a key plus coordinates
        for an edit, or `None` when the gesture is cancelled or has no action.
    """
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
