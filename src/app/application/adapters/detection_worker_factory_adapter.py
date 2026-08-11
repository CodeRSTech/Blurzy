# [AUDIT] DOCUMENTATION: Copy-paste error in module docstring
# Says "tracking workers" but this adapter is for "detection workers"
"""Infrastructure-backed factory adapter for detection workers."""

from __future__ import annotations

from typing import TYPE_CHECKING



from app.application.interfaces.detection.worker_factory_interface import DetectionWorkerFactoryInterface
if TYPE_CHECKING:
    from app.application.interfaces import DetectionWorkerInterface, DetectionEngineInterface
    from app.domain.session import SessionId




class DetectionWorkerFactoryAdapter(DetectionWorkerFactoryInterface):
    """Create concrete ``DetectionWorker`` instances behind an interface seam."""

    def create(
        self,
        session_id: SessionId,
        detection_engine: DetectionEngineInterface
    ) -> DetectionWorkerInterface:
        from app.infrastructure.detection import DetectionWorker  # lazy import

        return DetectionWorker(
            s_id=session_id, detection_engine=detection_engine
        )
