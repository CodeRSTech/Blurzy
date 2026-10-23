"""
Interface contract for background tracking worker implementations.

See Also:
    - [`TrackingWorker`][app.infrastructure.tracking.track_worker.TrackingWorker] — implements this worker contract in the background
    - [`TrackingWorkerFactoryAdapter`][app.application.adapters.tracking_worker_factory_adapter.TrackingWorkerFactoryAdapter] — constructs the concrete worker

Layer: Application.
Context: Defines protocol boundaries consumed by application orchestration.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol
if TYPE_CHECKING:
    from app.domain.base.dtypes import ListOfBoxesByFrameIndexAsDict


class TrackingWorkerInterface(Protocol):
    """
    Abstraction boundary for background multi-object tracking workers.

    Layer: Application.
    Context: Coordinates use-case behavior through domain services and application contracts.
    """

    def start(self) -> None:
        """
        Start the tracking thread.
"""
        ...

    def stop(self) -> None:
        """
        Request the tracking thread to stop.
"""
        ...

    def isRunning(self) -> bool:
        """
        Return `True` while the tracking thread is active.

        Returns:
            `True` while the tracking worker thread is running.
        """
        ...

    def get_tracked_data(self) -> ListOfBoxesByFrameIndexAsDict:
        """
        Return tracked results keyed by frame index.

        Returns:
            Mapping from frame indices to the tracked boxes for those frames.
        """
        ...
