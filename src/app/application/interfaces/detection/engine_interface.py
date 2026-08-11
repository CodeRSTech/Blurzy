"""Interface contract for detection engine implementations."""

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

    Any object that exposes ``model_name``, ``set_model()``, and ``detect()``
    with matching signatures satisfies this interface — no explicit inheritance
    required (structural subtyping via ``Protocol``).
    """

    @property
    def model_name(self) -> str:
        """Return the currently loaded model name."""
        ...

    def set_model(self, model_name: str) -> None:
        """Switch to a different model by name."""
        ...

    def detect(self, frame: np.ndarray) -> list[DetectionResult]:
        """Run inference on ``frame`` and return a list of ``DetectionResult`` objects."""
        ...
