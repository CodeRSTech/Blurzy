"""
Infrastructure layer — workers, video decoding, model loading, session data management.

See Also:
    - [`Session`][app.infrastructure.session.session.Session] — composes runtime session collaborators
    - [`SessionInitializer`][app.application.managers.session_initializer.SessionInitializer] — initializes infrastructure resources for each session


Layer: Infrastructure.
Context: Implements concrete processing and I/O behind application-facing contracts.
"""

from .dtypes import RGBFrame  # depends on numpy only
from .video import VideoReader, VideoDecodeWorker # reader depends on dtypes, worker depends on reader and dtypes
from .session import Session, SessionDataStore # depends on the above
# tracking is independent
from .tracking import TrackingWorker
# export workers depend on nothing
from .export import ExportWorker, ExportAllWorker
from .detection import BaseDetectionModel, YoloDetectionModel, TorchDetectionModel, DummyDetectionModel, \
    DetectionWorker, DetectionEngine, DetectionEngineAdapterFactory
# adapters depend on entire infrastructure
from .adapters import DetectionEngineAdapter, DetectionWorkerAdapter, ExportAllWorkerAdapter, ExportWorkerAdapter, \
    VideoDecodeWorkerControlAdapter
from .views import list_of_session_list_view_models

__all__ = ["RGBFrame",
           "VideoReader",
           "VideoDecodeWorker",
           "Session",
           "SessionDataStore",
           "TrackingWorker",
           "ExportWorker",
           "ExportAllWorker",
           "BaseDetectionModel",
           "YoloDetectionModel",
           "TorchDetectionModel",
           "DummyDetectionModel",
           "DetectionWorker",
           "DetectionEngine",
           "DetectionEngineAdapterFactory",
           "DetectionEngineAdapter",
           "DetectionWorkerAdapter",
           "ExportAllWorkerAdapter",
           "ExportWorkerAdapter",
           "VideoDecodeWorkerControlAdapter",
           "list_of_session_list_view_models"]
