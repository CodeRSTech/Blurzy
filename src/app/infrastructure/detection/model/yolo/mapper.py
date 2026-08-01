"""Mapper for converting Ultralytics YOLO model output to DetectionPayload."""

from __future__ import annotations

from app.domain.detection.result import DetectionResult
from app.infrastructure.detection.model.names import DEFAULT_YOLO_CONFIDENCE_THRESHOLD
from app.shared import get_logger

logger = get_logger("Infrastructure->Detection->Models->YoloModelMapper")


class YoloDetectionMapper:
    """Maps raw YOLO detection results to DetectionPayload format."""

    @staticmethod
    def map(
            results: list,
            chosen_labels: list[str] | None = None,
    ) -> list[DetectionResult]:
        """
        Map YOLO raw inference output to DetectionResult list.

        Args:
            results: Raw YOLO model output (list of Result objects).
            chosen_labels: Optional filter to include only these labels.

        Returns:
            List of DetectionResult instances filtered by confidence and label.
        """
        detections: list[DetectionResult] = []

        for result in results:
            names = result.names
            for index, box in enumerate(result.boxes):
                try:
                    score = float(box.conf[0])
                    if score < DEFAULT_YOLO_CONFIDENCE_THRESHOLD:
                        continue

                    xyxy = box.xyxy[0].tolist()
                    class_index = int(box.cls[0])
                    label = str(names[class_index])

                    if chosen_labels and label not in chosen_labels:
                        continue

                    detections.append(
                        DetectionResult(
                            item_id=f"yolo-{index}",
                            bbox_xyxy=(
                                int(xyxy[0]),
                                int(xyxy[1]),
                                int(xyxy[2]),
                                int(xyxy[3]),
                            ),
                            confidence=score,
                            label=label,
                            color_hex="#8080F0",  # Default color; can be customized if needed
                        )
                    )
                except Exception:
                    logger.opt(exception=True).warning("Failed to map YOLO detection result")
                    continue

        logger.trace(
            "YOLO detection filtered to {} item(s) using confidence threshold {}",
            len(detections),
            DEFAULT_YOLO_CONFIDENCE_THRESHOLD,
        )
        return detections
