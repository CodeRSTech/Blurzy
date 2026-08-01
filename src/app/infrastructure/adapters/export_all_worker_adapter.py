"""Explicit adapter wrapping ``ExportAllWorker`` to ``ExportAllWorkerInterface``."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.application.interfaces import ExportAllWorkerInterface

if TYPE_CHECKING:
    from app.infrastructure.export import ExportAllWorker


class ExportAllWorkerAdapter(ExportAllWorkerInterface):
    """Delegate ``ExportAllWorker`` thread control and signals through the interface seam."""

    def __init__(self, worker: ExportAllWorker) -> None:
        self._worker = worker

    def __repr__(self) -> str:
        return f"<ExportAllWorkerAdapter wrapping={self._worker!r}>"

    @property
    def session_started(self):
        return self._worker.session_started

    @property
    def session_finished(self):
        return self._worker.session_finished

    @property
    def session_failed(self):
        return self._worker.session_failed

    @property
    def progress_updated(self):
        return self._worker.progress_updated

    @property
    def session_export_progress_updated(self):
        return self._worker.session_export_progress_updated

    @property
    def finished_processing(self):
        return self._worker.finished_processing

    @property
    def cancelled(self):
        return self._worker.cancelled

    def start(self) -> None:
        self._worker.start()

    def stop(self) -> None:
        self._worker.stop()

    def isRunning(self) -> bool:
        return self._worker.isRunning()

    def deleteLater(self) -> None:
        self._worker.deleteLater()
