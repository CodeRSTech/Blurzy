"""Package for yolo; implements concrete processing and I/O behind application-facing contracts.

Layer: Infrastructure.
Context: Implements concrete processing and i/o behind application-facing contracts at this architectural boundary.
"""

from .model import YoloDetectionModel

__all__ = ["YoloDetectionModel"]