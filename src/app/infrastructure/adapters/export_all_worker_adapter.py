"""
Explicit adapter wrapping `ExportAllWorker` to `ExportAllWorkerInterface`.

See Also:
    - [`ExportAllWorkerInterface`][app.application.interfaces.export_all.worker_interface.ExportAllWorkerInterface] — defines the exposed worker contract
    - [`ExportAllWorker`][app.infrastructure.export.export_all_worker.ExportAllWorker] — concrete worker being adapted

Layer: Infrastructure.
Context: Implements concrete processing and I/O behind application-facing contracts.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.application.interfaces import ExportAllWorkerInterface

if TYPE_CHECKING:
    from app.infrastructure.export import ExportAllWorker


class ExportAllWorkerAdapter(ExportAllWorkerInterface):
    """
    Delegate `ExportAllWorker` thread control and signals through the interface seam.

    Layer: Infrastructure.
    Context: Implements concrete processing or I/O behind application-facing contracts.


    Args:
        worker: Concrete batch-export worker wrapped by this adapter.
    """

    def __init__(self, worker: ExportAllWorker) -> None:
        self._worker = worker

    def __repr__(self) -> str:
        return f"<ExportAllWorkerAdapter wrapping={self._worker!r}>"

    @property
    def session_started(self):
        """
        Forward the batch worker session-started signal.
"""
        return self._worker.session_started

    @property
    def session_finished(self):
        """
        Forward the batch worker session-finished signal.
"""
        return self._worker.session_finished

    @property
    def session_failed(self):
        """
        Forward the batch worker session-failed signal.
"""
        return self._worker.session_failed

    @property
    def progress_updated(self):
        """
        Forward the worker progress signal.
"""
        return self._worker.progress_updated

    @property
    def session_export_progress_updated(self):
        """
        Forward per-session export progress.
"""
        return self._worker.session_export_progress_updated

    @property
    def finished_processing(self):
        """
        Forward the worker completion signal.
"""
        return self._worker.finished_processing

    @property
    def cancelled(self):
        """
        Forward the worker cancellation signal.
"""
        return self._worker.cancelled

    def start(self) -> None:
        """
        Start the wrapped batch-export worker.
"""
        self._worker.start()

    def stop(self) -> None:
        """
        Request the wrapped batch-export worker to stop.
"""
        self._worker.stop()

    def isRunning(self) -> bool:
        """
        Return whether the worker thread is running.

        Returns:
            `True` while the wrapped batch-export worker is running.
        """
        return self._worker.isRunning()

    def deleteLater(self) -> None:
        """
        Schedule this Qt object for deletion.
"""
        self._worker.deleteLater()
