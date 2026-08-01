"""Interface contract for background detection worker implementations."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from PySide6.QtCore import SignalInstance

if TYPE_CHECKING:
    from app.domain.detection.result import DetectionResult


class DetectionWorkerInterface(Protocol):
    """
    Abstraction boundary for background YOLO/ML detection worker threads.

    Implementations must be startable, stoppable, and expose cached detection
    results per frame index.  Signals (``batch_ready``, ``progress_updated``,
    etc.) remain on the concrete class and are connected by the orchestrating
    service; they are intentionally outside this minimal interface.
    """
    progress_updated = SignalInstance
    finished_processing = SignalInstance
    error_occurred = SignalInstance
    batch_ready = SignalInstance

    def start(self) -> None:
        """Start the detection thread."""
        ...

    def stop(self) -> None:
        """Request the detection thread to stop."""
        ...

    def isRunning(self) -> bool:
        """Return ``True`` while the worker thread is processing frames."""
        ...

    def is_complete(self) -> bool:
        """Return ``True`` after the full frame stream has been processed."""
        ...

    def get_detections(self, frame_index: int) -> list[DetectionResult] | None:
        """Return cached detections for ``frame_index``, or ``None`` if not yet processed."""
        ...

    def get_all_detections(self) -> dict[int, list[DetectionResult]]:
        """Return a copy of all cached detections keyed by frame index."""
        ...
