"""
Package for mtcnn torch; implements concrete processing and I/O behind application-facing contracts.

See Also:
    - [`MTCNNTorchDetectionModel`][app.infrastructure.detection.model.mtcnn_torch.model.MTCNNTorchDetectionModel] — implements PyTorch-backed MTCNN inference
    - [`load_detection_model`][app.infrastructure.detection.model.loader.load_detection_model] — selects the configured detection implementation

Layer: Infrastructure.
Context: Implements concrete processing and i/o behind application-facing contracts at this architectural boundary.
"""

from .model import MTCNNTorchDetectionModel

__all__ = ["MTCNNTorchDetectionModel"]