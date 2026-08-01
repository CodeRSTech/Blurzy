from typing import TYPE_CHECKING

import numpy as np

from app.domain.detection.result import DetectionResult
from app.infrastructure.detection.model.base import BaseDetectionModel
from app.infrastructure.detection.model.mtcnn_torch.loader_factory import MTCNNTorchModelLoaderFactory
from app.infrastructure.detection.model.mtcnn_torch.mapper import MTCNNTorchDetectionMapper
from app.shared import get_logger

if TYPE_CHECKING:
    from facenet_pytorch import MTCNN

logger = get_logger("Infrastructure->Detection->Models->MTCNN")


class MTCNNTorchDetectionModel(BaseDetectionModel):
    """
    MTCNN (facenet-pytorch) face detection model wrapper.

    Attributes:
        _model: Loaded MTCNN instance (facenet_pytorch.MTCNN).
        _loader (MTCNNTorchModelLoaderFactory): Factory for loading the model.
        _mapper (MTCNNTorchDetectionMapper): Mapper for converting raw output to DetectionResult.

    Note:
        Confidence threshold: 0.90 (default).
        Input frames must be RGB ``numpy.ndarray`` (uint8, shape HxWx3).
        Returns detections with label ``"person"``.
    """
    def __init__(
        self,
        loader: MTCNNTorchModelLoaderFactory | None = None,
        mapper: MTCNNTorchDetectionMapper | None = None,
    ) -> None:
        """Initialize MTCNN model."""
        self._loader = loader or MTCNNTorchModelLoaderFactory()
        self._mapper = mapper or MTCNNTorchDetectionMapper()
        self._model = self._load_model()

    def _load_model(self) -> "MTCNN":
        """Load MTCNN model using factory."""
        return self._loader.create()

    def detect(
        self,
        frame: np.ndarray,
        chosen_labels: list[str] | None = None,
    ) -> list[DetectionResult]:
        """
        Run MTCNN face detection on an RGB frame.

        Args:
            frame: RGB numpy array (uint8, HxWx3).
            chosen_labels: Optional label filter; only ``"person"`` detections
                are produced by this model.

        Returns:
            List of DetectionResult instances that pass the confidence threshold
            and optional label filter.
        """
        try:
            from PIL import Image
            pil_image = Image.fromarray(frame)  # frame is already RGB
            boxes, probs = self._model.detect(pil_image)
        except Exception as exc:
            logger.opt(exception=exc).warning("MTCNN Torch inference failed")
            return []

        return self._mapper.map(boxes, probs, chosen_labels)
