"""
Frame rendering and UI view_state management handler.

See Also:
    - [`UIController`][app.ui.uicontroller.UIController] — coordinates the UI handlers
    - [`PreviewContainer`][app.ui.qt.widgets.preview.preview_container.PreviewContainer] — renders frames and canvas-space annotations

Layer: Presentation.
Context: Converts user actions and worker signals into application calls and UI feedback.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, final, override

from PySide6.QtCore import Slot

from app.shared.image_utils import rgb_frame_to_q_image
from app.shared.logging_cfg import get_logger
from app.shared.masked_blur import (
    apply_masked_blur,
    compute_blur_alpha_mask,
    overlay_alpha_mask,
)
from app.domain import VideoDataLayer
if TYPE_CHECKING:
    from app.domain import SessionId, VideoDataLayerGroup
    from app.infrastructure.dtypes import RGBFrame, ListOfBoxes
    from app.ui.uicontroller import UIController

logger = get_logger("UI->UIHandler")


@final
class UIHandler:
    """
    Manages frame rendering and UI view_state updates.

    Responsibilities:
        - Fetch and render video frames from session cache.
        - Draw bounding boxes (detections and tracking) on frames.
        - Update frame label (current frame / total frames).
        - Update seek slider range and position.
        - Populate detection and tracking data tabs.
        - Convert RGB frames to QImage for display.

    Note:
        Separates rendering logic from handler coordination.
        Does not emit signals (utility class for UI updates).
        Works with `RGBFrame` data from session cache.
        Converts frames and generates overlays for preview container.

    Layer: Presentation.
    Context: Supports user interaction and delegates application work through presentation contracts.
    """

    def __init__(self, controller: UIController) -> None:
        """
        Initialize the UIHandler.
        Args:
            controller: The UIController instance that coordinates the UI handlers.
        """
        self._controller = controller
        self._window = controller.window
        self._app = controller.app
        self._win = controller.window

    @override
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}>"

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    #                           PUBLIC METHODS
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def set_boxes_for_tab(self, boxes: ListOfBoxes, tab: VideoDataLayerGroup) -> None:
        """
        Update the data boxes displayed in a specific tab.

        Args:
            boxes (ListOfBoxes): List of `BBoxViewModel` objects to display.
            tab (VideoDataLayerGroup): Target tab (`DataBox.DETECTION` or `DataBox.TRACKING`).
        """
        self._window.bottom_panel.set_data_boxes_for_tab(boxes, tab)

    def update_status_bar(self) -> None:
        """
        Update status bar with session metadata and playback view_state.

        Note:
            Flow:
                update_status_bar()
                  ├── Fetch active session
                  ├── Extract metadata (filename, resolution, FPS, frame count)
                  ├── Extract playback view_state (current frame, playing status)
                  └──> Format and set status text

            Status Format: `filename | 1920x1080 | 30.00 fps | 1/1500 frames | Playing | Model: yolov8n`.
        """
        # ====================================================================
        # 1. FETCH ACTIVE SESSION
        # ====================================================================
        session = self._app.active_session
        if session is None:
            self._window.transport_panel.set_rotation_degrees(0)
            self._window.set_status_text("No session loaded")
            return

        # ====================================================================
        # 2. EXTRACT SESSION STATE VARIABLES
        # ====================================================================
        metadata = session.state.metadata
        playback = session.state.playback
        model_name = session.state.settings.detection_model_name
        rotation_degrees = session.video_reader.manual_rotation if session.video_reader is not None else 0
        width = session.video_reader.width if session.video_reader is not None else metadata.width
        height = session.video_reader.height if session.video_reader is not None else metadata.height
        self._window.transport_panel.set_rotation_degrees(rotation_degrees)

        # ====================================================================
        # 3. FORMAT STATUS TEXT WITH METADATA
        # ====================================================================
        status_text = (
            f"{metadata.path.split('/')[-1]} | "  # [NOTE] Equivalent to os.path.basename()
            f"{width}x{height} | "
            f"{metadata.fps:.2f} fps | "
            f"{playback.current_frame_index + 1}/{metadata.frame_count} frames | "
            f"{'Playing' if playback.is_playing else 'Paused'} | "
            f"Model: {model_name} | "
            f"Rot: {rotation_degrees}°"
        )

        # ====================================================================
        # 4. DISPLAY STATUS TEXT IN UI
        # ====================================================================
        self._window.set_status_text(status_text)

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    #                           SLOTS
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    @Slot(object)
    def render_saved_frame(self, s_id: SessionId) -> None:
        """
        Fetch, draw boxes on, and display the current frame for a session.

        Note:
            Triggered by `UIController.render_frame_for_session_id()` internal calls.

            Flow:
                render_saved_frame(s_id) [this slot]
                  ├── Get session and current frame from cache
                  ├── Draw detection and tracking boxes on frame
                  └──> Update UI labels, seek slider, and status bar

            Handles:
                Frame acquisition from session cache.
                Bounding detection drawing (detection + tracking overlays).
                UI view_state sync (frame label, seek position, status text).
        """
        # ====================================================================
        # 1. GET SESSION AND CURRENT FRAME
        # ====================================================================
        idx, frame_count, frame = 0, 0, None

        try:
            session = self._app.get_session_by_id(s_id)
            idx = session.state.playback.current_frame_index
            frame_count = session.state.metadata.frame_count
            frame = session.get_current_frame()
        except Exception:
            logger.opt(exception=True).error("Error getting current frame for session '{}', skipping", s_id)

        # ====================================================================
        # 2. RENDER FRAME WITH BOXES
        # ====================================================================
        if frame is None:
            return
        self._draw_boxes_on_frame_for_session_id(s_id, frame)

        # ====================================================================
        # 3. UPDATE UI STATE (LABELS, SEEK SLIDER, STATUS)
        # ====================================================================
        frame_label_text = f"Frame {idx + 1}/{frame_count}"
        self._set_ui_state(
            frame_label_text=frame_label_text, idx=idx, max_frame_idx=max(frame_count - 1, 0)
        )
        self.update_status_bar()

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    #                           PRIVATE METHODS
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def _draw_boxes_on_frame_for_session_id(self, s_id: SessionId, frame: RGBFrame) -> None:
        """
        Fetch boxes for the current frame and prepare frame for rendering.

        ???+ abstract "Flow"
            _draw_boxes_on_frame_for_session_id(s_id, frame)
              ├── Get detection boxes for current frame
              ├── Get tracking boxes for current frame
              ├── Determine which boxes to display (based on active tab)
              └──> Call _update_frame_with_bboxes() to render



        Args:
            s_id: Session whose frame is being rendered.
            frame: Decoded RGB frame.
        Raises:
            Exception: Propagates failures fetching session data or applying overlays.

        ???+ note "Notes"
            - Preview outlines are drawn only if `draw_boxes` is True; table data is
            always populated independently of outline visibility.
            - Displays detection boxes if Detection tab active, tracking boxes if Tracking tab active.
            - Live Gaussian blur requires both export `blur_enabled` and the
            editor-only `preview_blur_enabled` setting.

        Example:
            ```python
            handler._draw_boxes_on_frame_for_session_id(session_id, frame)
            ```
        """
        session = self._app.get_session_by_id(s_id)

        # ====================================================================
        # 1. DETERMINE WHICH BOXES TO DISPLAY
        # ====================================================================
        active_tab = self._window.active_tab_index
        frame_boxes = self._app.get_tab_frame_boxes_for_session_id(s_id, active_tab).frame_data_boxes

        settings = session.state.settings
        render_layer = (
            VideoDataLayer.D
            if session.data.has_boxes_for_layer(VideoDataLayer.D)
            else VideoDataLayer.C
        )
        render_boxes = session.data.get_boxes_for_layer_at_frame_index_as_list(
            render_layer, session.state.playback.current_frame_index
        )
        if settings.blur_enabled and settings.preview_blur_enabled and render_boxes:
            frame = apply_masked_blur(frame.copy(), render_boxes, settings.blur_strength)
        if settings.show_preview_mask and render_boxes:
            alpha_mask = compute_blur_alpha_mask(frame.shape, render_boxes)
            frame = overlay_alpha_mask(frame, alpha_mask)

        # ====================================================================
        # 2. UPDATE FRAME WITH BOXES
        # ====================================================================
        self._update_frame_with_bboxes(
            frame,
            tab_index=active_tab,
            boxes=frame_boxes,
            border_width=settings.box_border_width,
            draw_boxes=settings.draw_boxes,
        )

    def _set_ui_state(
        self, frame_label_text: str, idx: int, max_frame_idx: int, status_text: str | None = None
    ) -> None:
        """
        Synchronize UI controls with frame playback view_state.

        Args:
            frame_label_text (str): Text to display in frame counter (e.g., "Frame 123/1500").
            idx (int): Current frame index (0-based).
            max_frame_idx (int): Maximum frame index (for seek slider range).
            status_text (str | None): Optional status bar text.

        Note:
            Updates:
                Frame label in preview container.
                Seek slider range and position.
                Status bar (if provided).
        """
        # ====================================================================
        # 1. UPDATE STATUS TEXT (IF PROVIDED)
        # ====================================================================
        if status_text is not None:
            self._window.set_status_text(status_text)

        # ====================================================================
        # 2. UPDATE SEEK SLIDER RANGE AND POSITION
        # ====================================================================
        self._window.transport_panel.set_seek_range(max_frame_idx)
        self._window.transport_panel.set_seek_value(idx)

        # ====================================================================
        # 3. UPDATE FRAME LABEL TEXT
        # ====================================================================
        self._window.set_frame_label_text(frame_label_text)

    def _update_frame_with_bboxes(
        self,
        frame: RGBFrame,
        tab_index: VideoDataLayerGroup,
        boxes: ListOfBoxes,
        border_width: int = 2,
        *,
        draw_boxes: bool = True,
    ) -> None:
        """
        Display a frame and supply annotations to the canvas-space Qt overlay.

        Note:
            Flow:
                `_update_frame_with_bboxes(frame, tab_index, boxes, draw_boxes=True)`
                  ├── Set active bboxes for overlay highlighting
                  ├── Supply colors and captions to the Qt overlay
                  ├── Convert RGB frame to QImage
                  ├── Display QImage in preview container
                  └──> Populate data tabs with detection and tracking boxes

            Handles:
                Canvas-space box drawing with readable color/label overlays.
                RGB to QImage conversion for Qt display.
                Data tab population independent of preview outline visibility.

        Args:
            frame: RGB image to display.
            tab_index: Active Detection or Tracking table.
            boxes: Current-frame active-tab boxes, including when outlines are hidden.
            border_width: Outline weight relative to a 480-pixel displayed video height.
            draw_boxes: Whether to draw preview outlines; never filters table data.
        Raises:
            Exception: Logs UI rendering failures and keeps the event loop alive.

        Note:
            Frames remain free of rasterized outlines. Qt paints ordinary and selected
            annotations using the same canvas-scaled width, independent of source resolution.

        Example:
            handler._update_frame_with_bboxes(frame, tab_index, boxes, border_width=2)
        """
        try:
            boxes_to_draw = boxes if draw_boxes else []
            logger.trace(
                "Rendering {} frame boxes for tab {}; preview outlines enabled={}",
                len(boxes), tab_index, draw_boxes,
            )
            # ================================================================
            # 1. SET ACTIVE BBOXES FOR OVERLAY HIGHLIGHTING
            # ================================================================
            # [NOTE] Highlights selected boxes in the preview container
            self._window.preview_container.set_annotations(boxes_to_draw)
            selected_keys = self._window.selected_frame_box_keys if draw_boxes else []
            logger.trace("Rendering {} selected overlay boxes: {}", len(selected_keys), selected_keys)
            self._window.preview_container.set_selected_bbox_keys(selected_keys)

            self._window.preview_container.set_box_border_width(border_width)

            # ================================================================
            # 2. CONVERT TO QIMAGE AND DISPLAY
            # ================================================================
            self._window.preview_container.set_image(rgb_frame_to_q_image(frame))

            # ================================================================
            # 4. POPULATE DATA TABS WITH BOXES
            # ================================================================
            self.set_boxes_for_tab(boxes, tab_index)
        except Exception:
            logger.opt(exception=True).error(
                "Error updating UI view_state with boxes",
            )
