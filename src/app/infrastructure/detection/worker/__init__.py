"""
Package for worker; implements concrete processing and I/O behind application-facing contracts.

See Also:
    - [`DetectionWorker`][app.infrastructure.detection.worker.detection_worker.DetectionWorker] — implements background inference
    - [`DetectionService`][app.application.services.detection.service.DetectionService] — requests detection workers for sessions

Layer: Infrastructure.
Context: Implements concrete processing and i/o behind application-facing contracts at this architectural boundary.
"""

from .detection_worker import DetectionWorker

__all__ = ["DetectionWorker"]