"""
Interface contract for background detection worker implementations.

See Also:
    - [`DetectionWorkerAdapter`][app.infrastructure.adapters.detection_worker_adapter.DetectionWorkerAdapter] — adapts worker operations to this contract
    - [`DetectionWorker`][app.infrastructure.detection.worker.detection_worker.DetectionWorker] — performs detection in the background

Layer: Application.
Context: Defines protocol boundaries consumed by application orchestration.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from PySide6.QtCore import SignalInstance

if TYPE_CHECKING:
    from app.domain.detection.result import DetectionResult


class DetectionWorkerInterface(Protocol):
    """
    Abstraction boundary for background YOLO/ML detection worker threads.

    Implementations must be startable, stoppable, and expose cached detection
    results per frame index.  Signals (`batch_ready`, `progress_updated`,
    etc.) remain on the concrete class and are connected by the orchestrating
    service; they are intentionally outside this minimal interface.


    Layer: Application.
    Context: Coordinates use-case behavior through domain services and application contracts.
    """
    progress_updated = SignalInstance
    finished_processing = SignalInstance
    error_occurred = SignalInstance
    batch_ready = SignalInstance

    def start(self) -> None:
        """
        Start the detection thread.
        """
        ...

    def stop(self) -> None:
        """
        Request the detection thread to stop.
        """
        ...

    def isRunning(self) -> bool:
        """
        Return `True` while the worker thread is processing frames.

        Returns:
            `True` while the detection worker thread is active.
        """
        ...

    def is_complete(self) -> bool:
        """
        Return `True` after the full frame stream has been processed.

        Returns:
            `True` once the worker has processed the complete frame stream.
        """
        ...

    def get_detections(self, frame_index: int) -> list[DetectionResult] | None:
        """
        Return cached detections for `frame_index`, or `None` if not yet processed.

        Args:
            frame_index: Zero-based index of the frame to query.

        Returns:
            Detections cached for the frame, or `None` if no result is available.
        """
        ...

    def get_all_detections(self) -> dict[int, list[DetectionResult]]:
        """
        Return a copy of all cached detections keyed by frame index.

        Returns:
            New dictionary mapping processed frame indices to detection results.
        """
        ...
