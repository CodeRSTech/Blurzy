"""Detection operations handler for model-based object detection."""

from __future__ import annotations

from typing import TYPE_CHECKING, final, override

from PySide6.QtCore import Slot, QObject

from app.domain import VideoDataLayer
from app.shared.exceptions import (
    DomainException,
    NullModelNameException,
    WorkerAlreadyRunningException,
)
from app.shared.logging_cfg import get_logger

if TYPE_CHECKING:
    from app.ui.uicontroller import UIController

logger = get_logger("UI->DetectionHandler")


@final
class DetectionHandler(QObject):
    """
    Orchestrates object detection operations and model configuration.

    **Responsibilities**:

    - Handle detection model selection and changes
    - Execute single-frame detection or background detection
    - Manage detection confidence thresholds
    - Filter detections by label selection
    - Update UI view_state based on detection results

    **Signal Flow**:

    - Receives signals from right panel (model selection, detect buttons, confidence changes)
    - Delegates to ``Application`` for detection execution
    - Renders frames after detection completion
    """

    def __init__(self, controller: UIController) -> None:
        super().__init__()
        self.setParent(controller)

        self._owner = controller
        self._controller = controller.ui_controller
        self._window = controller.window
        self._app = controller.ui_app

        self._connect_signals()

    @override
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}>"

    def _connect_signals(self) -> None:
        right_panel = self._window.right_panel

        right_panel.chosen_labels_changed.connect(self.on_chosen_labels_changed)
        right_panel.detect_btn.clicked.connect(self.on_detect_current_frame)
        right_panel.detect_all_btn.clicked.connect(self.on_start_background_detection)
        right_panel.min_confidence_spinbox.valueChanged.connect(self.on_min_confidence_changed)

    @Slot()
    def on_detect_current_frame(self) -> None:
        """
        Run detection on the current frame of the selected session.

        **Triggered By:**
            Right panel ``detect_btn.clicked`` signal

        **Flow:**

        ``on_detect_current_frame()`` `[this slot]`:
          |
          | ├──> Set active session
          | ├──> Call App.detect_current_frame(s_id)
          | └──> Render updated frame with detection results
              
        """
        s_id = self._window.selected_s_id
        if not s_id:
            return
        try:
            # ====================================================================
            # 1. SET ACTIVE SESSION
            # ====================================================================
            self._app.active_session_id = s_id

            # ====================================================================
            # 2. RUN DETECTION ON CURRENT FRAME
            # ====================================================================
            self._app.detect_current_frame(s_id)

            # ====================================================================
            # 3. RENDER FRAME WITH DETECTION RESULTS
            # ====================================================================
            self._controller.render_frame_for_session_id(s_id)
        except DomainException as exc:
            self._window.show_error("Detection Failed", str(exc))
            logger.warning("Detection failed due to domain exception: {}", exc)
        except Exception as exc:
            self._window.show_error("Detection Failed", str(exc))
            logger.opt(exception=exc).error("Failed to detect current frame")

    @Slot()
    def on_start_background_detection(self) -> None:
        """
        Start background detection worker for the selected session.

        **Triggered By:**
            Right panel ``detect_all_btn.clicked`` signal

        **Flow:**
            ``on_start_background_detection()`` [this slot]::
            
              ├── Set active session
              ├── Start DetectionWorker via App (catches WorkerAlreadyRunningException, NullModelNameException)
              └──> Update UI status bar
        

        **Error Handling:**
            - Displays error if worker already running for this session
            - Displays error if no model selected
            - Updates status bar in finally block
        """
        s_id = self._window.selected_s_id
        if not s_id:
            return

        # ====================================================================
        # 1. SET ACTIVE SESSION
        # ====================================================================
        self._app.active_session_id = s_id

        # ====================================================================
        # 2. START BACKGROUND DETECTION WORKER
        # ====================================================================
        try:
            self._window.set_detection_progress_busy(True)
            self._window.set_status_text("Starting background detection...")
            self._app.start_detection_worker(s_id)
            session = self._app.get_session_by_id(s_id)
            if session.detection_worker is not None:
                session.detection_worker.progress_updated.connect(self._on_detection_progress)
                session.detection_worker.finished_processing.connect(self._on_detection_finished)
                session.detection_worker.error_occurred.connect(self._on_detection_failed)
        except WorkerAlreadyRunningException:
            self._window.show_error(
                title="Background Detection Failed",
                msg=f"A detection worker is already running for session: {s_id}.",
            )
        except NullModelNameException:
            self._window.show_error(
                title="Background Detection Failed", msg=f"No model selected for session: {s_id}."
            )
        except DomainException as exc:
            self._window.show_error("Background Detection Failed", str(exc))
            logger.warning("Background detection failed due to domain exception: {}", exc)
        except Exception as exc:
            self._window.show_error("Background Detection Failed", str(exc))
            logger.opt(exception=exc).error("Failed to start background detection")
        # ====================================================================
        # 3. UPDATE UI STATUS BAR
        # ====================================================================
        finally:
            self._controller.update_ui_status_bar()

    @Slot(int, int, float)
    def _on_detection_progress(self, processed_frames: int, total_frames: int, eta_msecs: float | None = None) -> None:
        self._window.set_detection_progress(processed_frames, total_frames, "Detection", eta_msecs=eta_msecs)
        self._window.set_status_text(f"Detecting frames: {processed_frames}/{total_frames}")

    @Slot()
    def _on_detection_finished(self) -> None:
        self._window.set_detection_progress_busy(False)
        self._controller.update_ui_status_bar()

    @Slot(str)
    def _on_detection_failed(self, error: str) -> None:
        self._window.set_detection_progress_busy(False)
        self._window.show_error("Background Detection Failed", error)

    @Slot(float)
    def on_min_confidence_changed(self, value: float) -> None:
        """
        Update the minimum detection confidence-threshold and refilter detections.

        **Triggered By:**

        Right panel ``min_confidence_spinbox.valueChanged`` signal

        **Flow:**

        ``on_min_confidence_changed(value)`` `[this slot]`:
          |
          | ├── Update session settings with new ``min_detection_confidence``
          | ├── Reapply filtering logic to Layer B (detections)
          | └──> Render frame with filtered boxes
            
        """
        s_id = self._window.selected_s_id
        if not s_id:
            return

        # ====================================================================
        # 1. UPDATE SESSION SETTINGS
        # ====================================================================
        self._app.update_session_settings(s_id, min_detection_confidence=value)

        # ====================================================================
        # 2. REAPPLY FILTERS AND RENDER
        # ====================================================================
        self._app.apply_filters_to_layer(layer_name=VideoDataLayer.B, s_id=s_id)
        self._controller.render_frame_for_session_id(s_id)

    @Slot(str)
    def on_chosen_labels_changed(self, raw: str) -> None:
        """
        Update selected labels and refilter detections by class.

        **Triggered By:**

        ``RightControlPanel.chosen_labels_changed`` signal

        **Flow:**

        ``on_chosen_labels_changed(raw)`` `[this slot]`:
          |
          | ├── Parse comma-separated label string
          | ├── Update session settings with new ``chosen_labels``
          | ├── Reapply filtering logic to Layer B
          | ├── Render frame with filtered boxes
          | └──> Show tracking warning if tracking data exists
            
        """
        s_id = self._window.selected_s_id
        if not s_id:
            return

        # ====================================================================
        # 1. PARSE LABELS FROM COMMA-SEPARATED STRING
        # ====================================================================
        labels = self._preprocess_labels(raw)

        # ====================================================================
        # 2. UPDATE SESSION SETTINGS AND REAPPLY FILTERS
        # ====================================================================
        self._app.update_session_settings(s_id, chosen_labels=labels)
        self._app.apply_filters_to_layer(layer_name=VideoDataLayer.B, s_id=s_id)

        # ====================================================================
        # 3. RENDER FRAME WITH FILTERED BOXES
        # ====================================================================
        self._controller.render_frame_for_session_id(s_id)

        # ====================================================================
        # 4. WARN IF TRACKING DATA EXISTS
        # ====================================================================
        # [NOTE] Show warning if user has tracking results that may be affected
        active = self._app.active_session
        if active and active.data.has_boxes_for_layer(VideoDataLayer.C):
            self._window.set_tracking_config_warning_visible(True)

    @staticmethod
    def _preprocess_labels(raw: str) -> list[str]:
        return [lbl.strip() for lbl in raw.split(",") if lbl.strip()]
