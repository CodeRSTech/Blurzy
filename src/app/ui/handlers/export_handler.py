"""Video export handler for exporting annotated videos."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, final, override

from PySide6.QtCore import Slot, QObject
from PySide6.QtWidgets import QFileDialog

from app.application.adapters import ExportAllWorkerFactoryAdapter, ExportWorkerFactoryAdapter

from app.shared.app_preferences import AppPreferencesStore
from app.shared.logging_cfg import get_logger
from app.ui.qt.dialogs.export_all import ExportAllDialog
if TYPE_CHECKING:
    from app.domain.session import SessionId


if TYPE_CHECKING:
    from app.application.interfaces import ExportAllWorkerInterface, ExportWorkerInterface
    from app.ui.uicontroller import UIController

logger = get_logger("UI->ExportHandler")


@final
class ExportHandler(QObject):
    """
    Manages video export operations (single session and batch).

    Responsibilities:
        - Handle single-session export with user file selection.
        - Handle batch export for multiple sessions with export dialog.
        - Manage export worker lifecycle and progress tracking.
        - Toggle blur and detection drawing settings.
        - Update UI with export progress and completion status.

    Note:
        Signal flow:
            Receives signals from right panel (blur toggle, detection drawing toggle).
            Receives export button clicks from UI.
            Emits worker progress, success, and failure signals.
            Manages export worker and thread lifecycle.

        Uses background worker threads for non-blocking export.
        Prevents overlapping exports.
        Tracks batch export failures and cancellations.
        Cleans up workers after completion via ``deleteLater()``.
    """

    def __init__(self, controller: UIController) -> None:
        super().__init__()
        self.setParent(controller)
        self._controller = controller
        self._window = controller.window
        self._app = controller.app

        self._export_worker_factory = ExportWorkerFactoryAdapter()
        self._export_all_worker_factory = ExportAllWorkerFactoryAdapter()
        self._preferences_store = AppPreferencesStore()

        self.__export_worker: ExportWorkerInterface | None = None
        self.__export_all_worker: ExportAllWorkerInterface | None = None
        self._batch_failed_count = 0
        self._batch_cancelled = False
        self._batch_total_sessions = 0

        self._connect_signals()

    @override
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}>"
    
    def _connect_signals(self) -> None:
        self._window.right_panel.connect_signals_to_export_handler(self)

    @property
    def _export_worker(self) -> ExportWorkerInterface:
        if self.__export_worker is None:
            raise ValueError("Export Worker has not been initialized.")
        return self.__export_worker

    @property
    def _export_all_worker(self) -> ExportAllWorkerInterface:
        if self.__export_all_worker is None:
            raise ValueError("Export All Worker has not been initialized.")
        return self.__export_all_worker

    @property
    def is_exporting(self) -> bool:
        return (
            self.has_export_worker and self._export_worker.isRunning()
        ) or (
                self.has_export_all_worker and self._export_all_worker.isRunning()
        )

    @property
    def has_export_worker(self) -> bool:
        return self.__export_worker is not None

    @property
    def has_export_all_worker(self) -> bool:
        return self.__export_all_worker is not None

    def stop_exports(self, wait: bool = False) -> None:
        if self.has_export_worker and self._export_worker.isRunning():
            self._export_worker.stop()
            if wait:
                self._export_worker.wait()

        if self.has_export_all_worker and self._export_all_worker.isRunning():
            self._export_all_worker.stop()
            if wait:
                self._export_all_worker.wait()

    @Slot(bool)
    def on_draw_boxes_changed(self, enabled: bool) -> None:
        """
        Toggle bounding detection drawing on exported video.
    
        Note:
            Triggered by right panel ``draw_boxes_changed`` signal.
    
            Action:
                Update session setting ``draw_boxes`` to enabled/disabled.
                Re-render frame to reflect change immediately.
        """
        s_id = self._window.selected_s_id
        if s_id:
            # ================================================================
            # 1. UPDATE SESSION SETTINGS
            # ================================================================
            self._app.update_session_settings(s_id, draw_boxes=enabled)

            # ================================================================
            # 2. RENDER FRAME WITH UPDATED SETTING
            # ================================================================
            self._controller.render_frame_for_session_id(s_id)

    @Slot(bool)
    def on_blur_toggled(self, enabled: bool) -> None:
        """
        Toggle blur effect on exported video.
    
        Note:
            Triggered by right panel ``blur_toggled`` signal.
    
            Action:
                Show/hide blur strength slider.
                Update session setting ``blur_enabled``.
                Re-render frame to reflect change immediately.
        """
        # ====================================================================
        # 1. SHOW/HIDE BLUR STRENGTH CONTROLS
        # ====================================================================
        self._window.set_blur_strength_visible(enabled)

        # ====================================================================
        # 2. UPDATE SESSION SETTINGS
        # ====================================================================
        s_id = self._window.selected_s_id
        if s_id:
            self._app.update_session_settings(s_id, blur_enabled=enabled)

            # ================================================================
            # 3. RENDER FRAME WITH BLUR EFFECT
            # ================================================================
            self._controller.render_frame_for_session_id(s_id)

    @Slot(float)
    def on_blur_strength_changed(self, value: float) -> None:
        """
        Update blur strength value for exported video.
    
        Note:
            Triggered by right panel ``blur_strength_changed`` signal.
    
            Action:
                Update session setting ``blur_strength`` to new value.
                Re-render frame with new blur strength.
        """
        s_id = self._window.selected_s_id
        if s_id:
            # ================================================================
            # 1. UPDATE BLUR STRENGTH SETTING
            # ================================================================
            self._app.update_session_settings(s_id, blur_strength=value)

            # ================================================================
            # 2. RENDER FRAME WITH NEW BLUR STRENGTH
            # ================================================================
            self._controller.render_frame_for_session_id(s_id)

    @Slot()
    def on_export(self) -> None:
        """
        Export current session video with annotations to file.
    
        Note:
            Triggered by right panel ``export_btn.clicked``.

            Flow:
                on_export() [this slot]
                  ├── Validate session is selected
                  ├── Check if export already in progress
                  ├── Validate session has tracking/detection results
                  ├── Show file save dialog
                  ├── Create ExportWorker with output path
                  └──> Connect worker signals and start export
    
            Validates:
                Session is selected (not None).
                No export currently in progress.
                Session has detection and/or tracking results to export.
                User provides valid output file path.
        """
        app = self._app
        s_id = self._window.selected_s_id
        if not s_id:
            return

        # ====================================================================
        # 1. CHECK IF EXPORT ALREADY IN PROGRESS
        # ====================================================================
        if self.is_exporting:
            self._window.show_error(
                title="Export In Progress",
                msg="Wait for the current export to finish before starting another."
            )
            return

        # ====================================================================
        # 2. VALIDATE SESSION HAS RESULTS TO EXPORT
        # ====================================================================
        if not self._app.session_is_ready_for_export(s_id):
            self._window.show_error(
                title="Export Failed",
                msg="No tracking results to export. Run detection and tracking first."
            )
            return

        # ====================================================================
        # 3. PROMPT USER FOR OUTPUT FILE PATH
        # ====================================================================
        preferences = self._preferences_store.load()
        project_dirs = self._app.project_directories
        default_name = (
            f"{project_dirs.export_prefix or preferences.default_export_prefix}"
            f"{s_id.basename_without_extension}"
            f"{project_dirs.export_suffix or preferences.default_export_suffix}.mp4"
        )
        default_path = (
            str(Path(project_dirs.last_export_directory or preferences.default_export_directory) / default_name)
            if project_dirs.last_export_directory or preferences.default_export_directory
            else default_name
        )
        output_path, _ = QFileDialog.getSaveFileName(
            self._window, "Export Video", default_path, "Video Files (*.mp4)"
        )

        if not output_path:
            return

        self._app.update_project_directories(
            last_export_directory=str(Path(output_path).parent),
            export_prefix=project_dirs.export_prefix or preferences.default_export_prefix,
            export_suffix=project_dirs.export_suffix or preferences.default_export_suffix,
        )

        # ====================================================================
        # 4. UPDATE UI TO SHOW EXPORT IN PROGRESS
        # ====================================================================
        self._window.set_export_busy(True, "Exporting video...")
        self._window.set_export_overall_busy(False)

        # ====================================================================
        # 5. CREATE AND CONFIGURE EXPORT WORKER
        # ====================================================================
        # [NOTE] ExportWorker will run in a background thread
        # [TODO] Move worker creation to ExportService (App responsibility)
        self.__export_worker = self._export_worker_factory.create(
            export_service=app.export_svc,
            s_id=s_id,
            output_path=output_path,
            parent=self,
        )

        # ====================================================================
        # 6. CONNECT WORKER SIGNALS FOR PROGRESS AND COMPLETION
        # ====================================================================
        self._export_worker.progress_updated.connect(self._on_export_progress)
        self._export_worker.succeeded.connect(self._on_export_succeeded)
        self._export_worker.cancelled.connect(self._on_export_cancelled)
        self._export_worker.error_occurred.connect(self._on_export_failed)
        self._export_worker.finished_processing.connect(self._cleanup_export_worker)

        # ====================================================================
        # 7. START EXPORT WORKER
        # ====================================================================
        self._export_worker.start()

    @Slot()
    def on_export_all(self) -> None:
        """
        Batch export all open sessions with configurable output paths.
    
        Note:
            Triggered by right panel ``export_all_btn.clicked`` or File menu action.

            Flow:
                on_export_all() [this slot]
                  ├── Validate videos are open
                  ├── Check if export already in progress
                  ├── Show batch export configuration dialog
                  ├── Create ExportAllWorker with parameters
                  └──> Connect worker signals and start batch export
    
            User Configuration (via dialog):
                Output directory path.
                Filename prefix.
                Filename suffix.
    
            Tracks:
                Failed session count (displayed in final message).
                Cancellation view_state (user stops batch).
        """
        # ====================================================================
        # 1. VALIDATE VIDEOS ARE OPEN
        # ====================================================================
        s_ids = list(self._app.all_s_ids)
        if not s_ids:
            self._window.show_error("Export All", "No videos are open.")
            return

        # ====================================================================
        # 2. CHECK IF EXPORT ALREADY IN PROGRESS
        # ====================================================================
        if self.is_exporting:
            self._window.show_error(
                "Export In Progress",
                "Wait for the current export to finish before starting another."
            )
            return

        # ====================================================================
        # 3. SHOW BATCH EXPORT CONFIGURATION DIALOG
        # ====================================================================
        preferences = self._preferences_store.load()
        project_dirs = self._app.project_directories
        dlg = ExportAllDialog(
            self._window,
            initial_directory=project_dirs.last_export_directory or preferences.default_export_directory,
            initial_prefix=project_dirs.export_prefix or preferences.default_export_prefix,
            initial_suffix=project_dirs.export_suffix or preferences.default_export_suffix,
        )
        if dlg.exec() != ExportAllDialog.DialogCode.Accepted:
            return

        # ====================================================================
        # 4. GET EXPORT CONFIGURATION FROM DIALOG
        # ====================================================================
        out_dir, prefix, suffix = dlg.get_export_config()
        self._app.update_project_directories(
            last_export_directory=out_dir,
            export_prefix=prefix,
            export_suffix=suffix,
        )
        self._batch_failed_count = 0
        self._batch_cancelled = False
        self._batch_total_sessions = len(s_ids)

        # ====================================================================
        # 5. UPDATE UI TO SHOW BATCH EXPORT IN PROGRESS
        # ====================================================================
        self._window.set_export_busy(True, f"Batch exporting {len(s_ids)} video(s)...")
        self._window.set_export_overall_busy(True)
        self._window.set_export_overall_progress(0, self._batch_total_sessions, "Batch")

        # ====================================================================
        # 6. CREATE BATCH EXPORT WORKER
        # ====================================================================
        self.__export_all_worker = self._export_all_worker_factory.create(
            app=self._app,
            s_ids=s_ids,
            output_dir=out_dir,
            prefix=prefix,
            suffix=suffix,
            parent=self,
        )

        # ====================================================================
        # 7. CONNECT WORKER SIGNALS FOR PROGRESS, PER-SESSION, AND COMPLETION
        # ====================================================================
        self._export_all_worker.session_started.connect(self._on_export_all_started)
        self._export_all_worker.session_export_progress_updated.connect(self._on_export_all_session_progress)
        self._export_all_worker.progress_updated.connect(self._on_export_all_progress)
        self._export_all_worker.session_failed.connect(self._on_export_all_session_failed)
        self._export_all_worker.cancelled.connect(self._on_export_all_cancelled)
        self._export_all_worker.finished_processing.connect(self._on_export_all_finished)

        # ====================================================================
        # 8. START BATCH EXPORT WORKER
        # ====================================================================
        self._export_all_worker.start()

    @Slot(object)
    def _on_export_all_started(self, s_id: SessionId) -> None:
        """
        Handle start of exporting a single session in batch.
    
        Note:
            Triggered by ``ExportAllWorker.session_started`` signal.
    
            Action: Update status bar to show which session is being exported.
        """
        self._window.set_export_progress_status(f"{s_id.basename} (Preparing)")
        self._window.set_status_text(f"Preparing session: {s_id}...")

    @Slot(int, int)
    def _on_export_progress(self, current_frame: int, total_frames: int) -> None:
        """
        Handle progress update from single-session export.
    
        Note:
            Triggered by ``ExportWorker.progress_updated`` signal.
    
            Action: Update progress bar and status text with frame count.
        """
        self._window.set_export_progress(current_frame, total_frames, "Exporting")
        self._window.set_status_text(f"Exporting video: frame {current_frame}/{total_frames}")

    @Slot()
    def _on_export_succeeded(self) -> None:
        """
        Handle successful completion of single-session export.
    
        Note:
            Triggered by ``ExportWorker.succeeded`` signal.
    
            Action: Show completion message and full progress bar.
        """
        self._window.set_status_text("Export completed.")
        self._window.set_export_progress(1, 1, "Complete")

    @Slot()
    def _on_export_cancelled(self) -> None:
        """
        Handle cancellation of single-session export.
    
        Note:
            Triggered by ``ExportWorker.cancelled`` signal.
    
            Action: Update status bar with cancellation message.
        """
        self._window.set_status_text("Export cancelled.")
        self._window.set_export_progress_status("Cancelled")

    @Slot(str)
    def _on_export_failed(self, error: str) -> None:
        """
        Handle failure of single-session export.
    
        Note:
            Triggered by ``ExportWorker.error_occurred`` signal.
    
            Action: Show error dialog and update status bar.
        """
        self._window.set_status_text("Export failed.")
        self._window.set_export_progress_status("Failed")
        self._window.show_error("Export Failed", error)

    @Slot()
    def _cleanup_export_worker(self) -> None:
        """
        Clean up single-session export worker after completion.
    
        Note:
            Triggered by ``ExportWorker.finished_processing`` signal.
    
            Action: Schedule worker deletion and clear busy view_state.
        """
        self._window.set_export_busy(False)
        if self.__export_worker is not None:
            self.__export_worker.deleteLater()
            self.__export_worker = None

    @Slot(object, int, int)
    def _on_export_all_session_progress(self, s_id: SessionId, current_frame: int, total_frames: int) -> None:
        """
        Handle per-session frame progress during batch export.
    
        Note:
            Triggered by ``ExportAllWorker.session_export_progress_updated`` signal.
    
            Action: Update progress bar with session name and frame count.
        """
        self._window.set_export_progress(current_frame, total_frames, s_id.basename)

    @Slot(int, int)
    def _on_export_all_progress(self, sessions_done: int, total_sessions: int) -> None:
        """
        Handle overall batch progress (sessions completed vs. total).
    
        Note:
            Triggered by ``ExportAllWorker.progress_updated`` signal.
    
            Action: Update status bar with session progress (X/N completed).
        """
        self._window.set_export_overall_progress(sessions_done, total_sessions, "Batch")
        self._window.set_status_text(f"Batch export progress: {sessions_done}/{total_sessions} session(s)")

    @Slot(object, str)
    def _on_export_all_session_failed(self, s_id: SessionId, error: str) -> None:
        """
        Handle failure of a single session during batch export.
    
        Note:
            Triggered by ``ExportAllWorker.session_failed`` signal.
    
            Action:
                Increment failed count (displayed in final message).
                Log error for debugging.
                Batch continues with next session.
        """
        self._batch_failed_count += 1
        logger.error("Batch export failed for {}: {}", s_id, error)

    @Slot()
    def _on_export_all_cancelled(self) -> None:
        """
        Handle cancellation of batch export (user stopped it).
    
        Note:
            Triggered by ``ExportAllWorker.cancelled`` signal.
    
            Action: Set flag so final message indicates cancellation.
        """
        self._batch_cancelled = True

    @Slot()
    def _on_export_all_finished(self) -> None:
        """
        Handle completion of batch export (all sessions done or cancelled).
    
        Note:
            Triggered by ``ExportAllWorker.finished_processing`` signal.
    
            Flow:
                _on_export_all_finished() [this slot]
                  ├── Clear busy view_state in UI
                  ├── Set final status message based on result:
                  │   ├── "cancelled" if user stopped
                  │   ├── "completed with N failures" if some failed
                  │   └── "completed" if all successful
                  └──> Schedule worker deletion
        """
        # ====================================================================
        # 1. CLEAR BUSY STATE
        # ====================================================================
        self._window.set_export_busy(False)

        # ====================================================================
        # 2. SET FINAL STATUS MESSAGE
        # ====================================================================
        if self._batch_cancelled:
            self._window.set_status_text("Batch export cancelled.")
        elif self._batch_failed_count:
            self._window.set_status_text(f"Batch export completed with {self._batch_failed_count} failure(s).")
        else:
            self._window.set_status_text("Batch export completed.")

        # ====================================================================
        # 3. SCHEDULE WORKER DELETION
        # ====================================================================
        if self.__export_all_worker is not None:
            self.__export_all_worker.deleteLater()
            self.__export_all_worker = None
        self._batch_total_sessions = 0
