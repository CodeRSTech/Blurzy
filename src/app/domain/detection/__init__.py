"""
Annotation domain model — detections, layers, detection sources, context actions.

See Also:
    - [`Box`][app.domain.detection.box.Box] — shared detection and tracking geometry
    - [`DetectionResult`][app.domain.detection.result.DetectionResult] — domain record for model output

Layer: Domain.
Context: Defines application concepts independently of UI and infrastructure implementations.
"""

from .box import Box
from .source import BoxSource
from .context_actions import AnnotationContextActions
from .result import DetectionResult

__all__ = ['Box',
           'BoxSource',
           'AnnotationContextActions',
           'DetectionResult']
