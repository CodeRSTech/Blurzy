"""Tracking configuration and execution handler for multi-object tracking."""

from __future__ import annotations

from typing import TYPE_CHECKING, Unpack, final, override

from PySide6.QtCore import Slot, QObject

from app.domain import VideoDataLayer
from app.domain.base.dtypes import ProcessingSettingsKwargs
from app.domain.session.session_id import SessionId
from app.domain.tracking.tracking_strategy import TrackingStrategy
from app.shared.exceptions import InvalidSessionIdException
from app.shared.logging_cfg import get_logger

if TYPE_CHECKING:
    from app.ui.interfaces import UIControllerInterface, UIApplicationInterface
    from app.ui.qt.main_window import MainWindow
    from app.ui.uicontroller import UIController

logger = get_logger("UI->TrackingHandler")


@final
class TrackingHandler(QObject):
    """
    Manages object tracking configuration and execution.

    Responsibilities:
        - Start background tracking worker with user-selected strategy.
        - Handle tracking source selection (which detection layer to track).
        - Update tracking parameters (IoU threshold, confidence, decay).
        - Monitor tracking worker progress and completion.
        - Display tracking results in UI.

    Note:
        Signal flow:
            Receives signals from right panel (start tracking, strategy, source, parameters).
            Emits tracking worker finished/failed signals to update UI.
            Triggers frame re-render after tracking completion.

        Validates that active session matches selected session before starting.
        Prevents tracking if detection worker is running.
        Shows configuration warning if tracking overlaps with detections.
    """

    def __init__(self, controller: UIController) -> None:
        super().__init__(parent=controller)
        self._owner = controller
        self._controller: UIControllerInterface = controller.ui_controller
        self._window: MainWindow = controller.window
        self._app: UIApplicationInterface = controller.ui_app

        self._connect_signals()

    @override
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}>"

    def _connect_signals(self) -> None:
        logger.debug("Connecting signals to tracker handler.")
        right_panel = self._window.right_panel

        right_panel.start_tracking_requested.connect(self.on_start_tracking)
        right_panel.tracking_strategy_changed.connect(self.on_strategy_changed)
        right_panel.tracking_source_changed.connect(self.on_source_changed)
        right_panel.min_iou_spinbox.valueChanged.connect(self.on_min_iou_changed)
        right_panel.min_tracker_confidence_spinbox.valueChanged.connect(
            self.on_min_tracker_confidence_changed
        )
        right_panel.confidence_decay_spinbox.valueChanged.connect(self.on_confidence_decay_changed)

    def _update_processing_settings_and_warn(self, **kwargs: Unpack[ProcessingSettingsKwargs]) -> None:
        # [AUDIT] SRP VIOLATION: Method does 4 distinct things
        # 1. Validate session ID (validation concern) [fixed]
        # 2. Update settings (state mutation concern)
        # 3. Check for existing tracking data (query concern)
        # 4. Show warning message (UI presentation concern)
        # Recommendation: Split into separate methods:
        #   - _validate_session_id() → raises exception or returns validated ID
        #   - _update_settings(s_id, **kwargs) → pure state update
        #   - _warn_if_tracking_data_exists(s_id) → check and show warning if needed
        # This improves clarity, reusability, and testability.
        # New: used key=value as arg for **kwargs and passed that into update_session_settings
        s_id = self._window.selected_s_id
        if not s_id:
            # raise InvalidSessionIdException(message="Error while attempting to update tracking/processing settings.",
            #                                 session_id=s_id)
            return

        self._app.update_session_settings(s_id, **kwargs)

        active_session = self._app.active_session
        if active_session and active_session.has_boxes_for_layer(VideoDataLayer.C):
            self._window.set_tracking_config_warning_visible(True)

    @Slot(str, object)
    def on_start_tracking(self, strategy_name: str, source_layer_name: VideoDataLayer) -> None:
        """
        Start background tracking for detected objects.
    
        Note:
            Triggered by right panel ``start_tracking_requested`` signal.
    
            Flow:
                on_start_tracking(strategy, source) [this slot]
                  ├── Validate selected and active sessions match
                  ├── Check that detection is not currently running
                  ├── Set UI to loading state
                  ├── Start TrackingWorker in background
                  └──> Connect worker signals for progress/completion
    
            Safety Checks:
                Session ID must be selected.
                Active session must match selected session.
                Tracking worker must not already be running.
                Display error dialogs if any check fails.
        """
        selected_s_id = self._window.selected_s_id
        logger.info("UI requested tracking start for session '{}' (strategy: {}, source: {})", selected_s_id, strategy_name,
                    source_layer_name)

        # ====================================================================
        # 1. VALIDATE SELECTED SESSION
        # ====================================================================
        if not selected_s_id:
            raise InvalidSessionIdException(message="Error while attempting to start tracking. Session id is None",
                                            session_id=selected_s_id)
        s_id: SessionId = selected_s_id

        # ====================================================================
        # 2. VALIDATE ACTIVE SESSION
        # ====================================================================
        active_s_id = self._app.active_session_id
        if not active_s_id:
            raise InvalidSessionIdException(
                message="Error while attempting to start tracking. Active session id is None",
                session_id=active_s_id
            )

        # ====================================================================
        # 3. CHECK ACTIVE SESSION MATCHES SELECTED SESSION
        # ====================================================================
        if active_s_id != s_id:
            logger.debug("Failed to start tracking: Active session is not the same as the selected session.")
            return

        # ====================================================================
        # 4. CHECK IF TRACKING WORKER ALREADY RUNNING
        # ====================================================================
        if self._app.session_has_running_tracking_worker(s_id):
            logger.debug("Blocked tracking start: Tracking is currently running.")
            self._window.show_error(
                "Action Not Allowed",
                "Please wait for tracking to finish before starting another.",
            )
            return

        try:
            # ================================================================
            # 5. UPDATE UI LOADING STATE
            # ================================================================
            self._window.set_tracking_loading_state(True)
            self._window.set_tracking_progress_busy(True, indeterminate=True)
            self._window.set_status_text("Tracking in progress...")
            self._window.set_tracking_config_warning_visible(False)

            # ================================================================
            # 6. START BACKGROUND TRACKING WORKER
            # ================================================================
            self._app.start_tracking_worker(s_id, strategy_name, source_layer_name)

            # ================================================================
            # 7. CONNECT WORKER SIGNALS FOR PROGRESS/COMPLETION
            # ================================================================
            if self._app.session_has_running_tracking_worker(s_id):
                tracking_worker = self._app.get_session_by_id(s_id).tracking_worker
                tracking_worker.progress_updated.connect(self._on_tracking_progress)
                tracking_worker.finished_processing.connect(lambda: self._on_tracking_finished(s_id))
                tracking_worker.error_occurred.connect(self._on_tracking_failed)
        except Exception as exc:
            self._window.set_tracking_loading_state(False)
            self._window.set_tracking_progress_busy(False)
            self._window.show_error("Tracking Failed!", str(exc))
            logger.opt(exception=exc).error("Failed to start tracking")

    @Slot(str)
    def on_strategy_changed(self, strategy: str) -> None:
        """
        Update tracking strategy and adjust UI visibility accordingly.
    
        Note:
            Triggered by right panel ``tracking_strategy_changed`` signal.
    
            Action:
                Show/hide IoU threshold controls (only for Hungarian strategy).
                Update session settings and show warning if tracking data exists.
        """
        logger.trace("Tracking strategy changed to: {}", strategy)

        # ====================================================================
        # 1. UPDATE IoU WIDGET VISIBILITY BASED ON STRATEGY
        # ====================================================================
        # [NOTE] Only Hungarian strategy uses IoU threshold parameter
        self._window.set_iou_widgets_visible(strategy == TrackingStrategy.HUNGARIAN)

        # ====================================================================
        # 2. UPDATE SESSION SETTINGS
        # ====================================================================
        self._update_processing_settings_and_warn(tracking_strategy=strategy)

    @Slot(str)
    def on_source_changed(self, source: str) -> None:
        """
        Update tracking source layer and reapply tracking configuration.
    
        Note:
            Triggered by right panel ``tracking_source_changed`` signal.
    
            Action: Update session settings and warn if tracking overlaps detection.
        """
        logger.trace("Tracking source changed to: {}", source)
        self._update_processing_settings_and_warn(tracking_source=source)

    @Slot(float)
    def on_min_iou_changed(self, value: float) -> None:
        """
        Update minimum IoU threshold for Hungarian strategy.
    
        Note:
            Triggered by right panel ``min_iou_spinbox.valueChanged`` signal.
        """
        logger.trace("Tracking min_iou changed to: {}", value)
        self._update_processing_settings_and_warn(min_iou=value)

    @Slot(float)
    def on_min_tracker_confidence_changed(self, value: float) -> None:
        """
        Update minimum tracker confidence threshold.
    
        Note:
            Triggered by right panel ``min_tracker_confidence_spinbox.valueChanged`` signal.
        """
        logger.trace("Tracking min_tracker_confidence changed to: {}", value)
        self._update_processing_settings_and_warn(min_tracker_confidence=value)

    @Slot(float)
    def on_confidence_decay_changed(self, value: float) -> None:
        """
        Update confidence decay rate for tracker.
    
        Note:
            Triggered by right panel ``confidence_decay_spinbox.valueChanged`` signal.
        """
        logger.trace("Tracking confidence_decay changed to: {}", value)
        self._update_processing_settings_and_warn(confidence_decay=value)

    @Slot(str)
    def _on_tracking_finished(self, s_id: SessionId) -> None:
        """
        Handle successful completion of tracking worker.
    
        Note:
            Triggered by ``TrackingWorker.finished_processing`` signal.
    
            Flow:
                _on_tracking_finished(s_id) [this slot]
                  ├── Synchronize tracking cache with session
                  ├── Clear loading state in UI
                  └──> Render frame with tracking results
        """
        logger.info("Tracking finished signal received for session '{}'", s_id)

        # ====================================================================
        # 1. SYNC TRACKING CACHE WITH SESSION
        # ====================================================================
        self._app.sync_tracking_cache(s_id)

        # ====================================================================
        # 2. CLEAR LOADING STATE IN UI
        # ====================================================================
        self._window.set_tracking_loading_state(False)
        self._window.set_tracking_progress_busy(False)

        # ====================================================================
        # 3. RENDER FRAME WITH TRACKING RESULTS
        # ====================================================================
        self._controller.render_frame_for_session_id(s_id)

    @Slot(str)
    def _on_tracking_failed(self, error: str) -> None:
        """
        Handle tracking worker failure.
    
        Note:
            Triggered by ``TrackingWorker.error_occurred`` signal.
    
            Action: Clear loading state and show error dialog to user.
        """
        logger.debug("Tracking failed signal received: {}", error)

        # ====================================================================
        # 1. CLEAR LOADING STATE
        # ====================================================================
        self._window.set_tracking_loading_state(False)
        self._window.set_tracking_progress_busy(False)

        # ====================================================================
        # 2. SHOW ERROR DIALOG
        # ====================================================================
        self._window.show_error("Tracking Error", error)

    @Slot(int, int)
    def _on_tracking_progress(self, current: int, total: int) -> None:
        self._window.set_tracking_progress(current, total, "Tracking")
        self._window.set_status_text(f"Tracking in progress: {current}/{total}")
