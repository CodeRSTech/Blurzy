from __future__ import annotations

from typing import TYPE_CHECKING




from app.infrastructure.detection.model.base import BaseDetectionModel
from app.infrastructure.detection.model.names import DEFAULT_YOLO_CONFIDENCE_THRESHOLD
from app.infrastructure.detection.model.yolo.loader_factory import YoloModelLoaderFactory
from app.infrastructure.detection.model.yolo.mapper import YoloDetectionMapper
from app.shared import get_logger
if TYPE_CHECKING:
    import numpy as np
    from app.domain.detection.result import DetectionResult


if TYPE_CHECKING:
    from ultralytics.models.yolo.model import YOLO

logger = get_logger("Infrastructure->Detection->Models->YOLO")


class YoloDetectionModel(BaseDetectionModel):
    """
    Ultralytics YOLO model wrapper (YOLOv3/v5/v8/v9/v10/v11/v12/v26).

    Attributes:
        _model_file_name (str): Model ``.pt`` file name, such as ``"yolov8n.pt"``.
        _model: Loaded Ultralytics YOLO instance.
        _loader (YoloModelLoaderFactory): Factory for loading model.
        _mapper (YoloDetectionMapper): Mapper for converting raw output to DetectionPayload.

    Note:
        Confidence threshold: ``DEFAULT_YOLO_CONFIDENCE_THRESHOLD`` (0.25).
        IoU threshold: 0.45 for NMS.
        Supported versions: YOLOv3, v5, v8, v9, v10, v11, v12, v26, and their
        variants (tiny, nano, small, medium, large, extra).
    """
    def __init__(
        self,
        model_file_name: str,
        loader: YoloModelLoaderFactory | None = None,
        mapper: YoloDetectionMapper | None = None,
    ) -> None:
        """Initialize Ultralytics YOLO model by ``model_file_name`` (e.g., "yolov8n.pt")."""
        self._model_file_name = model_file_name
        self._loader = loader or YoloModelLoaderFactory()
        self._mapper = mapper or YoloDetectionMapper()
        self._model = self._load_model()

    def _load_model(self) -> YOLO:
        """Load YOLO model using factory."""
        return self._loader.create(self._model_file_name)

    def detect(
        self,
        frame: np.ndarray,
        chosen_labels: list[str] | None = None,
    ) -> list[DetectionResult]:
        """Run YOLO inference, filter by confidence and optional label list."""
        try:
            results = self._model(
                frame,
                verbose=False,
                conf=DEFAULT_YOLO_CONFIDENCE_THRESHOLD,
                iou=0.45,
            )
        except Exception as exc:
            logger.opt(exception=exc).warning("YOLO inference failed")
            return []

        return self._mapper.map(results, chosen_labels)