"""Annotation domain model — detections, layers, detection sources, context actions.

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
