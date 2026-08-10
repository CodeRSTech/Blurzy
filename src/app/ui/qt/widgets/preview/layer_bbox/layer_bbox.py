"""Qt facade for interactive bbox overlay behavior.

Design notes for maintainers:
- This class intentionally keeps Qt event handlers and signal emission.
- Heavy logic is delegated to concern modules under the same package.
- ``context_action_triggered`` emits ``str`` payloads by design for Qt interoperability.
- Placeholder selection menu actions are intentionally routed to a no-op action until
  full multi-selection behavior is implemented.
"""

# app/ui/qt/preview/layer_bbox.py
from __future__ import annotations

from typing import final, override, TYPE_CHECKING

from PySide6.QtCore import Qt, Signal, QSize, QPoint, QRect
from PySide6.QtGui import (
    QPainter,
    QCursor,
    QPaintEvent,
    QMouseEvent,
    QContextMenuEvent,
    QWheelEvent,
    QAction,
)
from PySide6.QtWidgets import QWidget, QMenu

from app.shared.logging_cfg import get_logger
from app.ui.view_state.preview.bbox_drag import DragMode, CORNER_CURSOR
from app.ui.view_state.preview.bbox_state import BBoxState
from app.ui.qt.widgets.preview.layer_bbox.constants import (
    _MIN_BBOX_PX,
)
from app.ui.qt.widgets.preview.layer_bbox.geometry import (
    find_bbox_at_pos,
    image_rect_to_widget_space,
    widget_rect_to_image_space,
)
from app.ui.qt.widgets.preview.layer_bbox.interaction import (
    begin_add_drag,
    finalize_release,
    stop_panning,
    try_begin_existing_edit_drag,
    try_start_panning,
    try_select_bbox_for_edit,
    update_panning,
    update_drag_rect,
)
from app.ui.qt.widgets.preview.layer_bbox.menu import (
    build_hit_action_map,
    build_no_hit_action_map,
    resolve_selected_action,
)
from app.ui.qt.widgets.preview.layer_bbox.rendering import draw_active_bbox
from app.ui.qt.widgets.preview.layer_bbox.helpers import (
    apply_clamped_drag_deltas,
    clamp_point_to_rect,
    clamp_rect_to_pixmap,
    get_drag_mode_for_rect_at_pos,
)
from app.ui.view_state.preview_state import ToolMode

logger = get_logger("UI->Preview->Bbox Layer")

if TYPE_CHECKING:
    from app.domain.base.dtypes import BBoxXYXYTuple


# --- Constants ---


