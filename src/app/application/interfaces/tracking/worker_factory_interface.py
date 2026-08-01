"""Interface contract for creating tracking worker instances."""

from __future__ import annotations

from typing import Protocol

from app.application.interfaces.tracking.worker_interface import TrackingWorkerInterface
from app.domain.base.dtypes import ListOfBoxesByFrameIndexAsDict
from app.domain.session.session_state import SessionState


class TrackingWorkerFactoryInterface(Protocol):
    """Create start-ready tracking workers behind an interface seam."""

    def create(
        self,
        strategy_name: str,
        source_data: ListOfBoxesByFrameIndexAsDict,
        session_state: SessionState,
    ) -> TrackingWorkerInterface:
        """Build and return a tracking worker instance."""
        ...
