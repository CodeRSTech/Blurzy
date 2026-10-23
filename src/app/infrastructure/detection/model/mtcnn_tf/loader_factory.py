"""
Factory for loading TorchVision detection model with pretrained weights.

See Also:
    - [`MTCNNTFDetectionModel`][app.infrastructure.detection.model.mtcnn_tf.model.MTCNNTFDetectionModel] — consumes the loaded model
    - [`DetectionModelError`][app.infrastructure.detection.exceptions.DetectionModelError] — reports loader failures

Layer: Infrastructure.
Context: Implements concrete processing and I/O behind application-facing contracts.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.infrastructure.detection.exceptions import DetectionModelError
from app.shared import get_logger

logger = get_logger("Infrastructure->Detection->Models->MTCNNModelLoaderFactory")

if TYPE_CHECKING:
    from mtcnn import MTCNN


class MTCNNModelLoaderFactory:
    """
    Factory for loading MTCNN detection model.

    Layer: Infrastructure.
    Context: Implements concrete processing or I/O behind application-facing contracts.
    """

    @staticmethod
    def create() -> MTCNN:
        """
        Load MTCNN model.

        Returns:
            MTCNN Model instance

        Raises:
            DetectionModelError: If model loading fails.
        """
        try:
            from mtcnn import MTCNN
            logger.debug("Loading MTCNN model")
            return MTCNN()
        except ModuleNotFoundError:
            raise DetectionModelError("Failed to load MTCNN model.\n"
                                      + "Check whether MTCNN or its dependencies are installed.")
        except Exception as exc:
            logger.opt(exception=exc).error("Failed to load MTCNN model")
            raise DetectionModelError("Failed to load MTCNN model") from exc
