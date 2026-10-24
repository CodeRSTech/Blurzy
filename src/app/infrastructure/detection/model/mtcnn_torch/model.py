"""
Module for model; implements concrete processing and I/O behind application-facing contracts.

See Also:
    - [`BaseDetectionModel`][app.infrastructure.detection.model.base.BaseDetectionModel] — common model contract
    - [`MTCNNTorchModelLoaderFactory`][app.infrastructure.detection.model.mtcnn_torch.loader_factory.MTCNNTorchModelLoaderFactory] — loads the underlying model

Layer: Infrastructure.
Context: Implements concrete processing and i/o behind application-facing contracts at this architectural boundary.
"""

from __future__ import annotations

from typing import TYPE_CHECKING



from app.infrastructure.detection.model.base import BaseDetectionModel
from app.infrastructure.detection.model.mtcnn_torch.loader_factory import MTCNNTorchModelLoaderFactory
from app.infrastructure.detection.model.mtcnn_torch.mapper import MTCNNTorchDetectionMapper
from app.shared import get_logger
if TYPE_CHECKING:
    import numpy as np
    from app.domain.detection.result import DetectionResult


if TYPE_CHECKING:
    from facenet_pytorch import MTCNN

logger = get_logger("Infrastructure->Detection->Models->MTCNN")


class MTCNNTorchDetectionModel(BaseDetectionModel):
    """
    MTCNN (facenet-pytorch) face detection model wrapper.

    Attributes:
        _model: Loaded MTCNN instance (facenet_pytorch.MTCNN).
        _loader (MTCNNTorchModelLoaderFactory): Factory for loading the model.
        _mapper (MTCNNTorchDetectionMapper): Applies the face confidence threshold and maps boxes to person detections.

    Note:
        Confidence threshold: 0.90 (default).
        Input frames must be RGB `numpy.ndarray` (uint8, shape HxWx3).
        Returns detections with label `"person"`.


    Layer: Infrastructure.
    Context: Implements concrete processing or I/O behind application-facing contracts.


    Args:
        loader: Backend-specific model loader.
        mapper: MTCNN mapper that filters face scores and converts boxes to person detections.
    """
    def __init__(
        self,
        loader: MTCNNTorchModelLoaderFactory | None = None,
        mapper: MTCNNTorchDetectionMapper | None = None,
    ) -> None:
        """
        Load the facenet-pytorch MTCNN model and prepare its result mapper.

        Args:
            loader: Optional MTCNN loader override.
            mapper: Optional `MTCNNTorchDetectionMapper` override for face boxes and confidence scores.

        Note:
            Default loader and mapper instances are created when these arguments
            are omitted; model loading occurs during initialization.
        """
        self._loader = loader or MTCNNTorchModelLoaderFactory()
        self._mapper = mapper or MTCNNTorchDetectionMapper()
        self._model = self._load_model()

    def _load_model(self) -> "MTCNN":
        """
        Load MTCNN model using factory.
        """
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
            chosen_labels: Optional label filter; only `"person"` detections
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
