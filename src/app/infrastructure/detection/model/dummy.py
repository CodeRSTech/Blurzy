import numpy as np

from app.domain.detection.result import DetectionResult
from app.infrastructure.detection.model.base import BaseDetectionModel


class DummyDetectionModel(BaseDetectionModel):
    """No-op detection model — always returns empty list (used when model is "None")."""
    def detect(
        self,
        frame: np.ndarray,
        chosen_labels: list[str] | None = None,
    ) -> list[DetectionResult]:
        """Return empty list (no detections)."""
        return []