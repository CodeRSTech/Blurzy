"""Interface contract for detection engine implementations.

See Also:
    - [`DetectionEngine`][app.infrastructure.detection.engine.detection_engine.DetectionEngine] — concrete inference engine
    - [`DetectionEngineAdapter`][app.infrastructure.adapters.detection_engine_adapter.DetectionEngineAdapter] — exposes the engine through this contract

Layer: Application.
Context: Defines protocol boundaries consumed by application orchestration.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable
if TYPE_CHECKING:
    import numpy as np




if TYPE_CHECKING:
    from app.domain.detection.result import DetectionResult


@runtime_checkable
class DetectionEngineInterface(Protocol):
    """
    Abstraction boundary for YOLO / ML detection engine implementations.

    Any object that exposes `model_name`, `set_model()`, and `detect()`
    with matching signatures satisfies this interface — no explicit inheritance
    required (structural subtyping via `Protocol`).


Layer: Application.
Context: Coordinates use-case behavior through domain services and application contracts.
"""

    @property
    def model_name(self) -> str:
        """Return the currently loaded model name.

        Returns:
            Name of the model currently selected by the engine.
        """
        ...

    def set_model(self, model_name: str) -> None:
        """Switch to a different model by name.

        Args:
            model_name: Registered model identifier accepted by the detection-model factory.
        """
        ...

    def detect(self, frame: np.ndarray) -> list[DetectionResult]:
        """Run inference on `frame` and return a list of `DetectionResult` objects.

        Args:
            frame: RGB image array to pass to the detection model.

        Returns:
            Detection results produced for the frame.
        """
        ...
