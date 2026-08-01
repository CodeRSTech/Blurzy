# app/ui/qt/preview/layer_bbox.py
from __future__ import annotations

from typing import final, override

from PySide6.QtCore import Qt, Signal, QSize, QPoint, QRect
from PySide6.QtGui import (
    QPainter,
    QPen,
    QBrush,
    QColor,
    QCursor,
    QPaintEvent,
    QMouseEvent,
    QContextMenuEvent,
    QWheelEvent,
)
from PySide6.QtWidgets import QWidget, QMenu

from app.domain.base.dtypes import BBoxXYXYTuple
from app.shared.logging_cfg import get_logger
from app.ui.qt.data.bbox_drag import DragMode, CORNER_CURSOR
from app.ui.qt.data.bbox_state import BBoxState
from app.ui.qt.utilities.helpers import handle_points
from app.ui.state.preview_state import ToolMode

logger = get_logger("UI->Preview->Bbox Layer")


# --- Constants ---
_BOX_COLOR = QColor(255, 80, 80)
_CENTER_COLOR = QColor(255, 255, 255, 180)
_HANDLE_BORDER = QColor(200, 40, 40)
_HANDLE_COLOR = QColor(255, 255, 255)
_HANDLE_DRAW_R = 5
_HANDLE_RADIUS = 6
_MIN_BBOX_PX = 4


def get_drag_mode_for_rect_at_pos(rect: QRect, pos: QPoint) -> DragMode:
    x1, y1 = rect.left(), rect.top()
    x2, y2 = rect.right(), rect.bottom()
    mx, my = (x1 + x2) // 2, (y1 + y2) // 2
    r = _HANDLE_RADIUS

    handles: list[tuple[QPoint, DragMode]] = [
        (QPoint(x1, y1), DragMode.TOP_LEFT),
        (QPoint(x2, y1), DragMode.TOP_RIGHT),
        (QPoint(x1, y2), DragMode.BOT_LEFT),
        (QPoint(x2, y2), DragMode.BOT_RIGHT),
        (QPoint(mx, y1), DragMode.TOP),
        (QPoint(mx, y2), DragMode.BOTTOM),
        (QPoint(x1, my), DragMode.LEFT),
        (QPoint(x2, my), DragMode.RIGHT),
    ]
    for pt, mode in handles:
        if (pos - pt).manhattanLength() <= r * 2:
            return mode
    return DragMode.NONE


def clamp_rect_to_pixmap(rect: QRect, pixmap_rect: QRect) -> QRect:
    dx = dy = 0
    if rect.left() < pixmap_rect.left():
        dx = pixmap_rect.left() - rect.left()
    if rect.right() > pixmap_rect.right():
        dx = pixmap_rect.right() - rect.right()
    if rect.top() < pixmap_rect.top():
        dy = pixmap_rect.top() - rect.top()
    if rect.bottom() > pixmap_rect.bottom():
        dy = pixmap_rect.bottom() - rect.bottom()
    return rect.translated(dx, dy)


def apply_clamped_drag_deltas(mode: DragMode, pr: QRect, x1: int, x2: int, y1: int, y2: int, dx: int, dy: int) -> QRect:
    def clamp_x(v: int) -> int:
        return max(pr.left(), min(v, pr.right()))

    def clamp_y(v: int) -> int:
        return max(pr.top(), min(v, pr.bottom()))

    if mode == DragMode.TOP_LEFT:
        x1, y1 = clamp_x(x1 + dx), clamp_y(y1 + dy)
    elif mode == DragMode.TOP_RIGHT:
        x2, y1 = clamp_x(x2 + dx), clamp_y(y1 + dy)
    elif mode == DragMode.BOT_LEFT:
        x1, y2 = clamp_x(x1 + dx), clamp_y(y2 + dy)
    elif mode == DragMode.BOT_RIGHT:
        x2, y2 = clamp_x(x2 + dx), clamp_y(y2 + dy)
    elif mode == DragMode.TOP:
        y1 = clamp_y(y1 + dy)
    elif mode == DragMode.BOTTOM:
        y2 = clamp_y(y2 + dy)
    elif mode == DragMode.LEFT:
        x1 = clamp_x(x1 + dx)
    elif mode == DragMode.RIGHT:
        x2 = clamp_x(x2 + dx)

    return QRect(QPoint(x1, y1), QPoint(x2, y2)).normalized()


