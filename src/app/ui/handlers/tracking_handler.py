"""
Tracking configuration and execution handler for multi-object tracking.

See Also:
    - [`TrackingService`][app.application.services.tracking.service.TrackingService] — coordinates tracking workflows
    - [`TrackingStrategy`][app.domain.tracking.tracking_strategy.TrackingStrategy] — defines selectable tracking algorithms

Layer: Presentation.
Context: Converts user actions and worker signals into application calls and UI feedback.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, final, override

from PySide6.QtCore import Slot, QObject

from app.domain import VideoDataLayer
from app.domain import VideoDataLayerGroup


from app.domain.tracking.tracking_strategy import TrackingStrategy
from app.shared.exceptions import InvalidSessionIdException
from app.shared.logging_cfg import get_logger
if TYPE_CHECKING:
    from typing import Unpack
    from app.domain.base.dtypes import ProcessingSettingsKwargs
    from app.domain.session.session_id import SessionId


if TYPE_CHECKING:
    from app.ui.interfaces import UIControllerInterface, UIApplicationInterface
    from app.ui.qt.window import Window
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


    Layer: Presentation.
    Context: Supports user interaction and delegates application work through presentation contracts.
    """

    def __init__(self, controller: UIController) -> None:
        """
        Initialize the TrackingHandler.
        Args:
            controller: UIController supplying tracking settings, worker controls, and the active window to this handler.
        """
        super().__init__(parent=controller)
        self._owner = controller
        self._controller: UIControllerInterface = controller.ui_controller
        self._window: Window = controller.window
        self._app: UIApplicationInterface = controller.ui_app

        self._connect_signals()

    @override
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}>"

    def _connect_signals(self) -> None:
        """
        Connect tracking controls to session-setting and worker actions.


        Note:
            Offline stitch settings are stored per session and consumed when a
            tracking worker is created.

        Example:
            handler._connect_signals()
        """
        logger.debug("Connecting signals to tracker handler.")
        right_panel = self._window.right_panel

        right_panel.start_tracking_requested.connect(self.on_start_tracking)
        right_panel.tracking_strategy_changed.connect(self.on_strategy_changed)
        right_panel.tracking_source_changed.connect(self.on_source_changed)
        right_panel.reid_embedding_dim_changed.connect(self.on_reid_embedding_dim_changed)
        right_panel.min_iou_spinbox.valueChanged.connect(self.on_min_iou_changed)
        right_panel.min_tracker_confidence_spinbox.valueChanged.connect(
            self.on_min_tracker_confidence_changed
        )
        right_panel.confidence_decay_spinbox.valueChanged.connect(self.on_confidence_decay_changed)
        right_panel.offline_stitching_checkbox.toggled.connect(
            self.on_offline_stitching_toggled
        )
        right_panel.max_stitch_gap_spinbox.valueChanged.connect(
            self.on_max_stitch_gap_changed
        )
        right_panel.gsi_smoothness_spinbox.valueChanged.connect(
            self.on_gsi_smoothness_changed
        )
        right_panel.privacy_features_enabled_changed.connect(
            self.on_privacy_features_enabled_changed
        )
        right_panel.resist_box_shrinking_changed.connect(
            self.on_resist_box_shrinking_changed
        )
        right_panel.shrink_resistance_changed.connect(self.on_shrink_resistance_changed)
        right_panel.pre_detection_padding_sec_changed.connect(
            self.on_pre_detection_padding_sec_changed
        )
        right_panel.post_detection_padding_sec_changed.connect(
            self.on_post_detection_padding_sec_changed
        )
        right_panel.box_safety_padding_pct_changed.connect(
            self.on_box_safety_padding_pct_changed
        )

    def _update_processing_settings_and_warn(self, **kwargs: Unpack[ProcessingSettingsKwargs]) -> None:
        # [AUDIT] SRP VIOLATION: Method does 4 distinct things
        # 1. Validate session ID (validation concern) [fixed]
        # 2. Update settings (view_state mutation concern)
        # 3. Check for existing tracking data (query concern)
        # 4. Show warning message (UI presentation concern)
        # Recommendation: Split into separate methods:
        #   - _validate_session_id() → raises exception or returns validated ID
        #   - _update_settings(s_id, **kwargs) → pure view_state update
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
            Triggered by right panel `start_tracking_requested` signal.

            Flow:
                on_start_tracking(strategy, source) [this slot]
                  ├── Validate selected and active sessions match
                  ├── Check that detection is not currently running
                  ├── Set UI to loading view_state
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
            Triggered by right panel `tracking_strategy_changed` signal.

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
            Triggered by right panel `tracking_source_changed` signal.

            Action: Update session settings and warn if tracking overlaps detection.
        """
        logger.trace("Tracking source changed to: {}", source)
        self._update_processing_settings_and_warn(tracking_source=source)

    @Slot(int)
    def on_reid_embedding_dim_changed(self, dimension: int) -> None:
        """
        Update the Re-ID embedding dimension for the selected session.

        Args:
            dimension: Embedding vector size selected in the tracking panel.
        Note:
            The panel offers only the dimensions accepted by ProcessingSettings.

        Example:
            handler.on_reid_embedding_dim_changed(256)
        """
        self._update_processing_settings_and_warn(reid_embedding_dim=dimension)

    @Slot(float)
    def on_min_iou_changed(self, value: float) -> None:
        """
        Update minimum IoU threshold for Hungarian strategy.

        Note:
            Triggered by right panel `min_iou_spinbox.valueChanged` signal.
        """
        logger.trace("Tracking min_iou changed to: {}", value)
        self._update_processing_settings_and_warn(min_iou=value)

    @Slot(float)
    def on_min_tracker_confidence_changed(self, value: float) -> None:
        """
        Update minimum tracker confidence threshold.

        Note:
            Triggered by right panel `min_tracker_confidence_spinbox.valueChanged` signal.
        """
        logger.trace("Tracking min_tracker_confidence changed to: {}", value)
        self._update_processing_settings_and_warn(min_tracker_confidence=value)

    @Slot(float)
    def on_confidence_decay_changed(self, value: float) -> None:
        """
        Update confidence decay rate for tracker.

        Note:
            Triggered by right panel `confidence_decay_spinbox.valueChanged` signal.
        """
        logger.trace("Tracking confidence_decay changed to: {}", value)
        self._update_processing_settings_and_warn(confidence_decay=value)

    @Slot(bool)
    def on_offline_stitching_toggled(self, enabled: bool) -> None:
        """
        Update whether post-tracking tracklet stitching is enabled.

        Args:
            enabled: True to enable bidirectional stitching and GSI.
        Raises:
            InvalidSessionIdException: If the application rejects the selected session.

        Note:
            The corresponding gap and smoothness controls are gated by the right panel.

        Example:
            handler.on_offline_stitching_toggled(True)
        """
        self._window.right_panel.set_stitching_controls_enabled(enabled)
        self._update_processing_settings_and_warn(offline_stitching_enabled=enabled)

    @Slot(int)
    def on_max_stitch_gap_changed(self, value: int) -> None:
        """
        Update the maximum number of missed frames eligible for stitching.

        Args:
            value: Gap length from 1 to 60 frames.
        Raises:
            InvalidSessionIdException: If the application rejects the selected session.

        Note:
            The right-panel spin box enforces the supported numeric range.

        Example:
            handler.on_max_stitch_gap_changed(25)
        """
        self._update_processing_settings_and_warn(max_stitch_gap=value)

    @Slot(float)
    def on_gsi_smoothness_changed(self, value: float) -> None:
        """
        Update the Gaussian interpolation lengthscale.

        Args:
            value: Kernel lengthscale from 1.0 to 30.0.
        Raises:
            InvalidSessionIdException: If the application rejects the selected session.

        Note:
            Higher values blend endpoint predictions across a wider temporal range.

        Example:
            handler.on_gsi_smoothness_changed(10.0)
        """
        self._update_processing_settings_and_warn(gsi_smoothness=value)

    @Slot(bool)
    def on_privacy_features_enabled_changed(self, enabled: bool) -> None:
        """
        Update the Privacy Shield master setting for the selected session.

        Args:
            enabled: Whether conservative privacy post-processing is active.

        Example:
            handler.on_privacy_features_enabled_changed(True)
        """
        self._update_processing_settings_and_warn(privacy_features_enabled=enabled)

    @Slot(bool)
    def on_resist_box_shrinking_changed(self, enabled: bool) -> None:
        """
        Update whether track boxes resist sudden size contractions.

        Args:
            enabled: Whether the anti-shrink size envelope is active.

        Example:
            handler.on_resist_box_shrinking_changed(True)
        """
        self._update_processing_settings_and_warn(resist_box_shrinking=enabled)

    @Slot(float)
    def on_shrink_resistance_changed(self, value: float) -> None:
        """
        Update the damping factor used by anti-shrink box processing.

        Args:
            value: Contraction damping factor between 0.0 and 0.99.

        Example:
            handler.on_shrink_resistance_changed(0.85)
        """
        self._update_processing_settings_and_warn(shrink_resistance=value)

    @Slot(float)
    def on_pre_detection_padding_sec_changed(self, value: float) -> None:
        """
        Update the backward pre-detection padding duration.

        Args:
            value: Backfill duration in seconds, from 0.0 to 5.0.

        Example:
            handler.on_pre_detection_padding_sec_changed(0.5)
        """
        self._update_processing_settings_and_warn(pre_detection_padding_sec=value)

    @Slot(float)
    def on_post_detection_padding_sec_changed(self, value: float) -> None:
        """
        Update the forward post-detection hold duration.

        Args:
            value: Hold duration in seconds, from 0.0 to 5.0.

        Example:
            handler.on_post_detection_padding_sec_changed(0.5)
        """
        self._update_processing_settings_and_warn(post_detection_padding_sec=value)

    @Slot(float)
    def on_box_safety_padding_pct_changed(self, value: float) -> None:
        """
        Update outward safety-margin inflation for privacy boxes.

        Args:
            value: Proportional inflation between 0.0 and 0.50.

        Example:
            handler.on_box_safety_padding_pct_changed(0.10)
        """
        self._update_processing_settings_and_warn(box_safety_padding_pct=value)

    @Slot(str)
    def _on_tracking_finished(self, s_id: SessionId) -> None:
        """
        Handle successful completion of tracking worker.

        Note:
            Triggered by `TrackingWorker.finished_processing` signal.

            Flow:
                _on_tracking_finished(s_id) [this slot]
                  ├── Synchronize tracking cache with session
                  ├── Clear loading view_state in UI
                  └──> Render frame with tracking results

        Args:
            s_id: Session whose worker has completed.
        Raises:
            Exception: Propagates synchronization or rendering failures.

        Note:
            The tracking tab is selected before rendering so its refreshed table
            and frame boxes are immediately visible.

        Example:
            handler._on_tracking_finished(session_id)
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
        self._window.bottom_panel.data_tab.setCurrentIndex(
            int(VideoDataLayerGroup.TRACKING)
        )
        self._controller.render_frame_for_session_id(s_id)

    @Slot(str)
    def _on_tracking_failed(self, error: str) -> None:
        """
        Handle tracking worker failure.

        Note:
            Triggered by `TrackingWorker.error_occurred` signal.

            Action: Clear loading view_state and show error dialog to user.
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
