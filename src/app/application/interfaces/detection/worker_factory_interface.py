"""Interface contract for creating detection worker instances."""

from __future__ import annotations

from typing import Protocol, TYPE_CHECKING

from app.application.interfaces.detection.engine_interface import DetectionEngineInterface
from app.application.interfaces.detection.worker_interface import DetectionWorkerInterface

if TYPE_CHECKING:
    from app.domain.session.session_id import SessionId


class DetectionWorkerFactoryInterface(Protocol):
    """Create start-ready detection workers behind an interface seam."""

    def create(
        self,
        session_id: SessionId,
        detection_engine: DetectionEngineInterface
    ) -> DetectionWorkerInterface:
        """Build and return a detection worker instance."""
        ...
