"""Annotation domain model — detections, layers, detection sources, context actions."""

from .box import Box
from .source import BoxSource
from .context_actions import AnnotationContextActions
from .result import DetectionResult

__all__ = ['Box',
           'BoxSource',
           'AnnotationContextActions',
           'DetectionResult']
