"""
Infrastructure-backed factory adapter for tracking workers.

Based on the
[`TrackingWorkerFactoryInterface`][app.application.interfaces.tracking.worker_factory_interface.TrackingWorkerFactoryInterface]
interface contract, this adapter creates concrete
[`TrackingWorker`][app.infrastructure.tracking.track_worker.TrackingWorker]
instances behind an interface seam.


Layer: Application.
Context: Adapts infrastructure implementations to application contracts.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.application.interfaces import TrackingWorkerFactoryInterface
if TYPE_CHECKING:
    from app.application.interfaces import TrackingWorkerInterface
    from app.domain import ListOfBoxesByFrameIndexAsDict, SessionState


class TrackingWorkerFactoryAdapter(TrackingWorkerFactoryInterface):
    """Create concrete `TrackingWorker` instances behind an interface seam.

Layer: Application.
Context: Coordinates use-case behavior through domain services and application contracts.
"""

    def create(
        self,
        strategy_name: str,
        source_data: ListOfBoxesByFrameIndexAsDict,
        session_state: SessionState,
    ) -> TrackingWorkerInterface:
        """Build and return a `TrackingWorker` instance.

        Args:
            strategy_name: Tracking algorithm to instantiate.
            source_data: Per-frame detections that the tracker should follow.
            session_state: Session metadata and settings used by tracking.

        Returns:
            Tracking worker implementing `TrackingWorkerInterface`.
        """
        from app.infrastructure.tracking import TrackingWorker  # lazy import

        return TrackingWorker(
            strategy_name=strategy_name,
            source_data=source_data,
            session_state=session_state,
            start=True,
        )
