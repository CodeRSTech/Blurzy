"""Detection model factory and polymorphic implementations (Torch, YOLO, Dummy)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.infrastructure.detection.exceptions import DetectionModelError
from app.infrastructure.detection.model.dummy import DummyDetectionModel
from app.infrastructure.detection.model.mtcnn_tf import MTCNNTFDetectionModel
from app.infrastructure.detection.model.mtcnn_torch import MTCNNTorchDetectionModel
from app.infrastructure.detection.model.names import (
    TORCH_MODELS,
    ULTRALYTICS_YOLO_MODELS,
    MTCNN_MODELS,
)
from app.infrastructure.detection.model.torch import TorchDetectionModel
from app.infrastructure.detection.model.yolo import YoloDetectionModel
from app.shared.logging_cfg import get_logger

if TYPE_CHECKING:
    from app.infrastructure.detection.model.base import BaseDetectionModel

logger = get_logger("Infrastructure->Detection->Models")


def load_detection_model(model_name: str) -> BaseDetectionModel:
    """
    Factory function — return appropriate ``BaseDetectionModel`` instance by ``model_name``.

    Note:
        Routing:
            - ``"None"`` -> ``DummyDetectionModel()``.
            - Torch model names -> ``TorchDetectionModel(...)``.
            - YOLO model names -> ``YoloDetectionModel(...)``.

    Raises:
        DetectionModelError: If ``model_name`` is unknown.
    """
    if model_name == "None":
        return DummyDetectionModel()

    if model_name in TORCH_MODELS:
        torch_model_name, weights_name = TORCH_MODELS[model_name]
        return TorchDetectionModel(torch_model_name, weights_name)

    if model_name in ULTRALYTICS_YOLO_MODELS:
        return YoloDetectionModel(ULTRALYTICS_YOLO_MODELS[model_name])

    if model_name in MTCNN_MODELS and model_name == "MTCNN-Tensorflow":
        return MTCNNTFDetectionModel()

    if model_name in MTCNN_MODELS and model_name == "MTCNN-Pytorch":
        return MTCNNTorchDetectionModel()

    raise DetectionModelError(f"Unknown detection model: {model_name}")
