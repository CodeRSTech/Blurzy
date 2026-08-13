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

from PySide6.QtCore import Qt, Signal, QPoint, QRect
from PySide6.QtGui import QPainter, QCursor, QPen
from PySide6.QtWidgets import QWidget, QMenu

from app.shared.logging_cfg import get_logger
from app.ui.qt.widgets.preview.layer_bbox.bbox_drag import DragMode, CORNER_CURSOR
from app.ui.qt.widgets.preview.layer_bbox.bbox_mouse_release import MouseReleaseOutcome
from app.ui.qt.widgets.preview.layer_bbox.bbox_state import BBoxState
from app.ui.qt.widgets.preview.layer_bbox.constants import (
    _BOX_COLOR,
    _MIN_BBOX_PX,
)
from app.ui.qt.widgets.preview.layer_bbox.geometry import (
    find_bbox_keys_intersecting_rect,
    find_bbox_at_pos_with_transforms,
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
from app.ui.qt.widgets.preview.layer_bbox.rendering import draw_active_bbox, draw_selected_bbox
from app.ui.qt.widgets.preview.layer_bbox.helpers import (
    apply_clamped_drag_deltas,
    clamp_point_to_rect,
    clamp_rect_to_pixmap,
    get_drag_mode_for_rect_at_pos,
)
if TYPE_CHECKING:
    from PySide6.QtCore import QSize
    from PySide6.QtGui import QPaintEvent, QMouseEvent, QContextMenuEvent, QWheelEvent, QAction

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
    bbox_selected = Signal(str)  # item_key (new: canvas-driven selection)
    bbox_selection_requested = Signal(str, bool)  # item_key, additive toggle
    bbox_selection_cleared = Signal()
    bbox_marquee_selected = Signal(list)
    bboxes_moved = Signal(list, int, int)  # selected keys, image-space delta

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
        self._selected_bbox_keys: set[str] = set()
        self._group_drag_keys: list[str] = []
        self._marquee_origin: QPoint | None = None
        self._marquee_rect = QRect()

        # NEW: Pan state
        self._is_panning = False
        self._last_pan_pos = QPoint()

        # NEW: Zoom and pan transforms
        self._zoom: float = 1.0
        self._pan_x: float = 0.0
        self._pan_y: float = 0.0

    # --- Public API for App ---

    def cancel_edit(self) -> None:
        """Reset the editing state and cursor to prepare for a new interaction."""
        self._editing_bbox_id = None
        self._group_drag_keys = []
        self._state = BBoxState()
        self._marquee_origin = None
        self._marquee_rect = QRect()
        if self._tool_mode != ToolMode.ADD:
            self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
        self.update()

    def set_pixmap_rect(self, rect: QRect) -> None:
        """Called by the App when the underlying video resizes."""
        if self._state.has_valid_rect and self._image_size is not None and not self._pixmap_rect.isNull():
            old_rect = self._state.rect.normalized()
            image_coords = widget_rect_to_image_space(old_rect, self._pixmap_rect, self._image_size)
            self._state.rect = image_rect_to_widget_space(*image_coords, rect, self._image_size).normalized()

        self._pixmap_rect = rect
        self.update()

    def set_image_size(self, size: QSize) -> None:
        """Called by the App to supply raw video dimensions for coordinate math."""
        self._image_size = size

    def set_active_bboxes(self, bboxes: dict[str, BBoxXYXYTuple]) -> None:
        """Update the set of active bounding boxes and cancel editing if the current bbox was removed."""
        self._active_bboxes = bboxes
        self._selected_bbox_keys.intersection_update(bboxes)
        if self._editing_bbox_id and self._editing_bbox_id not in bboxes:
            self.cancel_edit()
        self.update()

    def set_selected_bbox_keys(self, box_keys: list[str]) -> None:
        """Render shared selection state without taking ownership of that state."""
        self._selected_bbox_keys = set(box_keys).intersection(self._active_bboxes)
        if self._editing_bbox_id and self._editing_bbox_id not in self._selected_bbox_keys:
            logger.debug("Clearing stale edit handles for deselected bbox {}.", self._editing_bbox_id)
            self._editing_bbox_id = None
            self._group_drag_keys = []
            self._state = BBoxState()
        logger.trace("Overlay selection updated: {}", sorted(self._selected_bbox_keys))
        self.update()

    def set_tool_mode(self, mode: ToolMode) -> None:
        """Change the active tool mode and update the cursor accordingly."""
        self._tool_mode = mode
        self.cancel_edit()

        if mode == ToolMode.ADD:
            self.setCursor(QCursor(Qt.CursorShape.CrossCursor))
        else:
            self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))

    def set_zoom(self, zoom: float) -> None:
        """Update the zoom level for coordinate transforms."""
        self._zoom = zoom
        self.update()

    def set_pan(self, pan_x: float, pan_y: float) -> None:
        """Update the pan offset for coordinate transforms."""
        self._pan_x = pan_x
        self._pan_y = pan_y
        self.update()

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

        if self._marquee_origin is not None:
            self._marquee_rect = QRect(self._marquee_origin, self._clamp(pos)).normalized()
            self.update()
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
            bbox_id = self._get_bbox_id_at_pos(pos)
            if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                if bbox_id:
                    self.bbox_selection_requested.emit(bbox_id, True)
                return

            # A selected box starts a group move even when it is not the box
            # currently carrying edit handles. The current handle box retains
            # its normal resize behavior.
            if (
                bbox_id in self._selected_bbox_keys
                and len(self._selected_bbox_keys) > 1
                and not (
                    bbox_id == self._editing_bbox_id
                    and self._hit_test_handle(pos) != DragMode.NONE
                )
            ):
                _, bbox_rect = self._get_bbox_at_pos(pos)
                if bbox_rect is not None:
                    state.rect = bbox_rect
                    state.drag_mode = DragMode.MOVE
                    state.drag_origin = pos
                    state.rect_at_drag_start = QRect(bbox_rect)
                    self._editing_bbox_id = bbox_id
                    self._group_drag_keys = list(self._selected_bbox_keys)
                    logger.debug("Starting group drag from bbox {} for {} boxes.", bbox_id, len(self._group_drag_keys))
                    logger.trace("Group drag keys: {}", self._group_drag_keys)
                    self.update()
                    return

            # 1. Interact with currently active rect handles/move
            if try_begin_existing_edit_drag(state, pos, self._hit_test_handle):
                if (
                    state.drag_mode == DragMode.MOVE
                    and self._editing_bbox_id in self._selected_bbox_keys
                    and len(self._selected_bbox_keys) > 1
                ):
                    self._group_drag_keys = list(self._selected_bbox_keys)
                    logger.debug("Starting group drag for {} boxes.", len(self._group_drag_keys))
                return

            # 2. Try to grab a new detection
            bbox_id = try_select_bbox_for_edit(state, pos, self._get_bbox_at_pos)
            if bbox_id:
                self._editing_bbox_id = bbox_id
                self.bbox_selection_requested.emit(bbox_id, False)
                self._group_drag_keys = list(self._selected_bbox_keys)
                logger.debug("Selected bbox {} for drag; group size={}", bbox_id, len(self._group_drag_keys))
                self.update()
                return

            # 3. Clicked empty space
            self._marquee_origin = clamped
            self._marquee_rect = QRect(clamped, clamped)
            self.cancel_edit()
            self._marquee_origin = clamped
            self._marquee_rect = QRect(clamped, clamped)
            logger.debug("Starting marquee selection at ({}, {}).", clamped.x(), clamped.y())
            self.update()

    @override
    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """Finalize draw/edit outcomes and emit overlay signals when release completes."""
        # 3. Stop panning safely without clearing the active selection state.
        if stop_panning(self._is_panning):
            self._is_panning = False
            self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
            self.update()
            return

        if event.button() != Qt.MouseButton.LeftButton:
            return

        if self._marquee_origin is not None:
            marquee_rect = self._marquee_rect.normalized()
            self._marquee_origin = None
            self._marquee_rect = QRect()
            if marquee_rect.width() < _MIN_BBOX_PX or marquee_rect.height() < _MIN_BBOX_PX:
                self.bbox_selection_cleared.emit()
            else:
                self.bbox_marquee_selected.emit(
                    find_bbox_keys_intersecting_rect(
                        self._active_bboxes,
                        marquee_rect,
                        self._pixmap_rect,
                        self._image_size,
                    )
                )
            logger.trace(
                "Finished marquee selection with size {}x{}.",
                marquee_rect.width(),
                marquee_rect.height(),
            )
            self.update()
            return

        state = self._state
        logger.debug("Current state: {}", state)
        outcome, payload = finalize_release(
            state=state,
            editing_bbox_id=self._editing_bbox_id,
            min_bbox_px=_MIN_BBOX_PX,
            widget_rect_to_image_space=self._widget_rect_to_image_space,
        )
        if outcome == MouseReleaseOutcome.CANCEL:
            self.cancel_edit()
            return
        if outcome == MouseReleaseOutcome.DRAW and payload is not None:
            x1, y1, x2, y2 = payload
            self.cancel_edit()
            self.bbox_drawn.emit(x1, y1, x2, y2)
            return
        if outcome == MouseReleaseOutcome.EDIT and payload is not None:
            item_key, x1, y1, x2, y2 = payload
            if self._group_drag_keys:
                start_x1, start_y1, _, _ = self._widget_rect_to_image_space(state.rect_at_drag_start)
                delta_x, delta_y = x1 - start_x1, y1 - start_y1
                logger.debug(
                    "Completing group drag for {} boxes with delta ({}, {}).",
                    len(self._group_drag_keys),
                    delta_x,
                    delta_y,
                )
                logger.trace("Group drag keys: {}", self._group_drag_keys)
                if delta_x or delta_y:
                    self.bboxes_moved.emit(self._group_drag_keys, delta_x, delta_y)
            else:
                self.bbox_edited.emit(item_key, x1, y1, x2, y2)

        state.drag_mode = DragMode.NONE
        self._group_drag_keys = []

    # --- Context Menu ---

    @override
    def paintEvent(self, event: QPaintEvent) -> None:
        """Render the current bounding detection with selection handles and center point."""
        if not self._state.has_valid_rect and self._marquee_rect.isNull() and not self._selected_bbox_keys:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        group_drag_delta = QPoint()
        if self._group_drag_keys and self._state.drag_mode == DragMode.MOVE:
            group_drag_delta = self._state.rect.topLeft() - self._state.rect_at_drag_start.topLeft()

        for box_key in self._selected_bbox_keys:
            bbox_xyxy = self._active_bboxes.get(box_key)
            if bbox_xyxy is None:
                continue
            selected_rect = self._image_rect_to_widget_space(*bbox_xyxy)
            if box_key in self._group_drag_keys:
                selected_rect = selected_rect.translated(group_drag_delta)
            draw_selected_bbox(painter, selected_rect)
        if self._state.has_valid_rect:
            draw_active_bbox(painter, self._state.rect)
        if not self._marquee_rect.isNull():
            painter.setPen(QPen(_BOX_COLOR, 2, Qt.PenStyle.DashLine))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(self._marquee_rect)

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
        """Finds the closest bbox hit by the given point, accounting for zoom/pan."""
        return find_bbox_at_pos_with_transforms(
            active_bboxes=self._active_bboxes,
            pos=pos,
            pixmap_rect=self._pixmap_rect,
            image_size=self._image_size,
            zoom=self._zoom,
            pan_x=self._pan_x,
            pan_y=self._pan_y,
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
