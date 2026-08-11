"""Playback control handler for video playback operations."""

from __future__ import annotations

from typing import TYPE_CHECKING, final, override

from PySide6.QtCore import QTimer, Slot, QObject, Signal


from app.shared.logging_cfg import get_logger
if TYPE_CHECKING:
    from app.domain.session.session_id import SessionId


if TYPE_CHECKING:
    from app.ui.uicontroller import UIController

logger = get_logger("UI->PlaybackHandler")

# [AUDIT] UNRESOLVED BUG: Seeking interrupts playback
# Issue: If user is playing video and performs seek, playback pauses instead of resuming.
# Expected: Playback should resume automatically after seek completes.
# Current behavior: Playback view_state is not preserved during seek operation.
# Recommendation: Create GitHub issue to track this bug with details:
#   - Steps to reproduce: Play → Seek → observe playback stops
#   - Expected: Should resume playback after seek
#   - Root cause: Likely seek operation doesn't preserve playback_is_playing flag
# Estimated fix: Save playback view_state before seek, restore after seek completes.
# FIXME: If a session was playing while seeking, it should keep playing after seeking


@final
class PlaybackHandler(QObject):
    """
    Manages video playback controls and timer-based frame rendering.

    Responsibilities:
        - Handle play, pause, next frame, and previous frame actions.
        - Manage playback timer for periodic frame updates during playback.
        - Coordinate frame seeking and rendering.
        - Emit frame render requests to update the UI.

    Note:
        Signal flow:
            Receives signals from transport control panel (play, pause, seek buttons).
            Emits ``render_frame_requested`` signal to trigger frame updates.
            Uses QTimer to trigger periodic ``on_playback_tick()`` calls during playback.
    """

    render_frame_requested = Signal(object)
    """Emitted when a frame needs to be rendered. Payload: ``SessionId``."""

    def __init__(self, controller: UIController) -> None:
        super().__init__()
        self.setParent(controller)  # <- avoids circular dependency
        
        self._controller = controller
        self._app = controller.app
        self._window = controller.window

        self._playback_timer = QTimer()
        self._playback_timer.setSingleShot(False)
        
        self._connect_signals()

    @override
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}>"
    
    def _connect_signals(self) -> None:
        self._playback_timer.timeout.connect(self.on_playback_tick)

        self._controller.window.transport_panel.play_btn.clicked.connect(self.on_play)
        self._controller.window.transport_panel.pause_btn.clicked.connect(self.on_pause)
        self._controller.window.transport_panel.next_btn.clicked.connect(self.on_next_frame)
        self._controller.window.transport_panel.previous_btn.clicked.connect(self.on_previous_frame)

    @property
    def selected_s_id(self) -> SessionId:
        """Retrieves the selected session ID from the session list."""
        return self._window.selected_s_id

    @Slot()
    def on_play(self) -> None:
        """
        Start video playback for the selected session.
    
        Note:
            Triggered by transport panel ``play_btn.clicked`` signal.
    
            Flow:
                on_play() [this slot]
                  ├── Validate session is selected
                  └──> Call _start_session_playback(s_id)
                          ├── Start App playback
                          ├── Calculate frame interval
                          └──> Start playback QTimer
        """
        s_id: SessionId = self.selected_s_id
        logger.trace("Attempting to play video for session '{}'", s_id)

        if not s_id:
            logger.warning("Attempted to play without a session selected! Aborting playback.")
            return

        try:
            self._start_session_playback(s_id)
        except Exception as exc:
            self._window.show_error("Play Failed", str(exc))

    @Slot()
    def on_pause(self) -> None:
        """
        Stop video playback for the selected session.
    
        Note:
            Triggered by transport panel ``pause_btn.clicked`` signal.
    
            Action: Calls ``stop_playback()`` to halt the playback timer and app playback view_state.
        """
        self.stop_playback()

    @Slot()
    def on_next_frame(self) -> None:
        """
        Advance to the next frame in the selected session.
    
        Note:
            Triggered by transport panel ``next_btn.clicked`` signal.
    
            Flow:
                on_next_frame() [this slot]
                  ├── Stop current playback if active
                  ├── Load next frame via App
                  └──> Emit render_frame_requested(s_id)
        """
        s_id = self.selected_s_id
        if not s_id:
            return
        try:
            # [NOTE] Pause playback before advancing to next frame
            if self._app.is_session_playing(s_id):
                self.stop_playback()
            # self._controller.active_session_id = s_id
            self._app.load_next_frame(s_id)
            # self.render_frame_requested.emit(s_id)
            self._controller.render_frame_for_session_id(s_id)
        except Exception as exc:
            self._window.show_error("Next Frame Failed", str(exc))

    @Slot()
    def on_previous_frame(self) -> None:
        """
        Advance to the previous frame in the selected session.
    
        Note:
            Triggered by transport panel ``previous_btn.clicked`` signal.
    
            Flow:
                on_previous_frame() [this slot]
                  ├── Stop current playback
                  ├── Load previous frame via App
                  └──> Render frame via Controller
        """
        s_id = self.selected_s_id
        if not s_id:
            return
        try:
            self.stop_playback()
            # self._controller.active_session_id = s_id
            self._app.load_previous_frame(s_id)
            self._controller.render_frame_for_session_id(s_id)
        except Exception as exc:
            self._window.show_error("Previous Frame Failed", str(exc))

    def on_seek(self, frame_index: int) -> None:
        """
        Seek to a specific frame index via slider movement.
    
        Note:
            Triggered by transport panel ``seek_slider`` ``sliderMoved`` signal.
    
            Flow:
                on_seek(frame_index) [this method]
                  ├── Stop any active playback
                  ├── Load frame at ``frame_index`` via App
                  └──> Render frame via Controller
        """
        s_id = self.selected_s_id
        if not s_id:
            return
        try:
            self.stop_playback()
            # self._controller.active_session_id = s_id
            self._app.load_frame_by_index(s_id, frame_index)
            self._controller.render_frame_for_session_id(s_id)

        except Exception as exc:
            self._window.show_error("Seek Failed", str(exc))

    @Slot()
    def on_playback_tick(self) -> None:
        """
        Periodic timer callback to update frame during playback.
    
        Note:
            Triggered by ``_playback_timer.timeout`` signal at regular intervals.
    
            Flow:
                on_playback_tick() [this slot]
                  ├── Check if session is still selected
                  ├── Check if at last frame (stop if true)
                  ├── Check if buffered frame is available
                  ├── If available: render frame
                  └── If not: skip frame to maintain sync (buffer underrun)
    
            Why this matters:
                Called every 16ms (or configured interval) during playback.
                Pulls pre-buffered frames from ``VideoDecodeWorker``.
                Skips frames if buffer underruns to prevent stutter.
                Stops playback automatically at end of video.
        """
        s_id = self.selected_s_id
        if not s_id:
            self.stop_playback()
            return

        try:
            # self._controller.active_session_id = s_id
            if self._app.is_at_last_frame(s_id):
                self.stop_playback()
                return

            # ====================================================================
            # 1. CHECK IF BUFFERED FRAME IS AVAILABLE
            # ====================================================================
            has_frame = self._app.session_has_buffered_frame(s_id)

            if has_frame:
                # ================================================================
                # 2. FRAME AVAILABLE — RENDER IT
                # ================================================================
                self._controller.render_frame_for_session_id(s_id)
            else:
                # ================================================================
                # 3. BUFFER UNDERRUN — SKIP THIS TICK
                # ================================================================
                # [NOTE] The ``VideoDecodeWorker`` is falling behind (CPU spike).
                # Skip this frame and let the timer fire again in 16ms.
                logger.trace("Buffer empty, dropping frame tick to maintain sync.")
        except Exception as exc:
            self.stop_playback()
            logger.opt(exception=exc).error("Playback tick failed")

    def _start_session_playback(self, s_id: SessionId) -> None:
        """
        Initialize and start playback for the specified session.
    
        Note:
            Flow:
                _start_session_playback(s_id)
                  ├── Tell App to start playback view_state for session
                  ├── Fetch frame interval (milliseconds) from App metadata
                  ├── Start QTimer with calculated interval
                  └──> Update UI status bar with playback info
    
            Key Steps:
                Notify App that session is starting playback (marks ``is_playing=True``).
                Calculate ``interval`` from FPS metadata (e.g., 30 fps → 33.33 ms).
                Start ``_playback_timer`` which triggers ``on_playback_tick()`` every interval.
                Update status bar to reflect playback view_state.
        """
        # ====================================================================
        # 1. NOTIFY APP TO START PLAYBACK STATE
        # ====================================================================
        self._app.start_session_playback(s_id)

        # ====================================================================
        # 2. CALCULATE FRAME INTERVAL AND START TIMER
        # ====================================================================
        interval = self._app.get_session_frame_interval_ms(s_id)
        self._playback_timer.start(interval)
        logger.trace("Started playback timer with interval: {} ms", interval)

        # ====================================================================
        # 3. UPDATE UI STATUS BAR
        # ====================================================================
        self._controller.update_ui_status_bar()

    def stop_playback(self) -> None:
        """
        Stop video playback and reset playback timer.
    
        Note:
            Flow:
                stop_playback()
                  ├── Stop the QTimer (stops on_playback_tick() calls)
                  ├── Notify App to stop all playback
                  └──> Update UI status bar
        """
        # ====================================================================
        # 1. STOP PLAYBACK TIMER
        # ====================================================================
        self._playback_timer.stop()

        # ====================================================================
        # 2. STOP APP PLAYBACK
        # ====================================================================
        self._app.stop_all_playback()

        # ====================================================================
        # 3. UPDATE UI STATUS BAR
        # ====================================================================
        active_s_id = self.selected_s_id
        if active_s_id:
            self._controller.update_ui_status_bar()
