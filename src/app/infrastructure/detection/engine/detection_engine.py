"""``DetectionEngine`` is the application-facing wrapper around a detection model.
It loads the named model when created, then passes each image or frame to that model’s ``detect()`` method and
returns the resulting ``DetectionResult`` list. It can also replace the active model at runtime with ``set_model()``.

!!! quote "Simple explanation"

    A ``DetectionEngine`` takes an input image and returns a list of detected objects as ``List[DetectionResult]``

The engine itself does not appear to perform image preprocessing, inference, or result conversion:
those responsibilities are delegated to the loaded model implementation.
In this code, ``detect()`` returns the model’s results directly,
so the docstring’s reference to mapping raw output to ``DetectionResult``
objects describes the expected model-layer behavior, not a conversion performed by the engine."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.infrastructure.detection.model.loader import load_detection_model
from app.shared.logging_cfg import get_logger

if TYPE_CHECKING:
    import numpy as np
    from app.domain.detection.result import DetectionResult
    from app.infrastructure.detection.model.base import BaseDetectionModel

logger = get_logger("Infrastructure->Video->Detection Engine")


class DetectionEngine:
    """
    Loads and manages a detection model, converting raw inference output to ``DetectionResult`` objects.
    The generated API page lists supported model names from the model registry.

    Attributes:
        _model_name (str): Current detection model name, such as ``"YOLOv8n"``.
        _model (BaseDetectionModel): Loaded detection model instance.

    Design:
        - Single responsibility: load or switch model and run inference only.
        - Decoupling: delegates model loading to ``load_detection_model()``.
        - Immutability: ``detect()`` returns a new list and does not mutate view_state.

    Example:

    ```python title="example.py"
    engine = DetectionEngine("YOLOv8n")
    detections: list[DetectionResult] = engine.detect(frame)

    engine.set_model("YOLOv8s")  # Switch to a different model at runtime
    detections = engine.detect(frame)
    ```
    """
    def __init__(self, model_name: str) -> None:
        """Load a detection model by ``model_name`` (e.g., "YOLOv8n")."""
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
        """Switch to a different detection model by ``model_name``."""
        logger.trace("Setting detection model to {}", model_name)
        self._model_name = model_name
        self._model = self._load_model(model_name)
        logger.info("Switched detection model to {}", model_name)

    def detect(self, frame: np.ndarray) -> list[DetectionResult]:
        """
        Run detection model inference on ``frame``, returning list of ``DetectionResult`` objects.

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
        """Load detection model via factory ``load_detection_model()``."""
        logger.info("Loading detection model {}", model_name)
        return load_detection_model(model_name)
