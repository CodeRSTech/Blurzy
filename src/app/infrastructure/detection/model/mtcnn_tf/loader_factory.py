"""Factory for loading TorchVision detection model with pretrained weights."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.infrastructure.detection.exceptions import DetectionModelError
from app.shared import get_logger

logger = get_logger("Infrastructure->Detection->Models->MTCNNModelLoaderFactory")

if TYPE_CHECKING:
    from mtcnn import MTCNN


class MTCNNModelLoaderFactory:
    """Factory for loading MTCNN detection model."""

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
