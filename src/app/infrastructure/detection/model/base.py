from abc import abstractmethod, ABC

import numpy as np

from app.domain.detection.result import DetectionResult


class BaseDetectionModel(ABC):
    """Abstract base class for all detection model implementations (Torch, YOLO, Dummy)."""
    @abstractmethod
    def detect(
        self,
        frame: np.ndarray,
        chosen_labels: list[str] | None = None,
    ) -> list[DetectionResult]:
        """Run inference on ``frame``, optionally filtering to ``chosen_labels``."""
        raise NotImplementedError