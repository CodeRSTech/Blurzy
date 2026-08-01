from typing import Protocol
from app.application.interfaces.detection.engine_interface import DetectionEngineInterface

class DetectionEngineFactoryInterface(Protocol):
    """
    The `DetectionEngineFactoryInterface`

    ``DetectionEngineFactory`` in `Infrastructure/detection` is instantiated from it,

    which is then used by the ``DetectionEngineManager``.
    """
    def create(self, model_name: str) -> DetectionEngineInterface: ...