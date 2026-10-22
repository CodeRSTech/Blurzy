"""Module for uicontroller; presents application behavior to users.

See Also:
    - [`Application`][app.application.application.Application] — supplies application workflows
    - [`UIControllerInterface`][app.ui.interfaces.controller_interface.UIControllerInterface] — defines the handler-facing controller contract

Layer: Presentation.
Context: Presents application behavior to users at this architectural boundary.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, final, override

from PySide6.QtCore import Slot, QObject

from app.infrastructure.detection.model.helpers import get_detection_model_names_as_view_model_by_provider_id
from app.shared import get_logger

if TYPE_CHECKING:
    from PySide6.QtWidgets import QApplication, QTableWidget
    from app.application.application import Application
    from app.domain.base.dtypes import ListOfBoxes
    from app.domain import SessionId, VideoDataLayerGroup
    from app.infrastructure.session.session import Session
    from app.ui.qt.dialogs import EditAnnotationDialog, ModelChangeWarningDialog
    from app.ui.qt.window import Window

logger = get_logger("UI->Controller")


@final
class UIController(QObject):
    """
    Central coordinator for all UI operations and handler management.
    Acts as the bridge between App (application/business logic) and Qt UI layer.

    Responsibilities:
        - Initialize and own all UI handlers (playback, detection, tracking, detection, export, etc.).
        - Coordinate handler signal connections and event flow.
        - Provide unified interface for handlers to access app and window.
        - Manage Qt application lifecycle (initialization, shutdown).
        - Route frame render requests to UIHandler.
        - Manage data table event filtering (keyboard shortcuts).
        - Handle critical Qt events (close, quit).

    Note:
        Does NOT inherit from App (circular dependency prevention).
        Delegates handler ownership and coordination, frame rendering, and status updates.
        Handlers communicate through the controller, never directly to each other (avoid coupling).

        Signal flow:
            Qt events (clicks, signals) → Handlers (via signal connections).
            Handlers call controller methods for coordination.
            Controller triggers frame renders, status updates, dialog creation.


Layer: Presentation.
Context: Supports user interaction and delegates application work through presentation contracts.


    Args:
        q_app: Qt application instance.
        window: Window instance used by this component.
        app: Application facade exposed to UI handlers and adapters for session and settings operations.
"""

    def __init__(self, q_app: QApplication, window: Window, app: Application, ) -> None:
        logger.info("Initializing UI Controller...")

        from app.ui import handlers, adapters
        from app.ui.view_state.table_key_filter import FrameTableKeyFilter

        # ====================================================================
        # [NOTE] CIRCULAR DEPENDENCY PREVENTION
        # ====================================================================
        # We do NOT pass `parent=App` in the `super().__init__()` call because
        # `Application` is imported TYPE CHECKING only.
        # Directly importing `Application` at runtime would create a circular dependency.
        # Instead, we use `setParent()` to assign the parent ref at runtime.
        super().__init__()
        self.setParent(app)

        # Long-lived collaborators.
        self.q_app = q_app
        self.window = window
        self.app = app
        self.ui_app = adapters.UIApplicationAdapter(app)
        self.ui_controller = adapters.UIControllerAdapter(self)

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

        # ====================================================================
        # Complete UI initialization after handler creation.
        # ====================================================================

        # 1. REGISTER CLOSE REQUEST HANDLER
        self.window.set_close_request_handler(self.on_close_requested)

        # 2. INSTALL KEYBOARD EVENT FILTER FOR ANNOTATION SHORTCUTS
        # [NOTE] Filters keyboard events (arrow keys for nudge, etc.)
        self.window.installEventFilter(self._frame_table_key_filter)
        self.detection_tab_data_table.installEventFilter(self._frame_table_key_filter)
        self.tracker_tab_data_table.installEventFilter(self._frame_table_key_filter)

        # 3. POPULATE MODEL DROPDOWN
        available_models = get_detection_model_names_as_view_model_by_provider_id()
        self.window.set_detection_model_boxes(available_models)
        self.window.set_selected_detection_model("None")

        # ====================================================================
        # Wire up critical Qt signals for application lifecycle and UI events.
        # ====================================================================

        # 1. APPLICATION LIFECYCLE
        self.q_app.aboutToQuit.connect(self.on_about_to_quit)

        # 2. TRANSPORT CONTROLS
        self.window.transport_panel.seek_pos_changed.connect(self.on_seek_requested)

        # 3. PREVIEW CONTAINER AND TOOL MODE
        self.window.tool_mode_changed.connect(self.window.preview_container.set_tool_mode)

    @override
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}>"

    @property
    def active_session(self) -> Session | None:
        """Return the currently active session, if any.

        Returns:
            Active session, or `None` when no session is selected.
        """
        return self.app.active_session

    @property
    def detection_tab_data_table(self) -> QTableWidget:
        """Return the detection-layer table shown in the bottom panel.

        Returns:
            Detection table widget.
        """
        return self.window.bottom_panel.detection_tab_frame_data_table

    @property
    def tracker_tab_data_table(self) -> QTableWidget:
        """Return the tracking-layer table shown in the bottom panel.

        Returns:
            Tracking table widget.
        """
        return self.window.bottom_panel.tracker_tab_frame_data_table

    def create_edit_annotation_dialogue(
            self,
            initial_label: str,
            initial_bbox_xyxy: tuple[int, int, int, int]
    ) -> EditAnnotationDialog:
        """
        Create and return an `EditAnnotationDialog` with the given initial label and bounding box.
        """
        return self.dialogue_handler.handle_edit_annotation_dialogue(
            initial_label=initial_label, initial_bbox_xyxy=initial_bbox_xyxy
        )

    def create_model_change_warning_dialog(self, s_id: SessionId) -> ModelChangeWarningDialog:
        """Create model change warning dialog.

        Args:
            s_id: Session whose detection model would be changed.

        Returns:
            Dialog describing the consequences of changing that model.
        """
        return self.dialogue_handler.handle_model_change_warning_dialogue(s_id)

    @Slot()
    def on_about_to_quit(self) -> None:
        """
        Handle application shutdown cleanup.

        Note:
            Triggered by `QApplication.aboutToQuit` signal (before main window closes).

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
            bool: `True` — Allow window to close. `False` — Prevent window from closing (user cancelled).

        Note:
            Triggered by `MainWindow.closeEvent` → `set_close_request_handler()`.

            Flow:

            `on_close_requested()` `[this slot]`
              |    ├── Check if export currently in progress
              |    ├── If no export: allow close
              |    └── If export: ask user for confirmation
              |        ├── If user confirms: cancel export (wait), then allow close
              |        └── If user declines: prevent close

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
            Triggered by `transport_panel.seek_pos_changed` signal.

            Delegates To: `PlaybackHandler.on_seek(idx)` for actual seeking.
        """
        self.playback_handler.on_seek(idx)

    def render_frame_for_session_id(self, s_id: SessionId) -> None:
        """
        Render the saved frame for the given session ID.

        Note:
            Delegates to `UIHandler.render_saved_frame(s_id)` for actual rendering.
        """
        self.ui_handler.render_saved_frame(s_id)

    def set_ui_data_tab_frame_boxes(self, tab: VideoDataLayerGroup, boxes: ListOfBoxes) -> None:
        """Display frame boxes in the specified detection or tracking table.

        Args:
            tab: Data-layer table to update.
            boxes: Boxes to display in that table.
        """
        self.ui_handler.set_boxes_for_tab(boxes, tab)

    def update_ui_status_bar(self):
        """Update ui status bar."""
        self.ui_handler.update_status_bar()
