"""Background video export worker with progress callbacks and cancellation support."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QThread, Signal
if TYPE_CHECKING:
    from PySide6.QtCore import QObject


if TYPE_CHECKING:
    from app.application.services.export_service import ExportService
    from app.domain.session import SessionId
from app.shared.logging_cfg import get_logger

logger = get_logger("Infrastructure->ExportWorker")


class ExportCancelled(Exception):
    """Raised inside the export callback when the user cancels export (via ``stop()``)."""


class ExportWorker(QThread):
    """
    Background QThread that renders and exports a video session with blurred regions.

    Attributes:
        _export_service (ExportService): Application service that renders the video.
        _s_id (SessionId): Session identifier being exported.
        _output_path (str): Destination file path for the exported video.
        _stop_requested (bool): True after ``stop()`` requests cancellation.

    Note:
        Signals emitted by this worker:
            progress_updated(current_frame, total_frames): Per-frame progress callback.
            succeeded(): Emitted on successful export completion.
            finished_processing(): Emitted when the thread exits.
            cancelled(): Emitted if the user cancels export.
            error_occurred(msg): Emitted on exception.

        Workflow:
            1. ``run()`` calls ``export_service.export_session()``.
            2. The progress callback emits ``progress_updated()`` for each frame.
            3. If ``stop()`` is called, the callback raises ``ExportCancelled`` and the
               thread emits ``cancelled()``.
            4. On success, emit ``succeeded()``.
            5. On error, emit ``error_occurred()``.
            6. Always emit ``finished_processing()`` before exit.

    Example:
        worker = ExportWorker(export_service, s_id, "output.mp4")
        worker.finished_processing.connect(on_finished)
        worker.start()
        worker.stop()
    """

    progress_updated = Signal(int, int)   # (current_frame, total_frames)
    succeeded = Signal()
    finished_processing = Signal()
    cancelled = Signal()
    error_occurred = Signal(str)

    def __init__(
        self,
        export_service: ExportService,
        s_id: SessionId,
        output_path: str,
        parent: QObject | None = None,
    ) -> None:
        """Initialize export worker for ``s_id`` to ``output_path``."""
        super().__init__(parent)
        self._export_service = export_service
        self._s_id = s_id
        self._output_path = output_path
        self._stop_requested = False

    def stop(self) -> None:
        """Request early stop (next progress callback will raise ``ExportCancelled``)."""
        self._stop_requested = True

    def run(self) -> None:
        """
        Main thread loop — export video session with blur overlays.

        Note:
            Workflow:
                1. Call ``export_service.export_session(s_id, output_path, callback)``.
                2. The callback emits progress signals and checks ``_stop_requested``.
                3. If cancelled, catch ``ExportCancelled`` and emit ``cancelled()``.
                4. On success, emit ``succeeded()``.
                5. On error, emit ``error_occurred(msg)``.
                6. Finally, emit ``finished_processing()``.
        """
        logger.info("ExportWorker started: session={}, output={}", self._s_id, self._output_path)
        try:
            self._export_service.export_session(
                self._s_id,
                self._output_path,
                progress_callback=self._emit_progress_or_cancel,
            )
            self.succeeded.emit()
        except ExportCancelled:
            logger.info("ExportWorker cancelled: session={}", self._s_id)
            self.cancelled.emit()
        except Exception as exc:
            logger.opt(exception=True).exception("ExportWorker failed")
            self.error_occurred.emit(str(exc))
        finally:
            self.finished_processing.emit()

    def _emit_progress_or_cancel(self, current_frame: int, total_frames: int) -> None:
        """Progress callback for export service — raise ``ExportCancelled`` if stop requested."""
        if self._stop_requested:
            raise ExportCancelled
        self.progress_updated.emit(current_frame, total_frames)
