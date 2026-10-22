"""Module for exceptions; implements concrete processing and I/O behind application-facing contracts.

See Also:
    - [`load_detection_model`][app.infrastructure.detection.model.loader.load_detection_model] — reports model-loading failures
    - [`DetectionEngine`][app.infrastructure.detection.engine.detection_engine.DetectionEngine] — consumes model-loading errors

Layer: Infrastructure.
Context: Implements concrete processing and i/o behind application-facing contracts at this architectural boundary.
"""

from __future__ import annotations


class DetectionModelError(Exception):
    """Raised when model loading or inference fails.

Layer: Infrastructure.
Context: Implements concrete processing or I/O behind application-facing contracts.
"""
    pass
