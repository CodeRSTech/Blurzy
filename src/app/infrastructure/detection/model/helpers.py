from __future__ import annotations

from app.domain.views import ModelSelectionViewModel
from app.infrastructure.detection.model.names import TORCH_MODELS, ULTRALYTICS_YOLO_MODELS, MTCNN_MODELS

DETECTION_MODEL_PROVIDER_ALL = "all"
DETECTION_MODEL_PROVIDER_TORCH = "torch"
DETECTION_MODEL_PROVIDER_YOLO = "yolo"
DETECTION_MODEL_PROVIDER_MTCNN = "mtcnn"

_PROVIDER_LABELS: dict[str, str] = {
    DETECTION_MODEL_PROVIDER_ALL: "All Models",
    DETECTION_MODEL_PROVIDER_TORCH: "Torch models",
    DETECTION_MODEL_PROVIDER_YOLO: "YOLO models",
    DETECTION_MODEL_PROVIDER_MTCNN: "MTCNN models",
}


def get_available_detection_model_names_as_str() -> list[str]:
    """
    Return list of all available model names (Dummy, Torch, YOLO variants).
    """
    return ["None", *TORCH_MODELS.keys(), *ULTRALYTICS_YOLO_MODELS.keys(), *MTCNN_MODELS]


def get_detection_model_provider_options() -> list[tuple[str, str]]:
    """Return provider dropdown options in display order."""
    return list(_PROVIDER_LABELS.items())


def resolve_detection_model_provider(model_name: str) -> str:
    """Map a model name to its provider/family identifier."""
    if model_name == "None":
        return DETECTION_MODEL_PROVIDER_ALL
    if model_name in TORCH_MODELS:
        return DETECTION_MODEL_PROVIDER_TORCH
    if model_name in ULTRALYTICS_YOLO_MODELS:
        return DETECTION_MODEL_PROVIDER_YOLO
    if model_name in MTCNN_MODELS:
        return DETECTION_MODEL_PROVIDER_MTCNN
    return DETECTION_MODEL_PROVIDER_ALL


def get_available_detection_model_names_as_view_model(
    provider_id: str = DETECTION_MODEL_PROVIDER_ALL,
) -> list[ModelSelectionViewModel]:
    """
    Retrieves a list of available detection model with their display names.
    """
    provider_filter = provider_id or DETECTION_MODEL_PROVIDER_ALL
    models: list[ModelSelectionViewModel] = []
    for model_name in get_available_detection_model_names_as_str():
        resolved_provider = resolve_detection_model_provider(model_name)
        if (
            provider_filter != DETECTION_MODEL_PROVIDER_ALL
            and model_name != "None"
            and resolved_provider != provider_filter
        ):
            continue
        models.append(
            ModelSelectionViewModel(
                model_id=model_name,
                display_name=model_name,
                provider_id=resolved_provider,
                provider_display_name=_PROVIDER_LABELS[resolved_provider],
            )
        )
    return models