def clamp_point_to_rect(point: QPoint, r: QRect) -> QPoint:
    return QPoint(
        max(r.left(), min(point.x(), r.right())),
        max(r.top(), min(point.y(), r.bottom())),
    )


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
            action_select_all = menu.addAction("Select All")
            action_select_none = menu.addAction("Deselect All")
            action_select_inverse = menu.addAction("Invert Selection")
            menu.addSeparator()
            action_create_bbox_here = menu.addAction("Add Bounding Box Here")
            action_remove_all_boxes = menu.addAction("Remove All Bounding Boxes")
            menu.addSeparator()
            action_reset_current_frame = menu.addAction("Reset Current Frame")
            action_reset_all_frames = menu.addAction("Reset All Frames")

            chosen = menu.exec(event.globalPos())

            # Route logic via string keys to the Controller
            if chosen == action_select_all:
                self.context_action_triggered.emit("select_all", hit_box_id)
            elif chosen == action_select_none:
                self.context_action_triggered.emit("select_none", hit_box_id)
            elif chosen == action_select_inverse:
                self.context_action_triggered.emit("inv_selection", hit_box_id)
            elif chosen == action_create_bbox_here:
                self.context_action_triggered.emit("add_bbox_here", hit_box_id)
            elif chosen == action_remove_all_boxes:
                self.context_action_triggered.emit("del_all_bboxes", hit_box_id)
            elif action_reset_current_frame:
                self.context_action_triggered.emit("reset_current_frame", hit_box_id)
            elif action_reset_all_frames:
                self.context_action_triggered.emit("reset_all_frames", hit_box_id)

            return

        menu = QMenu(self)
        action_select_all = menu.addAction("Select All")
        action_select_none = menu.addAction("Deselect All")
        action_select_inverse = menu.addAction("Invert Selection")
        action_dup_next = menu.addAction("Duplicate to Next Frame")
        action_dup_prev = menu.addAction("Duplicate to Previous Frame")
        action_dup_current = menu.addAction("Duplicate to Current Frame")
        menu.addSeparator()
        action_copy = menu.addAction("Copy")
        action_paste = menu.addAction("Paste")
        menu.addSeparator()
        action_delete = menu.addAction("Delete")

        action_del_next = None
        action_del_prev = None
        if self._tracker_actions_enabled:
            menu.addSeparator()
            action_del_next = menu.addAction("Delete Next Occurrences")
            action_del_prev = menu.addAction("Delete Previous Occurrences")

        chosen = menu.exec(event.globalPos())

        # Route logic via string keys to the Controller
        if chosen == action_dup_next:
            self.context_action_triggered.emit("copy_next", hit_box_id)
        elif chosen == action_dup_prev:
            self.context_action_triggered.emit("copy_prev", hit_box_id)
        elif chosen == action_dup_current:
            self.context_action_triggered.emit("copy_current", hit_box_id)
        elif chosen == action_copy:
            self.context_action_triggered.emit("copy", hit_box_id)
        elif chosen == action_paste:
            self.context_action_triggered.emit("paste", hit_box_id)
        elif chosen == action_delete:
            self.context_action_triggered.emit("delete", hit_box_id)
        elif chosen == action_del_next:
            self.context_action_triggered.emit("delete_next", hit_box_id)
        elif chosen == action_del_prev:
            self.context_action_triggered.emit("delete_prev", hit_box_id)

    @override
    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Handle mouse movement to update bbox drag operations or emit pan requests."""
        pos = event.position().toPoint()

        # 2. Process Panning continuously while mouse moves!
        if self._is_panning:
            delta = pos - self._last_pan_pos
            self._last_pan_pos = pos
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

        clamped = self._clamp(pos)

        if state.drag_mode == DragMode.DRAW:
            state.rect = QRect(state.drag_origin, clamped).normalized()
        elif state.drag_mode == DragMode.MOVE:
            delta = pos - state.drag_origin
            moved = state.rect_at_drag_start.translated(delta)
            state.rect = self._clamp_rect(moved)
        else:
            state.rect = self._apply_handle_drag(
                state.rect_at_drag_start, state.drag_mode, pos - state.drag_origin
            )
        self.update()

    @override
    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Handle mouse press to start drawing, panning, or selecting bounding boxes."""
        # 1. Catch Ctrl + Left Click to START panning
        # TODO: Swap Ctrl with Alt (Ctrl will be used for selecting boxes)
        #  Selection process will work in sync across THIS widget and,
        #  Tables within data tab of the BottomDataPanel,
        #  i.e. Detection/Tracking tables.
        #  Somewhere, a data structure (say list) will hold the selected detection keys.
        #  This is how it will be done:
        #  ----
        #  Case 1. : User clicks on a detection over the canvas (while NO boxes were selected)
        #   - the detection will be selected and
        #     the data tab will be updated accordingly
        #     (detection will become active on the data tab)
        #  Case 2. : User clicks on a detection over the canvas
        #            (while one or more boxes were selected AND Ctrl is held down)
        #   - the detection will be selected
        #   - the data tab will be updated accordingly
        #     (detection will become active on the data tab)
        #  ----
        #  IMPORTANT NOTE:
        #  While operations like Drag, Copy, Paste, Delete, etc. can be performed on two or more selected boxes,
        #  Operations like resize etc can NOT be used and are restricted to a single detection only.
        #  ----
        #  ANOTHER NOTE: Selection via canvas reflects in the data tab.
        #  SIMILARLY, Selection via data tab reflects in the canvas.
        #
        is_ctrl = event.modifiers() == Qt.KeyboardModifier.ControlModifier
        if event.button() == Qt.MouseButton.LeftButton and is_ctrl:
            self._is_panning = True
            self._last_pan_pos = event.position().toPoint()
            self.setCursor(QCursor(Qt.CursorShape.ClosedHandCursor))
            return

        if event.button() != Qt.MouseButton.LeftButton:
            return

        pos = event.position().toPoint()
        clamped = self._clamp(pos)
        state = self._state

        # MODE: ADD
        if self._tool_mode == ToolMode.ADD:
            state.rect = QRect(clamped, clamped)
            state.drag_mode = DragMode.DRAW
            state.drag_origin = clamped
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
            if state.has_valid_rect:
                drag_mode = self._hit_test_handle(pos)
                if drag_mode != DragMode.NONE:
                    state.drag_mode = drag_mode
                    state.drag_origin = pos
                    state.rect_at_drag_start = QRect(state.rect)
                    return
                if state.rect.contains(pos):
                    state.drag_mode = DragMode.MOVE
                    state.drag_origin = pos
                    state.rect_at_drag_start = QRect(state.rect)
                    return

            # 2. Try to grab a new detection
            bbox_id, bbox_rect = self._get_bbox_at_pos(pos)
            if bbox_id and bbox_rect:
                self._editing_bbox_id = bbox_id
                state.rect = bbox_rect
                state.drag_mode = DragMode.MOVE if bbox_rect.contains(pos) else DragMode.NONE
                state.drag_origin = pos
                state.rect_at_drag_start = QRect(state.rect)
                self.update()
                return

            # 3. Clicked empty space
            self.cancel_edit()

    @override
    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """Handle mouse release to finish drawing, moving, or resizing bounding boxes."""
        # 3. Stop panning safely
        if self._is_panning:
            self._is_panning = False
            self.cancel_edit()  # Resets cursor back to Arrow
            return

        if event.button() != Qt.MouseButton.LeftButton:
            return

        state = self._state
        logger.debug("Current state: {}", state)
        if state.drag_mode == DragMode.DRAW:
            if state.rect.width() < _MIN_BBOX_PX or state.rect.height() < _MIN_BBOX_PX:
                self.cancel_edit()
            else:
                x1, y1, x2, y2 = self._widget_rect_to_image_space(state.rect)
                self.cancel_edit()
                self.bbox_drawn.emit(x1, y1, x2, y2)  # Instantly confirms!
            return

        if self._editing_bbox_id is not None and state.drag_mode != DragMode.NONE:
            x1, y1, x2, y2 = self._widget_rect_to_image_space(state.rect)
            self.bbox_edited.emit(self._editing_bbox_id, x1, y1, x2, y2)

        state.drag_mode = DragMode.NONE

    # --- Context Menu ---

    @override
    def paintEvent(self, event: QPaintEvent) -> None:
        """Render the current bounding detection with selection handles and center point."""
        if not self._state.has_valid_rect:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self._state.rect
        painter.setPen(QPen(_BOX_COLOR, 2, Qt.PenStyle.SolidLine))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(rect)

        # Center dot
        cx, cy = rect.center().x(), rect.center().y()
        painter.setPen(QPen(_BOX_COLOR, 1))
        painter.setBrush(QBrush(_CENTER_COLOR))
        r = _HANDLE_DRAW_R + 2
        painter.drawEllipse(QPoint(cx, cy), r, r)

        # Handles
        for pt in handle_points(rect):
            painter.setPen(QPen(_HANDLE_BORDER, 1))
            painter.setBrush(QBrush(_HANDLE_COLOR))
            painter.drawEllipse(pt, _HANDLE_DRAW_R, _HANDLE_DRAW_R)

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
        closest_id = None
        closest_rect = None
        min_dist = float("inf")

        for bbox_id, (x1, y1, x2, y2) in self._active_bboxes.items():
            rect = self._image_rect_to_widget_space(x1, y1, x2, y2)
            if rect.isNull():
                continue

            if rect.contains(pos):
                return bbox_id, rect  # Direct hit

            cx, cy = rect.center().x(), rect.center().y()
            dist = (pos.x() - cx) ** 2 + (pos.y() - cy) ** 2
            if dist < min_dist:
                min_dist = dist
                closest_id = bbox_id
                closest_rect = rect

        if min_dist < 2500:  # ~50px snap radius
            return closest_id, closest_rect
        return None, None

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
        r = self._pixmap_rect
        if r.width() == 0 or self._image_size is None:
            return QRect()
        sx = r.width() / self._image_size.width()
        sy = r.height() / self._image_size.height()
        return QRect(
            QPoint(int((x1 * sx) + r.left()), int((y1 * sy) + r.top())),
            QPoint(int((x2 * sx) + r.left()), int((y2 * sy) + r.top())),
        ).normalized()

    def _widget_rect_to_image_space(self, rect: QRect) -> BBoxXYXYTuple:
        """Convert widget space rectangle to image space coordinates with scaling and bounds applied."""
        r = self._pixmap_rect
        if r.width() == 0 or self._image_size is None:
            return 0, 0, 0, 0
        sx = self._image_size.width() / r.width()
        sy = self._image_size.height() / r.height()
        return (
            max(0, int((rect.left() - r.left()) * sx)),
            max(0, int((rect.top() - r.top()) * sy)),
            min(self._image_size.width(), int((rect.right() - r.left()) * sx)),
            min(self._image_size.height(), int((rect.bottom() - r.top()) * sy)),
        )