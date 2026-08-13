"""Infrastructure-backed factory adapter for tracking workers."""

from __future__ import annotations

from typing import TYPE_CHECKING


from app.application.interfaces import TrackingWorkerFactoryInterface
if TYPE_CHECKING:
    from app.application.interfaces import TrackingWorkerInterface
    from app.domain import ListOfBoxesByFrameIndexAsDict, SessionState




class TrackingWorkerFactoryAdapter(TrackingWorkerFactoryInterface):
    """Create concrete ``TrackingWorker`` instances behind an interface seam."""

    def create(
        self,
        strategy_name: str,
        source_data: ListOfBoxesByFrameIndexAsDict,
        session_state: SessionState,
    ) -> TrackingWorkerInterface:
        from app.infrastructure.tracking import TrackingWorker  # lazy import

        return TrackingWorker(
            strategy_name=strategy_name,
            source_data=source_data,
            session_state=session_state,
            start=True,
        )
