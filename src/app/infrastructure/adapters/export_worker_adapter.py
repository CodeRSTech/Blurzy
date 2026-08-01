"""Explicit adapter wrapping ``ExportWorker`` to ``ExportWorkerInterface``."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.application.interfaces import ExportWorkerInterface

if TYPE_CHECKING:
    from app.infrastructure.export import ExportWorker


class ExportWorkerAdapter(ExportWorkerInterface):
    """Delegate ``ExportWorker`` thread control and signals through the interface seam."""

    def __init__(self, worker: ExportWorker) -> None:
        self._worker = worker

    def __repr__(self) -> str:
        return f"<ExportWorkerAdapter wrapping={self._worker!r}>"

    @property
    def progress_updated(self):
        return self._worker.progress_updated

    @property
    def succeeded(self):
        return self._worker.succeeded

    @property
    def finished_processing(self):
        return self._worker.finished_processing

    @property
    def cancelled(self):
        return self._worker.cancelled

    @property
    def error_occurred(self):
        return self._worker.error_occurred

    def start(self) -> None:
        self._worker.start()

    def stop(self) -> None:
        self._worker.stop()

    def isRunning(self) -> bool:
        return self._worker.isRunning()

    def deleteLater(self) -> None:
        self._worker.deleteLater()
