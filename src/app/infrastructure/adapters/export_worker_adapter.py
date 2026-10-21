"""Explicit adapter wrapping `ExportWorker` to `ExportWorkerInterface`.

Layer: Infrastructure.
Context: Implements concrete processing and I/O behind application-facing contracts.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.application.interfaces import ExportWorkerInterface

if TYPE_CHECKING:
    from app.infrastructure.export import ExportWorker


class ExportWorkerAdapter(ExportWorkerInterface):
    """Delegate `ExportWorker` thread control and signals through the interface seam.

Layer: Infrastructure.
Context: Implements concrete processing or I/O behind application-facing contracts.


    Args:
        worker: Concrete export worker wrapped by this adapter.
"""

    def __init__(self, worker: ExportWorker) -> None:
        self._worker = worker

    def __repr__(self) -> str:
        return f"<ExportWorkerAdapter wrapping={self._worker!r}>"

    @property
    def progress_updated(self):
        """Forward the worker progress signal."""
        return self._worker.progress_updated

    @property
    def succeeded(self):
        """Forward the worker success signal."""
        return self._worker.succeeded

    @property
    def finished_processing(self):
        """Forward the worker completion signal."""
        return self._worker.finished_processing

    @property
    def cancelled(self):
        """Forward the worker cancellation signal."""
        return self._worker.cancelled

    @property
    def error_occurred(self):
        """Forward the worker error signal."""
        return self._worker.error_occurred

    def start(self) -> None:
        """Start the wrapped export worker."""
        self._worker.start()

    def stop(self) -> None:
        """Request the wrapped export worker to stop."""
        self._worker.stop()

    def isRunning(self) -> bool:
        """Return whether the worker thread is running.

        Returns:
            `True` while the wrapped export worker is running.
        """
        return self._worker.isRunning()

    def deleteLater(self) -> None:
        """Schedule this Qt object for deletion."""
        self._worker.deleteLater()
