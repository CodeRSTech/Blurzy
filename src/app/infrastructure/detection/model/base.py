"""Module for base; implements concrete processing and I/O behind application-facing contracts.

See Also:
    - [`DetectionEngine`][app.infrastructure.detection.engine.detection_engine.DetectionEngine] — invokes the model interface
    - [`YoloDetectionModel`][app.infrastructure.detection.model.yolo.model.YoloDetectionModel] — one implementation of the model contract

Layer: Infrastructure.
Context: Implements concrete processing and i/o behind application-facing contracts at this architectural boundary.
"""

from __future__ import annotations

from typing import TYPE_CHECKING


from abc import abstractmethod, ABC
if TYPE_CHECKING:
    import numpy as np
    from app.domain.detection.result import DetectionResult







class BaseDetectionModel(ABC):
    """Abstract base class for all detection model implementations (Torch, YOLO, Dummy).

Layer: Infrastructure.
Context: Implements concrete processing or I/O behind application-facing contracts.
"""
    @abstractmethod
    def detect(
        self,
        frame: np.ndarray,
        chosen_labels: list[str] | None = None,
    ) -> list[DetectionResult]:
        """Run inference on `frame`, optionally filtering to `chosen_labels`.

        Args:
            frame: RGB image array to process.
            chosen_labels: Optional labels to retain in the returned detections.

        Returns:
            Detection results for the frame, restricted to `chosen_labels` when provided.
        """
        raise NotImplementedError