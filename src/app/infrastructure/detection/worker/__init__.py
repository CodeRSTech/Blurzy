"""Package for worker; implements concrete processing and I/O behind application-facing contracts.

Layer: Infrastructure.
Context: Implements concrete processing and i/o behind application-facing contracts at this architectural boundary.
"""

from .detection_worker import DetectionWorker

__all__ = ["DetectionWorker"]