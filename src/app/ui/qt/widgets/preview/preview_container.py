# app/ui/qt/preview/preview_container.py
from __future__ import annotations

from typing import TYPE_CHECKING, final, override

from PySide6.QtCore import QRect, QSize, Signal, QPointF
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QWidget, QStackedLayout, QSizePolicy

from app.ui.qt.widgets import AnnotationOverlayWidget, VideoDisplayWidget
from app.ui.view_state.preview_state import ToolMode

from app.shared.logging_cfg import get_logger
if TYPE_CHECKING:
    from app.domain.base.dtypes import BBoxXYXYTuple

logger = get_logger("UI->Preview->Container")


@final
class PreviewContainer(QWidget):
    """
    SRP: Composes the Video Base Layer and Interactive Overlays using QStackedLayout.
    Acts as the single Facade API for the EditorController.

    TODO:
     The AnnotationOverlayWidget is likely handling
     both Qt Event processing (mouse press, mouse move) AND
     Coordinate Algebra (translating physical screen pixels to video-relative ratios,
     handling zoom offsets, aspect ratio letterboxing calculations).
     -
     TL;DR VERSION:
     Separate aforementioned responsibilities into separate classes.

    """

    # --- Signals echoed up to the Controller ---
    bbox_drawn = Signal(int, int, int, int)
    bbox_edited = Signal(str, int, int, int, int)
    bbox_deleted = Signal(str)
    context_action_triggered = Signal(str, str)  # action_name, item_key
    bbox_selected = Signal(str)  # item_key (new: canvas-driven selection)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._parent = parent
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(640, 360)

        # Visual layer is underneath; interactive detection overlay sits on top.
        self.video_layer = VideoDisplayWidget()
        self.bbox_layer = AnnotationOverlayWidget()

        # 2. Stack them (Top to Bottom)
        self._layout: QStackedLayout = QStackedLayout(self)
        self._layout.setStackingMode(QStackedLayout.StackingMode.StackAll)
        self._layout.addWidget(self.bbox_layer)  # Index 0 (Top - Interactive)
        self._layout.addWidget(self.video_layer)  # Index 1 (Bottom - Visual)

        # 3. Internal Event Routing
        # When the video resizes and calculates new letterbox margins,
        # it tells the overlay so the bounding boxes scale perfectly.
        self.video_layer.pixmap_rect_changed.connect(self._handle_video_pixmap_rect_change)

        # Route the overlay's business signals up to the outside world
        self.bbox_layer.bbox_drawn.connect(self.bbox_drawn.emit)
        self.bbox_layer.bbox_edited.connect(self.bbox_edited.emit)
        self.bbox_layer.bbox_deleted.connect(self.bbox_deleted.emit)
        self.bbox_layer.bbox_selected.connect(self.bbox_selected.emit)  # New: canvas selection
        self.bbox_layer.context_action_triggered.connect(self.context_action_triggered.emit)

        # --- Viewport State ---
        self._current_zoom = 1.0
        self._current_pan = QPointF(0.0, 0.0)

        # Route viewport events
        self.bbox_layer.zoom_requested.connect(self._handle_zoom)
        self.bbox_layer.pan_requested.connect(self._handle_pan)

    # --- Public Facade API for EditorController ---
    

    def set_image(self, image: QImage) -> None:
        """Passes the raw video frame down to the display layer."""
        self.video_layer.set_image(image)

    def set_message(self, message: str) -> None:
        """Passes placeholder text down to the display layer."""
        self.video_layer.set_message(message)
        self.bbox_layer.cancel_edit()

    def set_tool_mode(self, mode: ToolMode) -> None:
        """
        Changes the active interactive tool.
        In the future, if a Draw Polygon tool is added, this method would disable
        the bbox_layer's hit-testing and enable the polygon_layer's hit-testing.
        """
        self.bbox_layer.set_tool_mode(mode)

    def set_active_bboxes(self, bboxes: dict[str, BBoxXYXYTuple]) -> None:
        """Injects the live bounding boxes from the current data tab into the overlay."""
        self.bbox_layer.set_active_bboxes(bboxes)

    def set_tracker_actions_enabled(self, enabled: bool) -> None:
        """
        Tells the overlay whether context menu boxes specific to tracking
        (e.g. 'Delete Next Occurrences') should be enabled.
        """
        self.bbox_layer.set_tracker_actions_enabled(enabled)

    def cancel_active_edits(self) -> None:
        self.bbox_layer.cancel_edit()

    def _handle_video_pixmap_rect_change(self, rect: QRect, size: QSize) -> None:
        self.bbox_layer.set_pixmap_rect(rect)
        self.bbox_layer.set_image_size(size)

    @override
    def __str__(self) -> str:
        return f"PreviewContainer(video_layer={self.video_layer}, bbox_layer={self.bbox_layer})"

    @override
    def __repr__(self) -> str:
        return f"PreviewContainer(parent = {self._parent.__repr__()})"

    def _handle_pan(self, dx: int, dy: int) -> None:
        self._current_pan += QPointF(dx, dy)
        self.video_layer.set_pan(self._current_pan.x(), self._current_pan.y())
        self.bbox_layer.set_pan(self._current_pan.x(), self._current_pan.y())  # Sync to overlay

    def _handle_zoom(self, scroll_delta: float, mouse_x: int, mouse_y: int) -> None:
        # TODO:
        #  The UI widget should just say
        #  `CoordinateMapper.screen_to_video(mouse_x, mouse_y, current_zoom)` and get the result.
        #  This makes your complex panning/zooming logic easily unit-testable without needing a GUI.
        zoom_step = 1.1 if scroll_delta > 0 else 0.9
        new_zoom = max(1.0, min(self._current_zoom * zoom_step, 10.0))

        if new_zoom == self._current_zoom:
            return

        # 1. Find the physical center of the widget
        cx = self.width() / 2.0
        cy = self.height() / 2.0

        # 2. Calculate the distance of the mouse from the center
        mx = mouse_x - cx
        my = mouse_y - cy

        # 3. Calculate the counter-shift required to keep the pixel under the mouse stationary
        scale_ratio = new_zoom / self._current_zoom
        shift_x = mx * (scale_ratio - 1.0)
        shift_y = my * (scale_ratio - 1.0)

        # 4. Apply the counter-shift directly to the pan offset
        self._current_pan.setX(self._current_pan.x() - shift_x)
        self._current_pan.setY(self._current_pan.y() - shift_y)

        self._current_zoom = new_zoom

        # Reset pan if zoomed all the way out
        if self._current_zoom == 1.0:
            self._current_pan = QPointF(0, 0)

        self.video_layer.set_zoom(self._current_zoom)
        self.video_layer.set_pan(self._current_pan.x(), self._current_pan.y())
        # Sync to overlay
        self.bbox_layer.set_zoom(self._current_zoom)
        self.bbox_layer.set_pan(self._current_pan.x(), self._current_pan.y())