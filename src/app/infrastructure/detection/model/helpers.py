from __future__ import annotations

from app.domain.views import ModelSelectionViewModel
from app.infrastructure.detection.model.names import TORCH_MODELS, ULTRALYTICS_YOLO_MODELS, MTCNN_MODELS


def get_available_detection_model_names_as_str() -> list[str]:
    """
    Return list of all available model names (Dummy, Torch, YOLO variants).
    """
    return ["None", *TORCH_MODELS.keys(), *ULTRALYTICS_YOLO_MODELS.keys(), *MTCNN_MODELS]


def get_available_detection_model_names_as_view_model() -> list[ModelSelectionViewModel]:
    """
    Retrieves a list of available detection model with their display names.
    """
    return [
        ModelSelectionViewModel(model_id=n, display_name=n)
        for n in get_available_detection_model_names_as_str()
    ]
