"""Session management handler for UI layer."""

from __future__ import annotations

from typing import TYPE_CHECKING


from typing import final, TYPE_CHECKING, override

from PySide6.QtCore import Slot, Qt, QObject


from app.infrastructure.views.view_models import list_of_session_list_view_models
from app.shared.exceptions import (
    NoNewOpenedSessionsException,
    SessionAlreadyExistsException,
    VideoFileOpenException,
    VideoStreamStateException,
)
from app.shared.logging_cfg import get_logger
if TYPE_CHECKING:
    from app.domain.session import SessionId


if TYPE_CHECKING:
    from app.ui.uicontroller import UIController

logger = get_logger("UI->SessionHandler")


@final
class SessionHandler(QObject):
    """Orchestrate session lifecycle events and UI synchronization.

    Responsibilities:
        - Handle video file loading and session creation.
        - Manage active-session switching.
        - Synchronize session view_state with UI widgets.
        - Coordinate playback initialization on session load.

    Notes:
        Signal flow:
            - Receives signals from ``MainWindow`` (file selection/menu) and
              ``BottomPanel`` (session selection).
            - Delegates to ``Application`` and ``UIController`` to perform actions.
            - Triggers UI updates to reflect session view_state changes.
    """

    def __init__(self, controller: UIController) -> None:
        """Initialize the session handler with UI controller dependencies."""
        super().__init__()
        self.setParent(controller)
        self._controller = controller
        self._app = controller.app
        self._window = controller.window
        self.update_video_related_widgets_state()
        self._connect_signals()
        logger.debug("SessionHandler initialized.")

    @override
    def __repr__(self) -> str:
        """Return a concise representation of the SessionHandler instance."""
        return f"<{self.__class__.__name__}>"

    def _connect_signals(self) -> None:
        """Wire all upstream signals to their corresponding slots."""
        # ====================================================================
        # 1. CONNECT MAIN WINDOW SIGNALS
        # ====================================================================
        self._controller.window.open_videos_requested.connect(
            self.on_open_videos
        )

        # ====================================================================
        # 2. CONNECT BOTTOM PANEL SIGNALS
        # ====================================================================
        # [NOTE] ``BottomPanel.session_list.itemSelectionChanged`` emits
        # ``session_selected`` signal
        self._controller.window.bottom_panel.session_selected.connect(
            self.on_session_selected
        )

    # ═══════════════════════════════════════════════════════════════
    #                          SLOT: ON_OPEN_VIDEOS
    # ═══════════════════════════════════════════════════════════════

    @Slot(list)
    def on_open_videos(self, paths: list[str]) -> None:
        """Receive file paths and create new sessions for each video.

        Args:
            paths (list[str]): Video file paths selected by the user.

        Notes:
            Signal cascade (complete flow):
                1. ``MainWindow`` File menu ``Open Videos`` action triggers file selection UI.
                2. ``MainWindow._choose_video_files()`` emits ``open_videos_requested(paths)``.
                3. ``SessionHandler.on_open_videos(paths)`` receives the signal.
                4. Existing playback is stopped.
                5. ``App.open_videos(paths)`` creates sessions via session manager.
                6. New sessions are adopted for parent-managed cleanup.
                7. Session list widget is refreshed.
                8. Video-related widgets are enabled.
                9. Active session is selected and seek-complete hookup is attached.

            Triggered by:
                ``MainWindow.open_videos_requested`` carrying ``list[str]``.

            Effects:
                - Prevents playback conflicts.
                - Delegates session creation to application layer.
                - Synchronizes newly created sessions into UI view_state.

            Downstream:
                May indirectly trigger ``on_session_selected()`` when active
                session view_state updates.
        """
        try:
            logger.debug("Opening {} video(s)", len(paths))

            # ====================================================================
            # 1. STOP ALL EXISTING PLAYBACK
            # ====================================================================
            self._app.stop_all_playback()

            # ====================================================================
            # 2. DELEGATE TO APP TO OPEN VIDEOS AND CREATE SESSIONS
            # ====================================================================
            # [NOTE] ``App.open_videos()`` cascades to ``SessionManager``, which
            # creates ``Session`` instances for each video path
            self._app.open_videos(paths)

            # ====================================================================
            # 3. ADOPT ORPHANED SESSIONS (PARENT MANAGEMENT)
            # ====================================================================
            # [NEW] ``SessionHandler`` adopts (sets itself as parent of) each
            # ``Session`` without a parent. This ensures proper cleanup when
            # ``SessionHandler`` is deleted.
            sessions = self._controller.app.sm.all_sessions
            for session in sessions:
                if session.parent() is None:
                    session.setParent(self)

            # ====================================================================
            # 4. UPDATE SESSION LIST WIDGET
            # ====================================================================
            # Convert ``Session`` instances to view model and update the UI list
            self._controller.window.bottom_panel.update_session_file_list(
                list_of_session_list_view_models(sessions=sessions)
            )

            # ====================================================================
            # 5. ENABLE VIDEO-RELATED WIDGETS
            # ====================================================================
            # Make video controls available now that sessions exist
            self.update_video_related_widgets_state(is_enabled=True)

            # ====================================================================
            # 6. SET ACTIVE SESSION AND CONNECT PLAYBACK SIGNALS
            # ====================================================================
            # Select the active session in the list and connect seek signals
            active = self._controller.app.active_session
            if active is not None:
                self._controller.window.bottom_panel.selected_s_id = active.s_id
                # [NOTE] ``SingleShotConnection`` ensures this slot fires only once
                # per seek operation (initial frame render on load)
                active.video_decode_worker.signals.seek_completed.connect(
                    self.on_video_seek_completed, Qt.ConnectionType.SingleShotConnection
                )

        except NoNewOpenedSessionsException as exc:
            self._controller.window.show_info(title="Error!", msg=str(exc))
            logger.info("Error while opening video(s)")
        except (SessionAlreadyExistsException, VideoFileOpenException, VideoStreamStateException) as exc:
            self._controller.window.show_error("Open Video(s) Failed!", str(exc))
            logger.warning("Failed to open selected video(s): {}", exc)
        except Exception as exc:
            self._controller.window.show_error("Open Video(s) Failed!", str(exc))
            logger.opt(exception=exc).error("Failed to open videos")

    # ═══════════════════════════════════════════════════════════════
    #                        SLOT: ON_SESSION_SELECTED
    # ═══════════════════════════════════════════════════════════════

    @Slot(object)
    def on_session_selected(self, s_id: SessionId) -> None:
        """Switch active session and restore UI view_state for the selected session.

        Args:
            s_id (SessionId): Identifier for the session to activate.

        Notes:
            Triggered by:
                ``BottomPanel.session_selected`` carrying ``SessionId``.

            Effects:
                - Stops playback in the previously active session.
                - Sets selected session as active.
                - Restores session settings in UI controls.
                - Renders initial frame for the selected session.

            Downstream:
                None. This slot is a leaf UI update operation.
        """
        logger.info("Session selected: {}", s_id)

        try:
            # ====================================================================
            # 1. STOP PLAYBACK IN CURRENT SESSION
            # ====================================================================
            self._controller.playback_handler.stop_playback()

            # ====================================================================
            # 2. SET AS ACTIVE SESSION
            # ====================================================================
            self._controller.app.active_session_id = s_id

            # ====================================================================
            # 3. RESTORE SESSION SETTINGS TO UI
            # ====================================================================
            # Fetch settings view model and update all UI controls
            settings_vm = self._controller.app.get_session_settings(s_id)
            self._controller.window.restore_session_settings(settings_vm)

            # ====================================================================
            # 4. RENDER INITIAL FRAME
            # ====================================================================
            self._controller.render_frame_for_session_id(s_id)

        except (VideoFileOpenException, VideoStreamStateException) as exc:
            self._controller.window.show_error(
                title="Session Load Failed", msg=str(exc)
            )
            logger.warning("Failed to load session due to video view_state error: {}", exc)
        except Exception as exc:
            self._controller.window.show_error(
                title="Session Load Failed", msg=str(exc)
            )
            logger.opt(exception=exc).error("Failed to load session")

    # ═══════════════════════════════════════════════════════════════
    #                     SLOT: ON_VIDEO_SEEK_COMPLETED
    # ═══════════════════════════════════════════════════════════════

    @Slot(int)
    def on_video_seek_completed(self, index: int) -> None:
        """Render initial frame after seek completion if playback is paused.

        Args:
            index (int): Frame index emitted by decode worker on seek completion.

        Notes:
            Triggered by:
                ``VideoDecodeWorker.signals.seek_completed`` connected with
                ``Qt.ConnectionType.SingleShotConnection``.

            Effects:
                - If playback is paused, forces one manual frame render.
                - If playback is already running, avoids redundant redraw.

            Why single-shot:
                - Ensures this slot fires once for initial frame readiness.
                - Prevents duplicate first-frame render behavior.
        """
        logger.info("Rendering video frame at index: {}", index)
        active = self._controller.app.active_session
        if active:
            # ====================================================================
            # 1. CHECK PLAYBACK STATE
            # ====================================================================
            # [NOTE] We only force a manual redraw if the video is paused.
            # If the user clicked Play before the worker finished loading the
            # first frame, the ``QTimer`` is already polling the buffer.
            if not active.state.playback.is_playing:
                # ================================================================
                # 2. FORCE FRAME RENDER
                # ================================================================
                self._controller.render_frame_for_session_id(active.s_id)

    # ═══════════════════════════════════════════════════════════════
    #                      HELPER METHOD: UPDATE WIDGETS STATE
    # ═══════════════════════════════════════════════════════════════

    def update_video_related_widgets_state(self, is_enabled: bool = False) -> None:
        """Enable or disable video-related widgets across UI panels.

        Args:
            is_enabled (bool): True to enable controls, False to disable.

        Notes:
            Called during startup (disabled) and after video load (enabled).
            Propagates view_state to bottom, right, and transport panels.
        """
        # ====================================================================
        # 1. UPDATE BOTTOM PANEL WIDGETS
        # ====================================================================
        self._controller.window.bottom_panel.update_video_related_widgets_state(
            is_enabled
        )

        # ====================================================================
        # 2. UPDATE RIGHT PANEL WIDGETS
        # ====================================================================
        self._controller.window.right_panel.update_video_related_widgets_state(
            is_enabled
        )

        # ====================================================================
        # 3. UPDATE TRANSPORT PANEL WIDGETS
        # ====================================================================
        self._controller.window.transport_panel.update_video_related_widgets_state(
            is_enabled
        )

        # [TODO] Move this logic to ``UIController`` which will delegate
        # to ``UIHandler`` for better separation of concerns
