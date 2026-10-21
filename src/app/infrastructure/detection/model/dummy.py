"""Module for dummy; implements concrete processing and I/O behind application-facing contracts.

Layer: Infrastructure.
Context: Implements concrete processing and i/o behind application-facing contracts at this architectural boundary.
"""




from __future__ import annotations

from typing import TYPE_CHECKING


from app.infrastructure.detection.model.base import BaseDetectionModel
if TYPE_CHECKING:
    import numpy as np
    from app.domain.detection.result import DetectionResult



class DummyDetectionModel(BaseDetectionModel):
    """No-op detection model — always returns empty list (used when model is "None").

Layer: Infrastructure.
Context: Implements concrete processing or I/O behind application-facing contracts.
"""
    def detect(
        self,
        frame: np.ndarray,
        chosen_labels: list[str] | None = None,
    ) -> list[DetectionResult]:
        """Return empty list (no detections).

        Args:
            frame: RGB image array; unused by this no-op model.
            chosen_labels: Optional label filter; unused because no detections are produced.

        Returns:
            Empty list.
        """
        return []