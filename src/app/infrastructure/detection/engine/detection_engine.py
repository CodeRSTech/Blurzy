"""
Application-facing model loading and frame-detection delegation.

The engine selects a provider through
[`load_detection_model`][app.infrastructure.detection.model.loader.load_detection_model]
and returns that provider's results directly. Preprocessing, inference, and
conversion to domain results belong to the
[`BaseDetectionModel`][app.infrastructure.detection.model.base.BaseDetectionModel]
implementation, not this wrapper.

Layer: Infrastructure.
Context: Implements concrete processing and I/O behind application-facing contracts.
"""

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
    Manage one model instance and delegate synchronous frame inference to it.

    The generated API page lists registered model names. Model construction and
    inference run in the calling thread; application workers are responsible for
    keeping expensive operations off the GUI thread. This wrapper adds no
    synchronization or result copying.

    !!! note "Provider requirements"

        Real models may load or acquire weights and require compatible runtimes
        or hardware. Input handling and inference-failure behavior are
        provider-specific; some providers log failures and return an empty list.

    Examples:
        Given a NumPy `frame` prepared for the selected provider:

        ```python
        from app.infrastructure.detection.engine.detection_engine import DetectionEngine

        engine = DetectionEngine("YOLOv8n")
        detections = engine.detect(frame)
        engine.set_model("YOLOv8s")
        ```

        This illustrative example may require model weights; documentation
        builds do not execute it.
    """
    def __init__(self, model_name: str) -> None:
        """Load the named provider synchronously.

        Args:
            model_name: Registered model name, or `"None"` for the dummy model.

        Raises:
            app.infrastructure.detection.exceptions.DetectionModelError: If the
                name is not registered.

        Provider construction errors propagate without translation.
        """
        logger.info("Initializing DetectionEngine with model {}", model_name)
        self._model_name = model_name
        self._model = self._load_model(model_name)

    def __repr__(self):
        return f"DetectionEngine<model_name={self._model_name}>"

    @property
    def model_name(self) -> str:
        """Return the last model name assigned during initialization or switching.

        Returns:
            Requested model name. After a failed switch, it can differ from
            the name associated with the retained model instance.
        """
        logger.trace("Returning current model name")
        return self._model_name

    def set_model(self, model_name: str) -> None:
        """Switch to a different detection model by `model_name`.

        Args:
            model_name: Registered model name, or `"None"` for the dummy model.

        Raises:
            app.infrastructure.detection.exceptions.DetectionModelError: If the
                name is not registered.

        Provider construction errors also propagate.

        !!! warning "A failed switch is not atomic"

            The name is assigned before loading. If loading fails, the previous
            model instance remains active but `model_name` reports the requested
            name. This method does not roll back the name or coordinate concurrent
            inference.
        """
        logger.trace("Setting detection model to {}", model_name)
        self._model_name = model_name
        self._model = self._load_model(model_name)
        logger.info("Switched detection model to {}", model_name)

    def detect(self, frame: np.ndarray) -> list[DetectionResult]:
        """
        Delegate one frame to the current provider without label selection.

        Args:
            frame: Image array prepared for the selected provider. The model
                interface describes RGB input; this wrapper does not validate
                shape, dtype, channel order, or copy the array.

        Returns:
            The provider's list of
            [`DetectionResult`][app.domain.detection.result.DetectionResult]
            objects, unchanged and without an additional copy. An empty list
            may mean no detections or a failure handled by the provider.

        Errors not handled by the provider propagate to the caller. This wrapper
        does not guarantee that inference leaves the supplied array unchanged.
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
        """Delegate model construction to the registry-backed factory.

        Args:
            model_name: Name passed unchanged to the model loader.

        Returns:
            Provider instance returned by the loader.

        Loader and provider errors propagate to the caller.
        """
        logger.info("Loading detection model {}", model_name)
        return load_detection_model(model_name)
