"""
Package for yolo; implements concrete processing and I/O behind application-facing contracts.

See Also:
    - [`YoloDetectionModel`][app.infrastructure.detection.model.yolo.model.YoloDetectionModel] — implements Ultralytics inference
    - [`load_detection_model`][app.infrastructure.detection.model.loader.load_detection_model] — selects the configured detection implementation

Layer: Infrastructure.
Context: Implements concrete processing and i/o behind application-facing contracts at this architectural boundary.
"""

from .model import YoloDetectionModel

__all__ = ["YoloDetectionModel"]