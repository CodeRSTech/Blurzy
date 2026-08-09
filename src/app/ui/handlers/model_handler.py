"""Detection model management handler for asynchronous model loading."""

from __future__ import annotations

from typing import TYPE_CHECKING, final, override

from PySide6.QtCore import Slot, QThread, QObject
from PySide6.QtWidgets import QDialog

from app.domain.video.layer_group import VideoDataLayerGroup
from app.shared.logging_cfg import get_logger
from app.ui.qt.workers import ModelLoadWorker

if TYPE_CHECKING:
    from app.ui.uicontroller import UIController
    from app.domain.session.session_id import SessionId

logger = get_logger("UI->ModelHandler")


@final
class ModelHandler(QObject):
    """
    Manages asynchronous detection model loading and switching.

    Responsibilities:
        - Handle model selection changes via UI dropdown.
        - Manage model load worker thread lifecycle.
        - Show model loading view_state in UI.
        - Handle model load success and failure cases.
        - Orchestrate proper thread cleanup to prevent memory leaks.

    Note:
        Uses ``ModelLoadWorker`` in separate ``QThread`` to prevent UI blocking.
        Must follow strict thread teardown sequence (quit → wait → deleteLater).
        Worker is parentless (required by ``moveToThread()`` in Qt).
        Cannot modify objects across thread boundaries.

        Signal flow:
            Receives ``model_changed`` signal from right panel dropdown.
            Emits worker finished/failed signals to update UI.
            Triggers frame re-render after successful model load.
    """

    def __init__(self, controller: UIController) -> None:
        super().__init__()
        self.setParent(controller)  # <- avoids circular dependency

        self._controller = controller
        self._window = controller.window
        self._app = controller.app

        self._dont_ask_again = False

        # Async model loader view_state.
        self._model_load_thread: QThread | None = None
        self._model_load_worker: ModelLoadWorker | None = None

        self._connect_signals()

    @override
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}>"

    def _connect_signals(self) -> None:
        self._controller.window.right_panel.model_changed.connect(self.on_model_changed)

    def close(self) -> None:
        if self._model_load_thread is not None and self._model_load_thread.isRunning():
            self._model_load_thread.quit()
            self._model_load_thread.wait()

    @Slot(str)
    def on_model_changed(self, model_name: str) -> None:
        """
        Handle detection model change from UI dropdown.
    
        Note:
            Triggered by right panel ``model_changed`` signal with model name.
    
            Flow:
                on_model_changed(model_name) [this slot]
                  ├── Validate session is selected
                  ├── Show confirmation dialog (unless dismissed via checkbox)
                  ├── Update session settings with new model name
                  └──> Start asynchronous model load worker
    
            Key Behaviors:
                Validates that a session is active (model can only load with active session).
                Shows warning dialog unless user checks "Don't ask again".
                Reverts dropdown if user cancels dialog.
                Starts ``ModelLoadWorker`` in separate thread (non-blocking).
        """
        # ====================================================================
        # 1. GET SELECTED SESSION ID
        # ====================================================================
        s_id = self._window.selected_s_id
        try:
            existing_session_model_name = self._app.get_selected_detection_model_name(s_id)
        except KeyError:
            existing_session_model_name = None
        logger.info("Changing model from {} to: {}", existing_session_model_name, model_name)

        # ====================================================================
        # 2. VALIDATE SESSION IS SELECTED
        # ====================================================================
        # [NOTE] When a video is opened, a session becomes active, which is
        # a prerequisite for enabling the model dropdown widget. Any calls
        # without a valid s_id indicate something is wrong.
        if not s_id:
            return

        # ====================================================================
        # 3. SHOW CONFIRMATION DIALOG (unless user dismissed it)
        # ====================================================================
        keep_manual = True
        if not self._dont_ask_again and model_name != "None":
            dlg = self._controller.create_model_change_warning_dialog(s_id)
            if dlg.exec() != QDialog.DialogCode.Accepted:
                # Revert dropdown to previous selection if user cancels
                self._window.set_selected_detection_model(
                    self._app.get_selected_detection_model_name(s_id)
                )
                return
            keep_manual, self._dont_ask_again = dlg.get_results()

        # ====================================================================
        # 4. UPDATE SESSION SETTINGS WITH NEW MODEL NAME
        # ====================================================================
        self._app.update_session_settings(s_id=s_id, detection_model_name=model_name)

        logger.info(
            "Model change requested (session: '{}', model: '{}', keep_manual={})",
            s_id,
            model_name,
            keep_manual,
        )

        # ====================================================================
        # 5. START ASYNCHRONOUS MODEL LOAD
        # ====================================================================
        self._start_model_load(s_id, model_name, keep_manual)

    @Slot(object, str)
    def on_model_load_finished(self, s_id: SessionId, model_name: str) -> None:
        """
        Handle successful completion of model load in worker thread.
    
        Note:
            Triggered by ``ModelLoadWorker.finished`` signal.
    
            Flow:
                on_model_load_finished(s_id, model_name) [this slot]
                  ├── Clear detection boxes from UI tab
                  ├── Update status bar with model info
                  └──> Render frame (ready for new detections)
    
            Downstream: None (leaf node — updates UI only).
        """
        logger.debug("Model load finished for session '{}' with model {}", s_id, model_name)

        # ====================================================================
        # 1. CLEAR EXISTING DETECTION BOXES FROM UI
        # ====================================================================
        # [NOTE] New model has different classes, so clear old detections
        self._controller.set_ui_data_tab_frame_boxes(tab=VideoDataLayerGroup.DETECTION, boxes=[])

        # ====================================================================
        # 2. UPDATE STATUS BAR
        # ====================================================================
        self._controller.update_ui_status_bar()

        # ====================================================================
        # 3. RENDER FRAME (READY FOR NEW DETECTIONS)
        # ====================================================================
        self._controller.render_frame_for_session_id(s_id)

    @Slot(object, str, str)
    def on_model_load_failed(self, s_id: SessionId, model_name: str, err: str) -> None:
        """
        Handle model load failure from worker thread.
    
        Note:
            Triggered by ``ModelLoadWorker.failed`` signal.
    
            Action: Display error dialog to user and update status bar.
    
            Downstream: None (leaf node — error display only).
        """
        logger.error(
            "Model load failed for session '{}' with model {}: {}",
            s_id,
            model_name,
            err,
        )

        # ====================================================================
        # 1. SHOW ERROR DIALOG
        # ====================================================================
        self._window.show_error("Model Load Failed", err)

        # ====================================================================
        # 2. UPDATE STATUS BAR
        # ====================================================================
        self._controller.update_ui_status_bar()

    @Slot()
    def _cleanup(self) -> None:
        """
        Clean up model load worker and thread after load completes.
    
        Note:
            Triggered by ``ModelLoadWorker.finished`` or ``failed`` signals.
    
            Why this is critical: The ``ModelLoadWorker`` is parentless (required by ``moveToThread()``) so Qt cannot automatically delete it when the handler is destroyed. We must manually orchestrate a synchronized teardown following a strict sequence to prevent memory leaks and thread crashes.
    
            Mandatory Shutdown Sequence (MUST follow this order):
                Stop the worker — signal it to finish its task.
                Quit the thread — tell the QThread event loop to stop accepting events.
                Wait for exit — block main thread until OS closes the thread completely.
                Delete the worker — safely free parentless worker via ``deleteLater()``.
                Delete the thread — schedule QThread itself for deletion.
        """
        # ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
        # ┃                                  IMPORTANT                                    ┃
        # ┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫
        # ┃ Do NOT call deleteLater() on active threads or workers.                      ┃
        # ┃ Must call quit() → wait() before deleting memory.                            ┃
        # ┃                                                                              ┃
        # ┃ Calling deleteLater() on a running thread causes immediate crashes.         ┃
        # ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

        # ====================================================================
        # 1. UPDATE UI LOADING STATE
        # ====================================================================
        self._window.set_detection_loading_state(is_loading=False)

        # ====================================================================
        # 2. STOP AND JOIN THREAD
        # ====================================================================
        if self._model_load_thread is not None and self._model_load_thread.isRunning():
            # 2.1 Tell the thread's event loop to stop accepting new events
            self._model_load_thread.quit()
            # 2.2 Block the main thread until the OS thread completely exits
            self._model_load_thread.wait()

        # ====================================================================
        # 3. SCHEDULE WORKER DELETION (NOW THAT THREAD IS DEAD)
        # ====================================================================
        # [NOTE] Only call deleteLater() after quit() and wait() complete
        if self._model_load_worker is not None:
            self._model_load_worker.deleteLater()
            self._model_load_worker = None

            # ================================================================
            # 4. FINALLY, SCHEDULE QTHREAD ITSELF FOR DELETION
            # ================================================================
            if self._model_load_thread is not None:
                self._model_load_thread.deleteLater()
                self._model_load_thread = None

    def _start_model_load(self, s_id: SessionId, model_name: str, keep_manual: bool) -> None:
        """
        Create and start model load worker in separate thread (non-blocking).
    
        Note:
            Flow:
                _start_model_load(s_id, model_name, keep_manual)
                  ├── Check if another model is already loading
                  ├── Create parentless ModelLoadWorker
                  ├── Move worker to new QThread
                  ├── Connect signals to slots
                  └──> Start QThread (triggers ModelLoadWorker.run())
    
            Critical Notes:
                Worker MUST be parentless before ``moveToThread()`` (Qt thread affinity rule).
                Parentless objects cannot have child objects and cannot span threads.
                Signal cascade: thread.started → worker.run() → worker.finished → cleanup.
        """
        # ====================================================================
        # 1. CHECK IF MODEL IS ALREADY LOADING
        # ====================================================================
        if self._model_load_thread is not None and self._model_load_thread.isRunning():
            self._window.show_error("Model Change Failed", "A model is already loading.")
            return

        # ====================================================================
        # 2. CREATE NEW PARENTLESS MODEL LOAD WORKER AND THREAD
        # ====================================================================
        # ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
        # ┃                                  IMPORTANT                        ┃
        # ┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫
        # ┃ Do NOT assign a parent before calling moveToThread().             ┃
        # ┃ Qt enforces strict thread affinity. A QObject hierarchy cannot   ┃
        # ┃ span multiple threads. Moving an object with a parent fails      ┃
        # ┃ with a runtime warning.                                          ┃
        # ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
        self._model_load_thread = QThread()
        self._model_load_worker = ModelLoadWorker(self._app, s_id, model_name, keep_manual)

        # ====================================================================
        # 3. VALIDATE WORKER AND THREAD CREATION
        # ====================================================================
        if self._model_load_worker is None or self._model_load_thread is None:
            logger.error(
                "Model load worker/thread became None after initialization. worker = {}, thread = {}",
                self._model_load_worker,
                self._model_load_thread,
            )
            return

        # ====================================================================
        # 4. UPDATE UI TO SHOW LOADING STATE
        # ====================================================================
        self._window.set_detection_loading_state(is_loading=True, model_name=model_name)

        # ====================================================================
        # 5. MOVE WORKER TO SEPARATE THREAD
        # ====================================================================
        # [NOTE] ``moveToThread()`` transfers the worker to a different thread.
        # The worker and all its children will execute in the target thread.
        # Worker must be parentless (see IMPORTANT detection above).
        self._model_load_worker.moveToThread(self._model_load_thread)

        # ====================================================================
        # 6. CONNECT SIGNAL CHAIN FOR THREAD LIFECYCLE
        # ====================================================================
        logger.trace("Connecting model worker and thread.")
        for signal, slot in (
            # When thread starts, run the worker's main loop
            (self._model_load_thread.started, self._model_load_worker.run),
            # When thread finishes, clean up worker and thread
            (self._model_load_thread.finished, self._cleanup),
            # When worker finishes successfully, notify UI and stop thread
            (self._model_load_worker.finished, self.on_model_load_finished),
            (self._model_load_worker.finished, self._model_load_thread.quit),
            # When worker fails, notify UI and stop thread
            (self._model_load_worker.failed, self.on_model_load_failed),
            (self._model_load_worker.failed, self._model_load_thread.quit),
        ):
            signal.connect(slot)

        # ====================================================================
        # 7. START THE THREAD
        # ====================================================================
        # [NOTE] This emits thread.started signal, which triggers worker.run()
        self._model_load_thread.start()
