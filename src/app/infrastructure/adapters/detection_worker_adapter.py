"""
Explicit adapter wrapping `DetectionWorker` to `DetectionWorkerInterface`.

See Also:
    - [`DetectionWorkerInterface`][app.application.interfaces.detection.worker_interface.DetectionWorkerInterface] — defines the exposed worker contract
    - [`DetectionWorker`][app.infrastructure.detection.worker.detection_worker.DetectionWorker] — concrete worker being adapted

Layer: Infrastructure.
Context: Implements concrete processing and I/O behind application-facing contracts.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.application.interfaces import DetectionWorkerInterface

if TYPE_CHECKING:
    from app.domain.detection.result import DetectionResult
    from app.infrastructure.detection.worker.detection_worker import DetectionWorker


class DetectionWorkerAdapter(DetectionWorkerInterface):
    """
    Explicit adapter that wraps a concrete `DetectionWorker` instance and
    exposes the `DetectionWorkerInterface` contract.

    In normal usage the concrete `DetectionWorker` already satisfies
    `DetectionWorkerInterface` via structural subtyping (`Protocol`), so
    this adapter is not required for runtime correctness.  It exists to:

    - Provide an explicit, named boundary at the infrastructure/application seam.
    - Enable test doubles that replace the real worker without subclassing `DetectionWorker`.

    Note:
        Qt signals (`batch_ready`, `progress_updated`, `finished_processing`,
        `error_occurred`) are not part of the interface contract and remain on
        the concrete worker.  Callers that need to connect signals must hold a
        reference to the concrete `DetectionWorker` directly.


    Layer: Infrastructure.
    Context: Implements concrete processing or I/O behind application-facing contracts.


    Args:
        worker: Concrete detection worker wrapped by this adapter.
    """

    def __init__(self, worker: DetectionWorker) -> None:
        self._worker = worker

    def __repr__(self) -> str:
        return f"<DetectionWorkerAdapter wrapping={self._worker!r}>"

    @property
    def batch_ready(self):
        """
        Expose the Qt signal so existing `connect` call-sites work unchanged.
"""
        return self._worker.batch_ready

    @property
    def progress_updated(self):
        """
        Expose the Qt signal so existing `connect` call-sites work unchanged.
"""
        return self._worker.progress_updated

    def start(self) -> None:
        """
        Start the wrapped detection worker.
"""
        self._worker.start()

    def stop(self) -> None:
        """
        Stop the wrapped detection worker.
"""
        self._worker.stop()

    def isRunning(self) -> bool:
        """
        Return whether the worker thread is running.

        Returns:
            `True` while the wrapped detection worker is active.
        """
        return self._worker.isRunning()

    def is_complete(self) -> bool:
        """
        Return whether the worker has processed all frames.

        Returns:
            `True` when detection is complete.
        """
        return self._worker.is_complete()

    def get_detections(self, frame_index: int) -> list[DetectionResult] | None:
        """
        Return cached detections for one frame.

        Args:
            frame_index: Zero-based index of the frame whose detections are requested.

        Returns:
            Detections for the frame, or `None` when the worker has no stored result.
        """
        return self._worker.get_detections(frame_index)

    def get_all_detections(self) -> dict[int, list[DetectionResult]]:
        """
        Return all cached detections grouped by frame index.

        Returns:
            New mapping copied from the wrapped worker's cache.
        """
        return self._worker.get_all_detections()
