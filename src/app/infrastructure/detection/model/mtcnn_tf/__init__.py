"""Package for mtcnn tf; implements concrete processing and I/O behind application-facing contracts.

See Also:
    - [`MTCNNTFDetectionModel`][app.infrastructure.detection.model.mtcnn_tf.model.MTCNNTFDetectionModel] — implements TensorFlow-backed MTCNN inference
    - [`load_detection_model`][app.infrastructure.detection.model.loader.load_detection_model] — selects the configured detection implementation

Layer: Infrastructure.
Context: Implements concrete processing and i/o behind application-facing contracts at this architectural boundary.
"""

from .model import MTCNNTFDetectionModel

__all__ = ["MTCNNTFDetectionModel"]