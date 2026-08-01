"""Factory for loading TorchVision detection model with pretrained weights."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.infrastructure.detection.exceptions import DetectionModelError
from app.shared import get_logger

logger = get_logger("Infrastructure->Detection->Models->MTCNNModelLoaderFactory")

if TYPE_CHECKING:
    from facenet_pytorch import MTCNN


class MTCNNTorchModelLoaderFactory:
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
            logger.debug("Loading MTCNN model")
            import torch
            from facenet_pytorch import MTCNN
            # 1. Automatically select GPU if available, otherwise fallback to CPU
            device = torch.device('cuda:0' if torch.cuda.is_available() else 'cpu')

            # 2. Initialize MTCNN (keep_all=True detects multiple faces)
            mtcnn = MTCNN(keep_all=True, device=device)
            logger.debug("MTCNN model loaded successfully on device {}", device)
            return mtcnn
        except ModuleNotFoundError:
            raise DetectionModelError("Failed to load MTCNN Torch model.\n"
                                      + "Check whether facenet_pytorch and its dependencies are installed.")
        except Exception as exc:
            logger.opt(exception=exc).error("Failed to load MTCNN Torch model")
            raise DetectionModelError("Failed to load MTCNN Torch model") from exc
