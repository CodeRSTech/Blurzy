"""Module for detection engine factory; implements concrete processing and I/O behind application-facing contracts.

See Also:
    - [`DetectionEngineFactoryInterface`][app.application.interfaces.detection.engine_factory_interface.DetectionEngineFactoryInterface] — defines the factory boundary
    - [`DetectionEngine`][app.infrastructure.detection.engine.detection_engine.DetectionEngine] — concrete engine created by this factory

Layer: Infrastructure.
Context: Implements concrete processing and i/o behind application-facing contracts at this architectural boundary.
"""


from __future__ import annotations

from typing import TYPE_CHECKING


from app.infrastructure.detection.engine.detection_engine import DetectionEngine
from app.application.interfaces.detection.engine_factory_interface import DetectionEngineFactoryInterface
from app.infrastructure.adapters.detection_engine_adapter import DetectionEngineAdapter
if TYPE_CHECKING:
    from app.application.interfaces import DetectionEngineInterface



# Used in :
#   DetectionEngineManager
#   src/app/infrastructure/detection/__init__.py
#   src/app/infrastructure/detection/engine/__init__.py
class DetectionEngineAdapterFactory(DetectionEngineFactoryInterface):
    """Represent detection engine adapter factory.

Layer: Infrastructure.
Context: Implements concrete processing or I/O behind application-facing contracts.
"""
    def create(self, model_name: str) -> DetectionEngineInterface:
        """Load a detection engine and expose it through the application interface.

        Args:
            model_name: Registered name of the model to load.

        Returns:
            Adapter delegating detection-engine operations to the loaded engine.
        """
        engine = DetectionEngine(model_name)
        return DetectionEngineAdapter(engine)