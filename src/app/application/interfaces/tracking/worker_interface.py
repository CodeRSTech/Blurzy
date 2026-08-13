"""Interface contract for background tracking worker implementations."""

from __future__ import annotations

from typing import TYPE_CHECKING


from typing import Protocol
if TYPE_CHECKING:
    from app.domain.base.dtypes import ListOfBoxesByFrameIndexAsDict





class TrackingWorkerInterface(Protocol):
    """Abstraction boundary for background multi-object tracking workers."""

    def start(self) -> None:
        """Start the tracking thread."""
        ...

    def stop(self) -> None:
        """Request the tracking thread to stop."""
        ...

    def isRunning(self) -> bool:
        """Return ``True`` while the tracking thread is active."""
        ...

    def get_tracked_data(self) -> ListOfBoxesByFrameIndexAsDict:
        """Return tracked results keyed by frame index."""
        ...
