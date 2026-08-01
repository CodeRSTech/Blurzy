"""Wrapper around YOLO object detection model — load model and run inference."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from app.infrastructure.detection.model.loader import load_detection_model
from app.shared.logging_cfg import get_logger

if TYPE_CHECKING:
    from app.domain.detection.result import DetectionResult
    from app.infrastructure.detection.model.base import BaseDetectionModel

logger = get_logger("Infrastructure->Video->Detection Engine")


class DetectionEngine:
    """
    Loads and manages a YOLO detection model, converting raw inference output to ``DetectionResult`` objects.

    Attributes:
        _model_name (str): Current YOLO model name, such as ``"yolov8n"``.
        _model (BaseDetectionModel): Loaded detection model instance.

    Note:
        Design:
            - Single responsibility: load or switch model and run inference only.
            - Decoupling: delegates model loading to ``load_detection_model()``.
            - Immutability: ``detect()`` returns a new list and does not mutate state.

    Example:
        engine = DetectionEngine("yolov8n")
        detections: list[DetectionResult] = engine.detect(frame)

        # Switch to a different model at runtime
        engine.set_model("yolov8s")
        detections = engine.detect(frame)
    """
    def __init__(self, model_name: str) -> None:
        """Load a YOLO model by ``model_name`` (e.g., "yolov8n")."""
        logger.info("Initializing DetectionEngine with model {}", model_name)
        self._model_name = model_name
        self._model = self._load_model(model_name)

    def __repr__(self):
        return f"DetectionEngine<model_name={self._model_name}>"

    @property
    def model_name(self) -> str:
        """Return the currently loaded model name."""
        logger.trace("Returning current model name")
        return self._model_name

    def set_model(self, model_name: str) -> None:
        """Switch to a different YOLO model by ``model_name``."""
        logger.trace("Setting detection model to {}", model_name)
        self._model_name = model_name
        self._model = self._load_model(model_name)
        logger.info("Switched detection model to {}", model_name)

    def detect(self, frame: np.ndarray) -> list[DetectionResult]:
        """
        Run YOLO inference on ``frame``, returning list of ``DetectionResult`` objects.

        Note:
            Workflow: raw model output is mapped to ``DetectionResult`` objects and
            returned as a new list.
        """
        logger.trace("Detecting boxes in frame")
        results = self._model.detect(frame, None)

        logger.trace(
            "Detected {} item(s) with {}",
            len(results),
            self._model_name,
        )
        return results

    @staticmethod
    def _load_model(model_name: str) -> BaseDetectionModel:
        """Load YOLO model via factory ``load_detection_model()``."""
        logger.info("Loading detection model {}", model_name)
        return load_detection_model(model_name)
