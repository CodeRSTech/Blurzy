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
        _mapper (MTCNNTFDetectionMapper): Mapper for converting raw output to DetectionPayload.

    Note:
        Confidence threshold: ``DEFAULT_MTCNN_TF_CONFIDENCE_THRESHOLD`` (0.90).
        IoU threshold: 0.45 for NMS.
        Supported versions: YOLOv3, v5, v8, v9, v10, v11, v12, v26, and their
        variants (tiny, nano, small, medium, large, extra).
    """
    def __init__(
        self,
        loader: MTCNNModelLoaderFactory | None = None,
        mapper: MTCNNTFDetectionMapper | None = None,
    ) -> None:
        """Initialize MTCNN model."""
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
        """Run MTCNN inference, filter by confidence and optional label list."""
        from mtcnn import MTCNN
        try:
            results = MTCNN.detect_faces(image=frame, threshold=DEFAULT_MTCNN_TF_CONFIDENCE_THRESHOLD)
        except Exception as exc:
            logger.opt(exception=exc).warning("MTCNN inference failed")
            return []

        return self._mapper.map(results, chosen_labels)