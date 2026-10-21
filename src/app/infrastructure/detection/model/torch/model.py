"""Module for model; implements concrete processing and I/O behind application-facing contracts.

Layer: Infrastructure.
Context: Implements concrete processing and i/o behind application-facing contracts at this architectural boundary.
"""




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
        Confidence threshold: `DEFAULT_TORCH_CONFIDENCE_THRESHOLD` (0.50).


Layer: Infrastructure.
Context: Implements concrete processing or I/O behind application-facing contracts.


    Args:
        model_name: Registered name of the detection model.
        weights_name: Name of the model weights to load.
        loader: Backend-specific model loader.
        mapper: TorchVision output mapper that applies confidence/label filtering and creates detection results.
"""
    def __init__(
        self,
        model_name: str,
        weights_name: str,
        loader: TorchModelLoaderFactory | None = None,
        mapper: TorchDetectionMapper | None = None,
    ) -> None:
        """Load the TorchVision model and prepare its inference mapper.

        Args:
            model_name: TorchVision model class name selected by the registry.
            weights_name: Weights enum name passed to the model loader.
            loader: Optional loader override, primarily for tests or alternate backends.
            mapper: Optional `TorchDetectionMapper` override for confidence filtering and result conversion.

        Note:
            If omitted, the loader and mapper are constructed automatically; model
            loading occurs during initialization.
        """
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
        """Run TorchVision inference, filter by confidence and optional label list.

        Args:
            frame: RGB image array converted to a tensor before inference.
            chosen_labels: Optional class labels to retain in the mapped detections.

        Returns:
            TorchVision boxes meeting the confidence threshold and label filter;
            an empty list when the model is not loaded or inference cannot proceed.
        """

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