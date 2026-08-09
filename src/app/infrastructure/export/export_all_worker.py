"""Batch export orchestrator — detects, tracks, and exports multiple sessions sequentially."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, final

from PySide6.QtCore import QObject, QThread, Signal

from app.domain import VideoDataLayer

if TYPE_CHECKING:
    from app.application.application import Application
    from app.domain.session import SessionId
from app.shared.logging_cfg import get_logger

logger = get_logger("Infrastructure->ExportAllWorker")


@final
class ExportAllWorker(QThread):
    """
    Background QThread that orchestrates full detect -> track -> export pipeline for multiple sessions.

    Attributes:
        _app (Application): Application instance containing session managers and services.
        _s_ids (list[SessionId]): Session IDs to process.
        _output_dir (str): Output directory for exported videos.
        _prefix (str): Filename prefix applied to each export.
        _suffix (str): Filename suffix applied before the ``.mp4`` extension.
        _stop_requested (bool): True when batch cancellation is requested.
        _current_s_id (SessionId | None): Session currently being processed.

    Note:
        Signals emitted by this worker:
            | ``session_started(s_id)``: Emitted when session processing begins.
            | ``session_finished(s_id)``: Emitted when a session succeeds.
            | ``session_failed(s_id, error_msg)``: Emitted when a session fails.
            | ``progress_updated(sessions_done, total_sessions)``: Per-session progress.
            | ``session_export_progress_updated(s_id, current_frame, total_frames)``: Per-frame export progress.
            | ``finished_processing()``: Emitted when all sessions are done or cancelled.
            | ``cancelled()``: Emitted if the batch is cancelled.

        Pipeline per session:
            1. Detection: if Layer A is empty, run ``start_detection_worker()``, wait,
               and sync the cache.
            2. Tracking: if Layer C is empty, run ``start_tracking_worker()`` and wait.
            3. Export: call ``export_session()`` with progress callbacks.
            4. Repeat sequentially for the next session.

        Cancellation stops current workers but does not abort an in-progress export.

    Example:
        s_ids = [SessionId(...), SessionId(...)]
        worker = ExportAllWorker(app, s_ids, "output", "prefix_", "_suffix")
        worker.session_finished.connect(on_session_done)
        worker.start()
        worker.stop()
    """

    session_started = Signal(str)  # s_id
    session_finished = Signal(str)  # s_id
    session_failed = Signal(str, str)  # s_id, error_message
    progress_updated = Signal(int, int)  # (sessions_done, total_sessions)
    session_export_progress_updated = Signal(str, int, int)  # s_id, current_frame, total_frames
    finished_processing = Signal()
    cancelled = Signal()

    def __init__(
        self,
        app: Application,
        s_ids: list[SessionId],
        output_dir: str,
        prefix: str,
        suffix: str,
        parent: QObject | None = None,
    ) -> None:
        """Initialize batch export for ``s_ids`` to ``output_dir`` with naming prefix/suffix."""
        super().__init__(parent)
        self._app = app
        self._s_ids = s_ids
        self._output_dir = output_dir
        self._prefix = prefix
        self._suffix = suffix
        self._stop_requested = False
        self._current_s_id: SessionId | None = None

    def stop(self) -> None:
        """Request early stop (stops current workers, doesn't cancel in-progress export)."""
        self._stop_requested = True
        if self._current_s_id is None:
            return
        try:
            session = self._app.sm.get_session_by_id(self._current_s_id)
        except KeyError:
            return
        if session.detection_worker is not None:
            session.detection_worker.stop()
        if session.tracking_worker is not None:
            session.tracking_worker.stop()

    def run(self) -> None:
        """
        Main thread loop — process each session sequentially (detect -> track -> export).

        Note:
            Workflow per session:
                1. Emit ``session_started(s_id)``.
                2. Call ``_process_session(s_id)``.
                3. Emit ``session_finished(s_id)`` or ``session_failed(s_id, error)``.
                4. Emit ``progress_updated(idx + 1, total)``.
                5. Repeat for the next session.
                6. If stopped early, emit ``cancelled()`` before
                   ``finished_processing()``.
        """
        total = len(self._s_ids)
        logger.info("ExportAllWorker started: {} session(s)", total)

        for idx, s_id in enumerate(self._s_ids):
            if self._stop_requested:
                logger.info("ExportAllWorker stopped by request")
                break

            self.session_started.emit(s_id)
            self._current_s_id = s_id
            try:
                if self._process_session(s_id):
                    self.session_finished.emit(s_id)
                else:
                    logger.info("ExportAllWorker cancelled while processing {}", s_id)
                    break
            except Exception as exc:
                if self._stop_requested:
                    logger.info("ExportAllWorker cancelled while processing {}", s_id)
                    break
                logger.opt(exception=True).exception(
                    "ExportAllWorker failed for session '{}'", s_id
                )
                self.session_failed.emit(s_id, str(exc))

            self.progress_updated.emit(idx + 1, total)

        self._current_s_id = None
        if self._stop_requested:
            self.cancelled.emit()
        self.finished_processing.emit()
        logger.info("ExportAllWorker finished")

    def _process_session(self, s_id: SessionId) -> bool:
        """
        Process a single session: detect (if needed), track (if needed), then export.

        Returns:
            bool: ``False`` if cancelled, otherwise ``True``. Errors are surfaced to the
            caller, which emits the failure signal.
        """
        app = self._app
        session = app.sm.get_session_by_id(s_id)

        # Detection
        # if not session.view_state.raw_boxes_by_frame:
        if not session.has_boxes_for_layer(VideoDataLayer.A):

            if self._stop_requested:
                return False

            logger.info("ExportAll: running detection for {}", s_id)
            app.start_detection_worker(s_id)

            if session.has_running_detection_worker:
                session.detection_worker.wait()
            # app.sync_detection_cache(s_id)
            if self._stop_requested:
                return False

        # Tracking
        # if not session.view_state.tracked_boxes_by_frame:
        if not session.has_boxes_for_layer(VideoDataLayer.C):
            if self._stop_requested:
                return False
            logger.info("ExportAll: running tracking for {}", s_id)
            app.start_tracking_worker(
                s_id,
                session.state.settings.tracking_strategy,
                VideoDataLayer(session.state.settings.tracking_source),
            )
            if session.has_running_tracking_worker:
                session.tracking_worker.wait()
            app.sync_tracking_cache(s_id)

            if self._stop_requested:
                return False

        # Export
        if self._stop_requested:
            return False
        if not app.session_is_ready_for_export(s_id):
            raise RuntimeError(f"Session {s_id} has no tracking data to export.")

        basename = s_id.basename_without_extension
        filename = f"{self._prefix}{basename}{self._suffix}.mp4"
        output_path = os.path.join(self._output_dir, filename)

        logger.info("ExportAll: exporting {} → {}", s_id, output_path)
        app.export_session(
            s_id,
            output_path,
            progress_callback=lambda current, total: self._emit_export_progress_or_cancel(
                s_id,
                current,
                total,
            ),
        )
        return not self._stop_requested

    def _emit_export_progress_or_cancel(self, s_id: SessionId, current_frame: int, total_frames: int) -> None:
        """Progress callback for export service — raise ``RuntimeError`` if batch stopped."""
        if self._stop_requested:
            raise RuntimeError("Batch export cancelled.")
        self.session_export_progress_updated.emit(s_id, current_frame, total_frames)
