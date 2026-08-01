"""
Mapper for converting MTCNN model output to DetectionPayload.

**[NOTE]**
**[IMPORTANT]**
!!! **NOT supported** as of current development status !!!
"""

from __future__ import annotations

from app.domain.detection.result import DetectionResult
from app.infrastructure.detection.model.names import DEFAULT_MTCNN_TF_CONFIDENCE_THRESHOLD
from app.shared import get_logger

logger = get_logger("Infrastructure->Detection->Models->MTCNN TF ModelMapper")


class MTCNNTFDetectionMapper:
    """Maps raw MTCNN detection results to DetectionPayload format."""

    @staticmethod
    def map(
            results: list,
            chosen_labels: list[str] | None = None,
    ) -> list[DetectionResult]:
        """
        Map MTCNN raw inference output to DetectionResult list.

        Args:
            results: Raw MTCNN model output (list of Result objects).
            chosen_labels: Optional filter to include only these labels.

        Returns:
            List of DetectionResult instances filtered by confidence and label.
        """
        detections: list[DetectionResult] = []

        for index, result in enumerate(results):
            try:
                score = float(result["confidence"])
                if score < DEFAULT_MTCNN_TF_CONFIDENCE_THRESHOLD:
                    continue

                label = "person"
                if chosen_labels and label not in chosen_labels:
                    continue

                xyxy = result["box"]
                detections.append(
                    DetectionResult(
                        item_id=f"mtcnn-tf-{index}",
                        bbox_xyxy=(
                            int(xyxy[0]),
                            int(xyxy[1]),
                            int(xyxy[2]),
                            int(xyxy[3]),
                        ),
                        confidence=score,
                        label=label,
                        color_hex="#80F080",  # Default color; can be customized if needed
                    )
                )
            except Exception:
                logger.opt(exception=True).warning("Failed to map MTCNN detection result")
                continue

        logger.trace(
            "MTCNN detection filtered to {} item(s) using confidence threshold {}",
            len(detections),
            DEFAULT_MTCNN_TF_CONFIDENCE_THRESHOLD,
        )
        return detections
