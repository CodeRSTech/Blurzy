"""Mapper for converting TorchVision model output to DetectionPayload."""

from __future__ import annotations

from app.domain.detection.result import DetectionResult
from app.infrastructure.detection.model.names import DEFAULT_TORCH_CONFIDENCE_THRESHOLD
from app.shared import get_logger

logger = get_logger("Infrastructure->Detection->Models->TorchModelMapper")


class TorchDetectionMapper:
    """Maps raw TorchVision detection results to DetectionPayload format."""

    @staticmethod
    def map(
        raw_results: dict,
        labels: list[str],
        chosen_labels: list[str] | None = None,
    ) -> list[DetectionResult]:
        """
        Map TorchVision raw inference output to DetectionResult list.

        Args:
            raw_results: Raw model output (dict with "boxes", "scores", "labels" keys).
            labels: Label names extracted from model weights metadata.
            chosen_labels: Optional filter to include only these labels.

        Returns:
            List of DetectionResult instances filtered by confidence and label.
        """
        detections: list[DetectionResult] = []
        num_boxes = len(raw_results["boxes"])

        for index in range(num_boxes):
            try:
                score = float(raw_results["scores"][index])
                if score < DEFAULT_TORCH_CONFIDENCE_THRESHOLD:
                    continue

                bbox_tensor = raw_results["boxes"][index]
                label_index = int(raw_results["labels"][index])
                label = labels[label_index]

                if chosen_labels and label not in chosen_labels:
                    continue

                bbox_values = bbox_tensor.tolist()
                detections.append(
                    DetectionResult(
                        item_id=f"torch-{index}",
                        bbox_xyxy=(
                            int(bbox_values[0]),
                            int(bbox_values[1]),
                            int(bbox_values[2]),
                            int(bbox_values[3]),
                        ),
                        confidence=score,
                        label=label,
                        color_hex="#808080",  # Default color; can be customized if needed
                    )
                )
            except Exception:
                logger.opt(exception=True).warning("Failed to map Torch detection result")
                continue

        logger.trace(
            "Torch detection filtered to {} item(s) using confidence threshold {}",
            len(detections),
            DEFAULT_TORCH_CONFIDENCE_THRESHOLD,
        )
        return detections
