"""
Factory for loading TorchVision detection model with pretrained weights.

See Also:
    - [`TorchDetectionModel`][app.infrastructure.detection.model.torch.model.TorchDetectionModel] — consumes the loaded model
    - [`DetectionModelError`][app.infrastructure.detection.exceptions.DetectionModelError] — reports loader failures

Layer: Infrastructure.
Context: Implements concrete processing and I/O behind application-facing contracts.
"""

from __future__ import annotations

import importlib
from typing import NamedTuple, TYPE_CHECKING

from app.infrastructure.detection.exceptions import DetectionModelError
from app.shared import get_logger

if TYPE_CHECKING:
    from torch.nn import Module

logger = get_logger("Infrastructure->Detection->Models->TorchModelLoaderFactory")


class LoadedTorchModel(NamedTuple):
    """
    Result of successful TorchVision model loading.

    Layer: Infrastructure.
    Context: Implements concrete processing or I/O behind application-facing contracts.
    """
    model: Module
    labels: list[str]


class TorchModelLoaderFactory:
    """
    Factory for loading TorchVision detection model.

    Layer: Infrastructure.
    Context: Implements concrete processing or I/O behind application-facing contracts.
    """

    @staticmethod
    def create(model_name: str, weights_name: str) -> LoadedTorchModel:
        """
        Load TorchVision model by `model_name` and `weights_name`.

        Returns:
            LoadedTorchModel with loaded model and labels extracted from weights metadata.

        Raises:
            DetectionModelError: If model loading fails.
        """
        try:
            logger.debug("Loading TorchVision model {}", model_name)
            detection_module = importlib.import_module("torchvision.models.detection")

            model_fn = getattr(detection_module, model_name)
            weights_class = getattr(detection_module, weights_name)
            weights = weights_class.DEFAULT

            labels = list(weights.meta["categories"])

            loaded_model = model_fn(weights=weights)
            _ = loaded_model.eval()

            return LoadedTorchModel(model=loaded_model, labels=labels)
        except Exception as exc:
            logger.opt(exception=exc).error(
                "Failed to load TorchVision model {}",
                model_name,
            )
            raise DetectionModelError(f"Failed to load TorchVision model: {model_name}") from exc
