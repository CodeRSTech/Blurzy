"""Frame rendering and UI view_state management handler."""

from __future__ import annotations

from typing import TYPE_CHECKING, final, override

from PySide6.QtCore import Slot


from app.shared.frame_overlay import draw_frame_overlays
from app.shared.image_utils import rgb_frame_to_q_image
from app.shared.logging_cfg import get_logger
if TYPE_CHECKING:
    from app.domain import SessionId, VideoDataLayerGroup


if TYPE_CHECKING:
    from app.infrastructure.dtypes import RGBFrame, ListOfBoxes
    from app.ui.uicontroller import UIController

logger = get_logger("UI->UIHandler")


@final
class UIHandler:
    # [AUDIT] Qt CONVENTIONS: UIHandler doesn't inherit from QObject
    # This handler delegates frame rendering and doesn't use Qt signals/slots directly.
    # Current design appears intentional: pure logic handler without Qt dependencies.
    # Note: If future requirements involve signals, inherit from QObject:
    #   class UIHandler(QObject): ...
    # Verify this doesn't prevent signal connections elsewhere in the codebase.
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
        Works with ``RGBFrame`` data from session cache.
        Converts frames and generates overlays for preview container.
    """

    def __init__(self, controller: UIController) -> None:
        self._controller = controller
        self._window = controller.window
        self._app = controller.app
        self._win = controller.window

        self._connect_signals()

    @override
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}>"

    def _connect_signals(self):
        pass

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    #                           PUBLIC METHODS
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def set_boxes_for_tab(self, boxes: ListOfBoxes, tab: VideoDataLayerGroup) -> None:
        """
        Update the data boxes displayed in a specific tab.
    
        Args:
            boxes (ListOfBoxes): List of ``BBoxViewModel`` objects to display.
            tab (VideoDataLayerGroup): Target tab (``DataBox.DETECTION`` or ``DataBox.TRACKING``).
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
    
            Status Format: ``filename | 1920x1080 | 30.00 fps | 1/1500 frames | Playing | Model: yolov8n``.
        """
        # ====================================================================
        # 1. FETCH ACTIVE SESSION
        # ====================================================================
        session = self._app.active_session
        if session is None:
            self._window.set_status_text("No session loaded")
            return

        # ====================================================================
        # 2. EXTRACT SESSION STATE VARIABLES
        # ====================================================================
        metadata = session.state.metadata
        playback = session.state.playback
        model_name = session.state.settings.detection_model_name

        # ====================================================================
        # 3. FORMAT STATUS TEXT WITH METADATA
        # ====================================================================
        status_text = (
            f"{metadata.path.split('/')[-1]} | "  # [NOTE] Equivalent to os.path.basename()
            f"{metadata.width}x{metadata.height} | "
            f"{metadata.fps:.2f} fps | "
            f"{playback.current_frame_index + 1}/{metadata.frame_count} frames | "
            f"{'Playing' if playback.is_playing else 'Paused'} | "
            f"Model: {model_name}"
        )

        # ====================================================================
        # 4. DISPLAY STATUS TEXT IN UI
        # ====================================================================
        self._window.set_status_text(status_text)

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    #                           SLOTS
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    @Slot(object)
    def render_saved_frame(self, s_id: SessionId) -> None:
        """
        Fetch, draw boxes on, and display the current frame for a session.
    
        Note:
            Triggered by ``UIController.render_frame_for_session_id()`` internal calls.
    
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

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    #                           PRIVATE METHODS
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def _draw_boxes_on_frame_for_session_id(self, s_id: SessionId, frame: RGBFrame) -> None:
        """
        Fetch boxes for the current frame and prepare frame for rendering.
    
        Note:
            Flow:
                _draw_boxes_on_frame_for_session_id(s_id, frame)
                  ├── Get detection boxes for current frame
                  ├── Get tracking boxes for current frame
                  ├── Determine which boxes to display (based on active tab)
                  └──> Call _update_frame_with_bboxes() to render
    
            Only displays boxes if ``draw_boxes_enabled`` is True.
            Displays detection boxes if Detection tab active, tracking boxes if Tracking tab active.
        """
        session = self._app.get_session_by_id(s_id)
        # ====================================================================
        # 1. GET DETECTION AND TRACKING BOXES FOR CURRENT FRAME
        # ====================================================================
        # TODO: ACTIVE TAB BOXES ARE SUFFICIENT
        # detections = self._app.get_tab_frame_boxes_for_session_id(s_id, DataBox.DETECTION).frame_data_boxes
        # trackers = self._app.get_tab_frame_boxes_for_session_id(s_id, DataBox.TRACKING).frame_data_boxes

        # ====================================================================
        # 2. DETERMINE WHICH BOXES TO DISPLAY
        # ====================================================================
        active_tab = self._window.active_tab_index
        display = (
            self._app.get_tab_frame_boxes_for_session_id(s_id, active_tab).frame_data_boxes
            if session.state.settings.draw_boxes
            else None
        )

        # ====================================================================
        # 3. UPDATE FRAME WITH BOXES
        # ====================================================================
        self._update_frame_with_bboxes(
            frame, tab_index=active_tab, boxes_to_draw=display
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
        boxes_to_draw: ListOfBoxes | None = None,
    ) -> None:
        """
        Draw bounding boxes on frame and update UI preview.
    
        Note:
            Flow:
                ``_update_frame_with_bboxes(frame, detections, trackers, boxes_to_draw)``
                  ├── Set active bboxes for overlay highlighting
                  ├── Draw boxes_to_draw onto frame
                  ├── Convert RGB frame to QImage
                  ├── Display QImage in preview container
                  └──> Populate data tabs with detection and tracking boxes
    
            Handles:
                Box drawing with color/label overlays.
                RGB to QImage conversion for Qt display.
                Data tab population (may be called without drawing if ``boxes_to_draw`` is None).
        """
        try:
            # ================================================================
            # 1. SET ACTIVE BBOXES FOR OVERLAY HIGHLIGHTING
            # ================================================================
            # [NOTE] Highlights selected boxes in the preview container
            if boxes_to_draw is not None:
                active_bboxes = {box.key: box.bbox_xyxy for box in boxes_to_draw}
                self._window.preview_container.set_active_bboxes(active_bboxes)

            # ================================================================
            # 2. DRAW BOXES ON FRAME
            # ================================================================
            frame_out = draw_frame_overlays(frame, boxes_to_draw)

            # ================================================================
            # 3. CONVERT TO QIMAGE AND DISPLAY
            # ================================================================
            self._window.preview_container.set_image(rgb_frame_to_q_image(frame_out))

            # ================================================================
            # 4. POPULATE DATA TABS WITH BOXES
            # ================================================================
            self.set_boxes_for_tab(boxes_to_draw, tab_index)
        except Exception:
            logger.opt(exception=True).error(
                "Error updating UI view_state with boxes",
            )
