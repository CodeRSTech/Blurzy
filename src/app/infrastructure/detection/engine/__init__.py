"""
Package for engine; implements concrete processing and I/O behind application-facing contracts.

See Also:
    - [`DetectionEngine`][app.infrastructure.detection.engine.detection_engine.DetectionEngine] — wraps model inference
    - [`DetectionEngineManager`][app.application.managers.detection_engine.DetectionEngineManager] — manages engines per session

Layer: Infrastructure.
Context: Implements concrete processing and i/o behind application-facing contracts at this architectural boundary.
"""

from .detection_engine import DetectionEngine
from .detection_engine_factory import DetectionEngineAdapterFactory

__all__ = ["DetectionEngine", "DetectionEngineAdapterFactory"]