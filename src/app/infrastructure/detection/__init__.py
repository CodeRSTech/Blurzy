"""Object detection infrastructure — YOLO model, detection engine, background worker.

Layer: Infrastructure.
Context: Implements concrete processing and I/O behind application-facing contracts.
"""

from .model import BaseDetectionModel, YoloDetectionModel, TorchDetectionModel, DummyDetectionModel
from .engine import DetectionEngine, DetectionEngineAdapterFactory
from .worker import DetectionWorker

__all__ = ["BaseDetectionModel",
           "YoloDetectionModel",
           "TorchDetectionModel",
           "DummyDetectionModel",
           "DetectionWorker",
           "DetectionEngine",
           "DetectionEngineAdapterFactory"]
