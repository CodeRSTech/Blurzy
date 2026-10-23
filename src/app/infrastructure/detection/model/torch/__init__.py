"""
Package for torch; implements concrete processing and I/O behind application-facing contracts.

See Also:
    - [`TorchDetectionModel`][app.infrastructure.detection.model.torch.model.TorchDetectionModel] — implements TorchVision inference
    - [`load_detection_model`][app.infrastructure.detection.model.loader.load_detection_model] — selects the configured detection implementation

Layer: Infrastructure.
Context: Implements concrete processing and i/o behind application-facing contracts at this architectural boundary.
"""

from .model import TorchDetectionModel

__all__ = ["TorchDetectionModel"]