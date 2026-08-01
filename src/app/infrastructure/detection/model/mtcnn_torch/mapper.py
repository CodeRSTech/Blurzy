"""Mapper for converting MTCNN (facenet-pytorch) output to DetectionResult."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.domain.detection.result import DetectionResult
from app.infrastructure.detection.model.names import DEFAULT_MTCNN_TORCH_CONFIDENCE_THRESHOLD
from app.shared import get_logger

if TYPE_CHECKING:
    import numpy as np

logger = get_logger("Infrastructure->Detection->Models->MTCNN Torch ModelMapper")


class MTCNNTorchDetectionMapper:
    """Maps raw MTCNN (facenet-pytorch) detection output to DetectionResult format.

    ``facenet_pytorch.MTCNN.detect()`` returns a pair ``(boxes, probs)`` where:

    * ``boxes`` – ``numpy.ndarray`` of shape ``(N, 4)`` in **xyxy** order, or
      ``None`` when no face is found.
    * ``probs`` – ``numpy.ndarray`` of shape ``(N,)`` with confidence scores in
      ``[0, 1]``, or ``None`` when no face is found.
    """

    @staticmethod
    def map(
        boxes: "np.ndarray | None",
        probs: "np.ndarray | None",
        chosen_labels: list[str] | None = None,
    ) -> list[DetectionResult]:
        """
        Map MTCNN raw inference output to a list of DetectionResult.

        Args:
            boxes: Array of bounding boxes in xyxy format, shape ``(N, 4)``, or
                ``None`` if no faces were detected.
            probs: Array of confidence scores, shape ``(N,)``, or ``None``.
            chosen_labels: Optional filter; results whose label is not in this
                list are dropped.  MTCNN always emits ``"person"`` labels.

        Returns:
            List of :class:`DetectionResult` instances filtered by confidence
            threshold and optional label filter.
        """
        if boxes is None or probs is None:
            return []

        detections: list[DetectionResult] = []

        for index, (box, prob) in enumerate(zip(boxes, probs)):
            try:
                score = float(prob)
                if score < DEFAULT_MTCNN_TORCH_CONFIDENCE_THRESHOLD:
                    continue

                label = "person"
                if chosen_labels and label not in chosen_labels:
                    continue

                detections.append(
                    DetectionResult(
                        item_id=f"mtcnn-torch-{index}",
                        bbox_xyxy=(
                            int(box[0]),
                            int(box[1]),
                            int(box[2]),
                            int(box[3]),
                        ),
                        confidence=score,
                        label=label,
                        color_hex="#80F080",
                    )
                )
            except Exception:
                logger.opt(exception=True).warning("Failed to map MTCNN detection result at index {}", index)
                continue

        logger.trace(
            "MTCNN Torch detection filtered to {} item(s) using confidence threshold {}",
            len(detections),
            DEFAULT_MTCNN_TORCH_CONFIDENCE_THRESHOLD,
        )
        return detections
