from __future__ import annotations

from typing import TYPE_CHECKING, final, override

from PySide6.QtCore import Slot, QObject




from app.infrastructure.detection.model.helpers import get_available_detection_model_names_as_view_model
from app.shared import get_logger
from app.ui.adapters import UIApplicationAdapter, UIControllerAdapter
from app.ui import handlers
from app.ui.view_state.table_key_filter import FrameTableKeyFilter
if TYPE_CHECKING:
    from PySide6.QtWidgets import QApplication, QTableWidget
    from app.domain.base.dtypes import ListOfBoxes
    from app.domain import SessionId, VideoDataLayerGroup
    from app.ui.qt.dialogs import EditAnnotationDialog, ModelChangeWarningDialog



if TYPE_CHECKING:
    from app.application.application import Application
    from app.ui.qt.window import Window
    from app.infrastructure.session.session import Session
logger = get_logger("UI->Controller")


@final
class UIController(QObject):
    """
    Central coordinator for all UI operations and handler management.

    Responsibilities:
        - Initialize and own all UI handlers (playback, detection, tracking, detection, export, etc.).
        - Coordinate handler signal connections and event flow.
        - Provide unified interface for handlers to access app and window.
        - Manage Qt application lifecycle (initialization, shutdown).
        - Route frame render requests to UIHandler.
        - Manage data table event filtering (keyboard shortcuts).
        - Handle critical Qt events (close, quit).

    Note:
        Acts as the bridge between App (application/business logic) and Qt UI layer.
        Does NOT inherit from App (circular dependency prevention).
        Delegates handler ownership and coordination.
        Delegates frame rendering to UIHandler.
        Handlers communicate through the controller, never directly to each other.

        Signal flow:
            Qt events (clicks, signals) → Handlers (via signal connections).
            Handlers call controller methods for coordination.
            Controller triggers frame renders, status updates, dialog creation.
            Handlers NEVER talk to each other directly (avoid coupling).
    """

    def __init__(
        self,
        q_app: QApplication,
        window: Window,
        app: Application,
    ) -> None:
        logger.info("Initializing UI Controller...")
        super().__init__()

        # ====================================================================
        # [NOTE] CIRCULAR DEPENDENCY PREVENTION
        # ====================================================================
        # We did NOT pass ``parent=App`` in the super().__init__() call because
        # ``Application`` is imported ONLY for TYPE CHECKING. Directly importing ``Application``
        # at runtime would create a circular dependency. Instead, we use the
        # ``setParent()`` method to assign the parent reference at runtime.
        self.setParent(app)

        # Long-lived collaborators.
        self.q_app = q_app
        self.window = window
        self.app = app
        self.ui_app = UIApplicationAdapter(app)
        self.ui_controller = UIControllerAdapter(self)

        # HANDLERS
        # These only talk to their boss, i.e., the UI Controller.
        # They may also talk to the window and the app instance, since they are
        # owned by their boss.
        # HOWEVER, they should NOT talk to each other.
        self.annotation_handler = handlers.AnnotationHandler(self)
        self.detection_handler = handlers.DetectionHandler(self)
        self.dialogue_handler = handlers.DialogueHandler(self)
        self.export_handler = handlers.ExportHandler(self)
        self.import_export_handler = handlers.ImportExportHandler(self)
        self.model_handler = handlers.ModelHandler(self)
        self.playback_handler = handlers.PlaybackHandler(self)
        self.preferences_handler = handlers.PreferencesHandler(self)
        self.project_handler = handlers.ProjectHandler(self)
        self.session_handler = handlers.SessionHandler(self)
        self.tracking_handler = handlers.TrackingHandler(self)
        self.ui_handler = handlers.UIHandler(self)

        self._frame_table_key_filter = FrameTableKeyFilter(
            self.annotation_handler, self.ui_handler.render_saved_frame
        )

        self._finalize_init()
        self._connect_signals()

    @override
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}>"

    def _connect_signals(self) -> None:
        """
        Wire up critical Qt signals for application lifecycle and UI events.
    
        Note:
            Connections:
                ``QApplication.aboutToQuit`` → ``on_about_to_quit()`` (cleanup).
                ``transport_panel.seek_pos_changed`` → ``on_seek_requested()`` (seek slider).
                ``tool_mode_changed`` → ``preview_container.set_tool_mode()`` (detection mode).
        """
        logger.info("Connecting UI Controller signals...")

        # ====================================================================
        # 1. APPLICATION LIFECYCLE
        # ====================================================================
        self.q_app.aboutToQuit.connect(self.on_about_to_quit)

        # ====================================================================
        # 2. TRANSPORT CONTROLS
        # ====================================================================
        self.window.transport_panel.seek_pos_changed.connect(self.on_seek_requested)

        # ====================================================================
        # 3. PREVIEW CONTAINER AND TOOL MODE
        # ====================================================================
        self.window.tool_mode_changed.connect(self.window.preview_container.set_tool_mode)

    def _finalize_init(self) -> None:
        """
        Complete UI initialization after handler creation.
    
        Note:
            Tasks:
                Install close request handler.
                Install keyboard event filter for data tables.
                Populate detection model dropdown with available model.
                Set initial model selection to "None".
        """
        # ====================================================================
        # 1. REGISTER CLOSE REQUEST HANDLER
        # ====================================================================
        self.window.set_close_request_handler(self.on_close_requested)

        # ====================================================================
        # 2. INSTALL KEYBOARD EVENT FILTER FOR ANNOTATION SHORTCUTS
        # ====================================================================
        # [NOTE] Filters keyboard events (arrow keys for nudge, etc.)
        self.window.installEventFilter(self._frame_table_key_filter)
        self.detection_tab_data_table.installEventFilter(self._frame_table_key_filter)
        self.tracker_tab_data_table.installEventFilter(self._frame_table_key_filter)

        # ====================================================================
        # 3. POPULATE MODEL DROPDOWN
        # ====================================================================
        available_models = get_available_detection_model_names_as_view_model()
        self.window.set_detection_model_boxes(available_models)
        self.window.set_selected_detection_model("None")

    @property
    def active_session(self) -> Session | None:
        return self.app.active_session

    @property
    def detection_tab_data_table(self) -> QTableWidget:
        return self.window.bottom_panel.detection_tab_frame_data_table

    @property
    def tracker_tab_data_table(self) -> QTableWidget:
        return self.window.bottom_panel.tracker_tab_frame_data_table

    def create_edit_annotation_dialogue(
        self, initial_label: str, initial_bbox_xyxy: tuple[int, int, int, int]
    ) -> EditAnnotationDialog:
        return self.dialogue_handler.handle_edit_annotation_dialogue(
            initial_label=initial_label, initial_bbox_xyxy=initial_bbox_xyxy
        )

    def create_model_change_warning_dialog(self, s_id: SessionId) -> ModelChangeWarningDialog:
        return self.dialogue_handler.handle_model_change_warning_dialogue(s_id)

    @Slot()
    def on_about_to_quit(self) -> None:
        """
        Handle application shutdown cleanup.

        Note:
            Triggered by ``QApplication.aboutToQuit`` signal (before main window closes).

            Flow:
                on_about_to_quit() [this slot]
                  ├── Stop active playback (if running)
                  ├── Wait for active exports to finish
                  ├── Close App instance (saves state, cleans up sessions)
                  └──> Close model load thread (if running)

            Graceful Shutdown:
                Ensures playback stops before closing.
                Waits for exports to complete before exiting.
                Properly closes App and cleans up resources.
                Handles case where no session is active (LookupError).
        """
        logger.debug("About to quit.")

        # ====================================================================
        # 1. STOP PLAYBACK
        # ====================================================================
        try:
            self.playback_handler.stop_playback()
        except LookupError:
            logger.opt(exception=True).info("Tried to stop playback with no active session while closing")

        # ====================================================================
        # 2. WAIT FOR EXPORTS TO COMPLETE
        # ====================================================================
        self.export_handler.stop_exports(wait=True)

        # ====================================================================
        # 3. CLOSE APP (SAVES STATE, CLEANS UP SESSIONS)
        # ====================================================================
        self.app.close()

        # ====================================================================
        # 4. CLOSE MODEL LOAD THREAD
        # ====================================================================
        self.model_handler.close()

    @Slot()
    def on_close_requested(self) -> bool:
        """
        Handle main window close request (checks if export in progress).

        Returns:
            bool: ``True`` — Allow window to close. ``False`` — Prevent window from closing (user cancelled).

        Note:
            Triggered by ``MainWindow.closeEvent`` → ``set_close_request_handler()``.

            Flow:
                on_close_requested() [this slot]
                  ├── Check if export currently in progress
                  ├── If no export: allow close
                  └── If export: ask user for confirmation
                      ├── If user confirms: cancel export (wait), then allow close
                      └── If user declines: prevent close

            Safety: Prevents accidental data loss by prompting before closing during export.
        """
        # ====================================================================
        # 1. CHECK IF EXPORT IN PROGRESS
        # ====================================================================
        if not self.export_handler.is_exporting:
            return True

        # ====================================================================
        # 2. ASK USER FOR CONFIRMATION IF EXPORT RUNNING
        # ====================================================================
        if not self.window.confirm_export_in_progress_exit():
            return False

        # ====================================================================
        # 3. CANCEL EXPORT AND WAIT FOR COMPLETION
        # ====================================================================
        self.window.set_status_text("Cancelling export...")
        self.export_handler.stop_exports(wait=True)
        return True

    @Slot(int)
    def on_seek_requested(self, idx: int) -> None:
        """
        Handle seek slider position change from transport panel.

        Note:
            Triggered by ``transport_panel.seek_pos_changed`` signal.

            Delegates To: ``PlaybackHandler.on_seek(idx)`` for actual seeking.
        """
        self.playback_handler.on_seek(idx)

    def render_frame_for_session_id(self, s_id: SessionId) -> None:
        self.ui_handler.render_saved_frame(s_id)

    def set_ui_data_tab_frame_boxes(self, tab: VideoDataLayerGroup, boxes: ListOfBoxes) -> None:
        self.ui_handler.set_boxes_for_tab(boxes, tab)

    def update_ui_status_bar(self):
        self.ui_handler.update_status_bar()
