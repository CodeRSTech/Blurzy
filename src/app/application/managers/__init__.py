"""Application-layer managers for Phase 1 lifecycle seams.

Managers centralise infrastructure lifecycle operations (engine creation,
worker activation) that previously lived inline inside service methods.
"""

from app.application.managers.detection_engine import DetectionEngineManager
from app.application.managers.session import SessionManager
from app.application.managers.session_initializer import SessionInitializer
from app.application.managers.tracking_worker import TrackingWorkerManager
from app.application.managers.video_decode_worker import VideoDecodeWorkerManager

__all__ = [
    "DetectionEngineManager",
    "SessionManager",
    "SessionInitializer",
    "TrackingWorkerManager",
    "VideoDecodeWorkerManager",
]