@final
class AnnotationOverlayWidget(QWidget):
    """
    Handles interactive drawing, hit-testing, tool modes, and the context menu.
    Sits completely transparently over the video display.

    TODO:
     The AnnotationOverlayWidget is likely handling
     both Qt Event processing (mouse press, mouse move) AND
     Coordinate Algebra (translating physical screen pixels to video-relative ratios,
     handling zoom offsets, aspect ratio letterboxing calculations).

    Current split:
     - Event-time state transition helpers live in ``interaction.py``.
     - Context menu assembly/mapping lives in ``menu.py``.
     - Coordinate conversion and bbox lookup live in ``geometry.py``.
     - Paint primitives live in ``rendering.py``.
    """

    # --- Signals ---
    bbox_drawn = Signal(int, int, int, int)  # x1, y1, x2, y2
    bbox_edited = Signal(str, int, int, int, int)  # item_key, x1, y1, x2, y2
    bbox_deleted = Signal(str)  # item_key
    context_action_triggered = Signal(str, str)  # action_name, item_key

    # NEW: Viewport Signals
    zoom_requested = Signal(float, int, int)  # zoom_delta, mouse_x, mouse_y
    pan_requested = Signal(int, int)  # dx, dy

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the detection overlay widget with mouse tracking and state management."""
        super().__init__(parent)
        self.setMouseTracking(True)
        # Keeps background transparent so the video shows through
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)

        self._pixmap_rect: QRect = QRect()
        self._image_size: QSize | None = None
        self._state = BBoxState()

        self._tool_mode: ToolMode = ToolMode.EDIT
        self._active_bboxes: dict[str, BBoxXYXYTuple] = {}
        self._editing_bbox_id: str | None = None
        self._tracker_actions_enabled: bool = False

        # NEW: Pan state
        self._is_panning = False
        self._last_pan_pos = QPoint()

    # --- Public API for App ---

    def cancel_edit(self) -> None:
        """Reset the editing state and cursor to prepare for a new interaction."""
        self._editing_bbox_id = None
        self._state = BBoxState()
        if self._tool_mode != ToolMode.ADD:
            self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
        self.update()

    def set_pixmap_rect(self, rect: QRect) -> None:
        """Called by the App when the underlying video resizes."""
        self._pixmap_rect = rect
        self.update()

    def set_image_size(self, size: QSize) -> None:
        """Called by the App to supply raw video dimensions for coordinate math."""
        self._image_size = size

    def set_active_bboxes(self, bboxes: dict[str, BBoxXYXYTuple]) -> None:
        """Update the set of active bounding boxes and cancel editing if the current bbox was removed."""
        self._active_bboxes = bboxes
        if self._editing_bbox_id and self._editing_bbox_id not in bboxes:
            self.cancel_edit()
        self.update()

    def set_tool_mode(self, mode: ToolMode) -> None:
        """Change the active tool mode and update the cursor accordingly."""
        self._tool_mode = mode
        self.cancel_edit()

        if mode == ToolMode.ADD:
            self.setCursor(QCursor(Qt.CursorShape.CrossCursor))
        else:
            self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))

    def set_tracker_actions_enabled(self, enabled: bool) -> None:
        """Enables tracker-specific context menu options like 'Delete Next Occurrences'."""
        self._tracker_actions_enabled = enabled

    # --- Mouse Event Handlers ---

    @override
    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        """Constructs and routes right-click actions dynamically."""
        if self._tool_mode != ToolMode.EDIT:
            return

        hit_box_id = self._get_bbox_id_at_pos(event.pos())
        if not hit_box_id:
            menu = QMenu(self)
            action_names = build_no_hit_action_map(menu)
            chosen = menu.exec(event.globalPos())
            self._emit_context_menu_action(chosen, action_names, hit_box_id)
            return

        menu = QMenu(self)
        action_names = build_hit_action_map(menu, self._tracker_actions_enabled)

        chosen = menu.exec(event.globalPos())
        self._emit_context_menu_action(chosen, action_names, hit_box_id)

    def _emit_context_menu_action(self, chosen: QAction | None, action_names: dict[QAction, str], hit_box_id: str | None) -> None:
        """Emit the selected context action as a ``str`` payload for downstream handlers."""
        action_name = resolve_selected_action(chosen, action_names)
        if action_name is None:
            return
        self.context_action_triggered.emit(action_name, hit_box_id or "")

    @override
    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Handle mouse movement and delegate drag/pan calculations to ``interaction.py``."""
        pos = event.position().toPoint()

        # 2. Process Panning continuously while mouse moves!
        is_panning, next_pan_pos, delta = update_panning(self._is_panning, self._last_pan_pos, pos)
        if is_panning and delta is not None:
            self._last_pan_pos = next_pan_pos
            self.pan_requested.emit(delta.x(), delta.y())
            return

        state = self._state

        if state.drag_mode == DragMode.NONE:
            if self._tool_mode == ToolMode.EDIT and state.has_valid_rect:
                hit = self._hit_test_handle(pos)
                if hit != DragMode.NONE:
                    self.setCursor(QCursor(CORNER_CURSOR[hit]))
                elif state.rect.contains(pos):
                    self.setCursor(QCursor(Qt.CursorShape.SizeAllCursor))
                else:
                    self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
            return

        if update_drag_rect(state, pos, self._clamp, self._clamp_rect, self._apply_handle_drag):
            self.update()

    @override
    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Handle mouse press to start drawing, panning, or selecting bounding boxes."""
        # 1. Catch Alt + Left Click to START panning
        pos = event.position().toPoint()
        panning_started, pan_origin = try_start_panning(
            is_panning=self._is_panning,
            button_is_left=event.button() == Qt.MouseButton.LeftButton,
            is_ctrl_pressed=event.modifiers() == Qt.KeyboardModifier.AltModifier,
            pos=pos,
        )
        if panning_started and pan_origin is not None:
            self._is_panning = True
            self._last_pan_pos = pan_origin
            self.setCursor(QCursor(Qt.CursorShape.ClosedHandCursor))
            return

        if event.button() != Qt.MouseButton.LeftButton:
            return

        clamped = self._clamp(pos)
        state = self._state

        # MODE: ADD
        if self._tool_mode == ToolMode.ADD:
            begin_add_drag(state, clamped)
            self.update()
            return

        # MODE: DELETE
        # FIXME: This mode does NOT work
        if self._tool_mode == ToolMode.DELETE:
            bbox_id = self._get_bbox_id_at_pos(pos)
            if bbox_id:
                self.bbox_deleted.emit(bbox_id)
            return

        # MODE: EDIT
        if self._tool_mode == ToolMode.EDIT:
            # 1. Interact with currently active rect handles/move
            if try_begin_existing_edit_drag(state, pos, self._hit_test_handle):
                return

            # 2. Try to grab a new detection
            bbox_id = try_select_bbox_for_edit(state, pos, self._get_bbox_at_pos)
            if bbox_id:
                self._editing_bbox_id = bbox_id
                self.update()
                return

            # 3. Clicked empty space
            self.cancel_edit()

    @override
    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """Finalize draw/edit outcomes and emit overlay signals when release completes."""
        # 3. Stop panning safely
        if stop_panning(self._is_panning):
            self._is_panning = False
            self.cancel_edit()  # Resets cursor back to Arrow
            return

        if event.button() != Qt.MouseButton.LeftButton:
            return

        state = self._state
        logger.debug("Current state: {}", state)
        outcome, payload = finalize_release(
            state=state,
            editing_bbox_id=self._editing_bbox_id,
            min_bbox_px=_MIN_BBOX_PX,
            widget_rect_to_image_space=self._widget_rect_to_image_space,
        )
        if outcome == "cancel":
            self.cancel_edit()
            return
        if outcome == "draw" and payload is not None:
            x1, y1, x2, y2 = payload
            self.cancel_edit()
            self.bbox_drawn.emit(x1, y1, x2, y2)
            return
        if outcome == "edit" and payload is not None:
            item_key, x1, y1, x2, y2 = payload
            self.bbox_edited.emit(item_key, x1, y1, x2, y2)

        state.drag_mode = DragMode.NONE

    # --- Context Menu ---

    @override
    def paintEvent(self, event: QPaintEvent) -> None:
        """Render the current bounding detection with selection handles and center point."""
        if not self._state.has_valid_rect:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        draw_active_bbox(painter, self._state.rect)

        painter.end()

    # --- Rendering ---

    @override
    def wheelEvent(self, event: QWheelEvent) -> None:
        """Captures scroll wheel to broadcast zoom requests."""
        # NEW: Require Ctrl modifier for zoom
        if event.modifiers() != Qt.KeyboardModifier.ControlModifier:
            return

        delta = event.angleDelta().y()
        if delta == 0:
            return

        pos = event.position().toPoint()
        self.zoom_requested.emit(delta, pos.x(), pos.y())

    # --- Geometry & Hit Test Helpers ---

    def _apply_handle_drag(self, base: QRect, mode: DragMode, delta: QPoint) -> QRect:
        """Apply clamped drag deltas to the specified bbox corner or edge."""
        x1, y1, x2, y2 = base.left(), base.top(), base.right(), base.bottom()
        dx, dy = delta.x(), delta.y()
        pr = self._pixmap_rect

        return apply_clamped_drag_deltas(mode, pr, x1, x2, y1, y2, dx, dy)

    def _clamp(self, point: QPoint) -> QPoint:
        """Clamp a point to the pixmap rectangle bounds."""
        r = self._pixmap_rect
        return clamp_point_to_rect(point, r)

    def _clamp_rect(self, rect: QRect) -> QRect:
        """Clamp a rectangle to the pixmap bounds by translating it without resizing."""
        return clamp_rect_to_pixmap(rect.normalized(), self._pixmap_rect)

    def _get_bbox_at_pos(self, pos: QPoint) -> tuple[str | None, QRect | None]:
        """Finds the closest bbox hit by the given point."""
        return find_bbox_at_pos(
            active_bboxes=self._active_bboxes,
            pos=pos,
            pixmap_rect=self._pixmap_rect,
            image_size=self._image_size,
        )

    def _get_bbox_id_at_pos(self, pos: QPoint) -> str | None:
        """Return the ID of the bbox at the given position using proximity testing."""
        box_id, _ = self._get_bbox_at_pos(pos)
        return box_id

    def _hit_test_handle(self, pos: QPoint) -> DragMode:
        """Detect which bbox handle or edge is closest to the given position."""
        rect = self._state.rect
        return get_drag_mode_for_rect_at_pos(rect, pos)

    def _image_rect_to_widget_space(self, x1: int, y1: int, x2: int, y2: int) -> QRect:
        """Convert image space coordinates to widget space rectangle with scaling applied."""
        return image_rect_to_widget_space(x1, y1, x2, y2, self._pixmap_rect, self._image_size)

    def _widget_rect_to_image_space(self, rect: QRect) -> BBoxXYXYTuple:
        """Convert widget space rectangle to image space coordinates with scaling and bounds applied."""
        return widget_rect_to_image_space(rect, self._pixmap_rect, self._image_size)
