"""Interface contract for creating tracking worker instances.

Layer: Application.
Context: Defines protocol boundaries consumed by application orchestration.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol
if TYPE_CHECKING:
    from app.application.interfaces.tracking.worker_interface import TrackingWorkerInterface
    from app.domain.base.dtypes import ListOfBoxesByFrameIndexAsDict
    from app.domain.session.session_state import SessionState


class TrackingWorkerFactoryInterface(Protocol):
    """Create start-ready tracking workers behind an interface seam.

Layer: Application.
Context: Coordinates use-case behavior through domain services and application contracts.
"""

    def create(
        self,
        strategy_name: str,
        source_data: ListOfBoxesByFrameIndexAsDict,
        session_state: SessionState,
    ) -> TrackingWorkerInterface:
        """Create a worker that tracks detections across video frames.

        Args:
            strategy_name: Tracking algorithm to instantiate.
            source_data: Per-frame detections that the tracker should follow.
            session_state: Session metadata and settings used by tracking.

        Returns:
            Tracking worker implementing the application contract.
        """
        ...
