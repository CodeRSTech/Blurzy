"""Factory for loading Ultralytics YOLO detection model."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.infrastructure.detection.exceptions import DetectionModelError
from app.shared import get_logger

if TYPE_CHECKING:
    from ultralytics.models.yolo.model import YOLO

logger = get_logger("Infrastructure->Detection->Models->YoloModelLoaderFactory")


class YoloModelLoaderFactory:
    """Factory for loading Ultralytics YOLO detection model."""

    @staticmethod
    def create(model_file_name: str) -> YOLO:
        """
        Load YOLO model by ``model_file_name`` (e.g., "yolov8n.pt").

        Returns:
            Loaded YOLO model instance.

        Raises:
            DetectionModelError: If Ultralytics is not installed or model loading fails.
        """
        try:
            logger.debug("Loading Ultralytics model {}", model_file_name)
            from ultralytics import YOLO
        except ModuleNotFoundError as exc:
            raise DetectionModelError(
                "Ultralytics is not installed, so YOLO model are unavailable."
            ) from exc

        try:
            return YOLO(model_file_name)
        except Exception as exc:
            logger.opt(exception=exc).error(
                "Failed to load Ultralytics model {}",
                model_file_name,
            )
            raise DetectionModelError(f"Failed to load YOLO model: {model_file_name}\n{exc}") from exc
