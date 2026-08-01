"""Explicit adapter wrapping ``DetectionWorker`` to ``DetectionWorkerInterface``."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.application.interfaces import DetectionWorkerInterface

if TYPE_CHECKING:
    from app.domain.detection.result import DetectionResult
    from app.infrastructure.detection.worker.detection_worker import DetectionWorker


class DetectionWorkerAdapter(DetectionWorkerInterface):
    """
    Explicit adapter that wraps a concrete ``DetectionWorker`` instance and
    exposes the ``DetectionWorkerInterface`` contract.

    In normal usage the concrete ``DetectionWorker`` already satisfies
    ``DetectionWorkerInterface`` via structural subtyping (``Protocol``), so
    this adapter is not required for runtime correctness.  It exists to:

    - Provide an explicit, named boundary at the infrastructure/application seam.
    - Enable test doubles that replace the real worker without subclassing ``DetectionWorker``.

    Note:
        Qt signals (``batch_ready``, ``progress_updated``, ``finished_processing``,
        ``error_occurred``) are not part of the interface contract and remain on
        the concrete worker.  Callers that need to connect signals must hold a
        reference to the concrete ``DetectionWorker`` directly.
    """

    def __init__(self, worker: DetectionWorker) -> None:
        self._worker = worker

    def __repr__(self) -> str:
        return f"<DetectionWorkerAdapter wrapping={self._worker!r}>"

    @property
    def batch_ready(self):
        """Expose the Qt signal so existing ``connect`` call-sites work unchanged."""
        return self._worker.batch_ready

    @property
    def progress_updated(self):
        """Expose the Qt signal so existing ``connect`` call-sites work unchanged."""
        return self._worker.progress_updated

    def start(self) -> None:
        self._worker.start()

    def stop(self) -> None:
        self._worker.stop()

    def isRunning(self) -> bool:
        return self._worker.isRunning()

    def is_complete(self) -> bool:
        return self._worker.is_complete()

    def get_detections(self, frame_index: int) -> list[DetectionResult] | None:
        return self._worker.get_detections(frame_index)

    def get_all_detections(self) -> dict[int, list[DetectionResult]]:
        return self._worker.get_all_detections()
