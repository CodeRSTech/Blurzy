"""
Interface contract for creating detection worker instances.

See Also:
    - [`DetectionWorkerFactoryAdapter`][app.application.adapters.detection_worker_factory_adapter.DetectionWorkerFactoryAdapter] — creates concrete detection workers
    - [`DetectionWorker`][app.infrastructure.detection.worker.detection_worker.DetectionWorker] — concrete worker type

Layer: Application.
Context: Defines protocol boundaries consumed by application orchestration.
"""

from __future__ import annotations

from typing import TYPE_CHECKING


from typing import Protocol, TYPE_CHECKING
if TYPE_CHECKING:
    from app.application.interfaces.detection.engine_interface import DetectionEngineInterface
    from app.application.interfaces.detection.worker_interface import DetectionWorkerInterface




if TYPE_CHECKING:
    from app.domain.session.session_id import SessionId


class DetectionWorkerFactoryInterface(Protocol):
    """
    Create start-ready detection workers behind an interface seam.

    Layer: Application.
    Context: Coordinates use-case behavior through domain services and application contracts.
    """

    def create(
        self,
        session_id: SessionId,
        detection_engine: DetectionEngineInterface
    ) -> DetectionWorkerInterface:
        """
        Create a worker that runs detection for a session.

        Args:
            session_id: Session whose frames the worker will process.
            detection_engine: Model engine used to detect objects in each frame.

        Returns:
            Detection worker implementing the application contract.
        """
        ...
