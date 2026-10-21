# [AUDIT] DOCUMENTATION: Copy-paste error in module docstring
# Says "tracking workers" but this adapter is for "detection workers"
"""Adapt the detection-worker factory contract to infrastructure.

Layer: Application adapter.
Context: Creates the infrastructure worker lazily, keeping its concrete type
behind the application interface.
"""

from __future__ import annotations

from typing import TYPE_CHECKING



from app.application.interfaces.detection.worker_factory_interface import DetectionWorkerFactoryInterface
if TYPE_CHECKING:
    from app.application.interfaces import DetectionWorkerInterface, DetectionEngineInterface
    from app.domain.session import SessionId




class DetectionWorkerFactoryAdapter(DetectionWorkerFactoryInterface):
    """Create concrete `DetectionWorker` instances behind an interface seam.

Layer: Application.
Context: Coordinates use-case behavior through domain services and application contracts.
"""

    def create(
        self,
        session_id: SessionId,
        detection_engine: DetectionEngineInterface
    ) -> DetectionWorkerInterface:
        """Create an infrastructure detection worker behind its interface.

        Args:
            session_id: Session that owns the detection work.
            detection_engine: Engine used to run frame inference.

        Returns:
            Worker adapter implementing `DetectionWorkerInterface`.
        """
        from app.infrastructure.detection import DetectionWorker  # lazy import

        return DetectionWorker(
            s_id=session_id, detection_engine=detection_engine
        )
