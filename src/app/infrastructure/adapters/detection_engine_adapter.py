"""Explicit adapter wrapping `DetectionEngine` to `DetectionEngineInterface`.

See Also:
    - [`DetectionEngineInterface`][app.application.interfaces.detection.engine_interface.DetectionEngineInterface] — defines the exposed engine contract
    - [`DetectionEngine`][app.infrastructure.detection.engine.detection_engine.DetectionEngine] — concrete engine being adapted

Layer: Infrastructure.
Context: Implements concrete processing and I/O behind application-facing contracts.
"""

from __future__ import annotations

from typing import TYPE_CHECKING



from app.application.interfaces import DetectionEngineInterface
if TYPE_CHECKING:
    import numpy as np


if TYPE_CHECKING:
    from app.domain.detection.result import DetectionResult
    from app.infrastructure.detection.engine.detection_engine import DetectionEngine


class DetectionEngineAdapter(DetectionEngineInterface):
    """
    Explicit adapter that wraps a concrete `DetectionEngine` instance and
    exposes the `DetectionEngineInterface` contract.

    In normal usage the concrete `DetectionEngine` already satisfies
    `DetectionEngineInterface` via structural subtyping (`Protocol`), so
    this adapter is not required for runtime correctness.  It exists to:

    - Provide an explicit, named boundary at the infrastructure/application seam.
    - Enable test doubles that replace the real model without subclassing `DetectionEngine`.
    - Act as the canonical reference implementation of the interface.


Layer: Infrastructure.
Context: Implements concrete processing or I/O behind application-facing contracts.


    Args:
        engine: Concrete detection engine delegated to by this adapter.
"""

    def __init__(self, engine: DetectionEngine) -> None:
        self._engine = engine

    def __repr__(self) -> str:
        return f"<DetectionEngineAdapter wrapping={self._engine!r}>"

    @property
    def model_name(self) -> str:
        """Return the configured detection model name.

        Returns:
            Name of the model currently loaded by the wrapped engine.
        """
        return self._engine.model_name

    def set_model(self, model_name: str) -> None:
        """Load and select a different detection model.

        Args:
            model_name: Registered name of the model to load.
        """
        self._engine.set_model(model_name)

    def detect(self, frame: np.ndarray) -> list[DetectionResult]:
        """Run detection on the supplied frame.

        Args:
            frame: RGB image array to pass to the wrapped engine.

        Returns:
            Detection results produced by the wrapped engine.
        """
        return self._engine.detect(frame)
