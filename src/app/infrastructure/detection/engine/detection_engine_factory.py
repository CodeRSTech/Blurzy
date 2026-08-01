from app.application.interfaces import DetectionEngineInterface
from app.infrastructure.detection.engine.detection_engine import DetectionEngine
from app.application.interfaces.detection.engine_factory_interface import DetectionEngineFactoryInterface
from app.infrastructure.adapters.detection_engine_adapter import DetectionEngineAdapter


# Used in :
#   DetectionEngineManager
#   src/app/infrastructure/detection/__init__.py
#   src/app/infrastructure/detection/engine/__init__.py
class DetectionEngineAdapterFactory(DetectionEngineFactoryInterface):
    def create(self, model_name: str) -> DetectionEngineInterface:
        engine = DetectionEngine(model_name)
        return DetectionEngineAdapter(engine)