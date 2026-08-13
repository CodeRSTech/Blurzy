


from __future__ import annotations

from typing import TYPE_CHECKING


from app.infrastructure.detection.model.base import BaseDetectionModel
from app.infrastructure.detection.model.torch.loader_factory import TorchModelLoaderFactory
from app.infrastructure.detection.model.torch.mapper import TorchDetectionMapper
from app.shared import get_logger
if TYPE_CHECKING:
    import numpy as np
    from app.domain.detection import Box


logger = get_logger("Infrastructure->Detection->Models->Torch")


class TorchDetectionModel(BaseDetectionModel):
    """
    TorchVision object detection model wrapper (FCOS, FasterRCNN, RetinaNet, SSD, etc.).

    Attributes:
        _model_name (str): Model class name.
        _weights_name (str): Weights class name.
        labels (list[str] | None): Class names from pretrained weights metadata.
        _model: Loaded TorchVision model instance.
        _loader (TorchModelLoaderFactory): Factory for loading model.
        _mapper (TorchDetectionMapper): Mapper for converting raw output to DetectionPayload.

    Note:
        Confidence threshold: ``DEFAULT_TORCH_CONFIDENCE_THRESHOLD`` (0.50).
    """
    def __init__(
        self,
        model_name: str,
        weights_name: str,
        loader: TorchModelLoaderFactory | None = None,
        mapper: TorchDetectionMapper | None = None,
    ) -> None:
        """Initialize TorchVision model by ``model_name`` and ``weights_name``."""
        self._model_name = model_name
        self._weights_name = weights_name
        self._loader = loader or TorchModelLoaderFactory()
        self._mapper = mapper or TorchDetectionMapper()
        self.labels = None
        self._model = None
        self._load_model()

    def _load_model(self) -> None:
        """Load TorchVision model using factory."""
        loaded = self._loader.create(self._model_name, self._weights_name)
        self._model = loaded.model
        self.labels = loaded.labels

    def detect(
        self,
        frame: np.ndarray,
        chosen_labels: list[str] | None = None,
    ) -> list[Box]:
        """Run TorchVision inference, filter by confidence and optional label list."""

        if self._model is None or self.labels is None:
            return []

        try:
            from torchvision.transforms.functional import to_tensor
            img_tensor = to_tensor(frame)
        except Exception as exc:
            logger.opt(exception=exc).warning("Failed to convert frame to tensor")
            return []

        from torch import no_grad
        with no_grad():
            results = self._model([img_tensor])[0]

        return self._mapper.map(results, self.labels, chosen_labels)