"""Module for model; implements concrete processing and I/O behind application-facing contracts.

Layer: Infrastructure.
Context: Implements concrete processing and i/o behind application-facing contracts at this architectural boundary.
"""

from __future__ import annotations

from typing import TYPE_CHECKING




from app.infrastructure.detection.model.base import BaseDetectionModel
from app.infrastructure.detection.model.names import DEFAULT_MTCNN_TF_CONFIDENCE_THRESHOLD
from app.infrastructure.detection.model.mtcnn_tf.loader_factory import MTCNNModelLoaderFactory
from app.infrastructure.detection.model.mtcnn_tf.mapper import MTCNNTFDetectionMapper
from app.shared import get_logger
if TYPE_CHECKING:
    import numpy as np
    from app.domain.detection.result import DetectionResult


if TYPE_CHECKING:
    from mtcnn import MTCNN


logger = get_logger("Infrastructure->Detection->Models->MTCNN")


class MTCNNTFDetectionModel(BaseDetectionModel):
    """
    MTCNN model wrapper.


    Attributes:
        _model: Loaded MTCNN instance.
        _loader (MTCNNModelLoaderFactory): Factory for loading model.
        _mapper (MTCNNTFDetectionMapper): Applies the face confidence threshold and maps face-result dictionaries.

    Note:
        Face detections are filtered using
        `DEFAULT_MTCNN_TF_CONFIDENCE_THRESHOLD` (0.90); returned labels are
        `"person"`.


Layer: Infrastructure.
Context: Implements concrete processing or I/O behind application-facing contracts.


    Args:
        loader: Backend-specific model loader.
        mapper: TensorFlow MTCNN mapper that filters face scores and converts boxes to person detections.
"""
    def __init__(
        self,
        loader: MTCNNModelLoaderFactory | None = None,
        mapper: MTCNNTFDetectionMapper | None = None,
    ) -> None:
        """Load the TensorFlow MTCNN model and prepare its result mapper.

        Args:
            loader: Optional MTCNN loader override.
            mapper: Optional `MTCNNTFDetectionMapper` override for face-result mappings.

        Note:
            Default loader and mapper instances are created when these arguments
            are omitted; model loading occurs during initialization.
        """
        self._loader = loader or MTCNNModelLoaderFactory()
        self._mapper = mapper or MTCNNTFDetectionMapper()
        self._model = self._load_model()

    def _load_model(self) -> MTCNN:
        """Load MTCNN model using factory."""
        return self._loader.create()

    def detect(
        self,
        frame: np.ndarray,
        chosen_labels: list[str] | None = None,
    ) -> list[DetectionResult]:
        """Run MTCNN inference, filter by confidence and optional label list.

        Args:
            frame: RGB image array to process.
            chosen_labels: Optional labels to retain in the mapped detections.

        Returns:
            MTCNN detections meeting the confidence threshold and label filter.
            Returns an empty list if inference fails.
        """
        from mtcnn import MTCNN
        try:
            results = MTCNN.detect_faces(image=frame, threshold=DEFAULT_MTCNN_TF_CONFIDENCE_THRESHOLD)
        except Exception as exc:
            logger.opt(exception=exc).warning("MTCNN inference failed")
            return []

        return self._mapper.map(results, chosen_labels)