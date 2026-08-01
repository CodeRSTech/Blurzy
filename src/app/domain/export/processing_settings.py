"""User-configurable settings for detection, tracking, and rendering pipelines."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.domain.views.session_settings_view_model import SessionSettingsViewModel


@dataclass(slots=True)
class ProcessingSettings:
    """
    Mutable configuration snapshot for a video processing session.

    Attributes:
        detection_model_name (str): YOLO model name, or ``"None"`` when disabled.
        min_detection_confidence (float): Confidence threshold used to filter detections.
        chosen_labels (list[str]): Whitelist of class names to detect.
        tracking_strategy (str): Tracking algorithm name.
        tracking_source (str): Input layer used for tracking.
        min_iou (float): IoU threshold for matching detections to tracks.
        min_tracker_confidence (float): Confidence floor before pruning a track.
        confidence_decay (float): Per-frame confidence decay for coasted tracks.
        draw_boxes (bool): Whether detection outlines should be drawn on video frames.
        blur_enabled (bool): Whether Gaussian blur should be applied.
        blur_strength (float): Blur sigma in pixels.

    Note:
        Created per session with defaults, updated when the user changes UI
        controls, and converted to ``SessionSettingsViewModel`` through
        ``as_view_model()`` for widget binding.

    Example:
        settings = ProcessingSettings(
            detection_model_name="yolov8n",
            min_detection_confidence=0.50,
            chosen_labels=["person", "car"],
            tracking_strategy="hungarian",
            blur_enabled=True
        )
        view_model = settings.as_view_model()  # For UI binding
    """

    # --- Detection ---
    detection_model_name: str = "None"
    min_detection_confidence: float = 0.25
    chosen_labels: list[str] = field(default_factory=lambda: ["person", "cat", "dog"])

    # --- Tracking ---
    tracking_strategy: str = "hungarian"
    tracking_source: str = "b"
    min_iou: float = 0.3
    min_tracker_confidence: float = 0.1
    confidence_decay: float = 0.05

    # --- Preview / Render ---
    draw_boxes: bool = True
    blur_enabled: bool = False
    blur_strength: float = 15.0

    def as_view_model(self) -> SessionSettingsViewModel:
        """Convert to ``SessionSettingsViewModel`` (UI-ready: labels joined as comma-separated string)."""
        s = self
        return SessionSettingsViewModel(
            detection_model_name=s.detection_model_name,
            min_detection_confidence=s.min_detection_confidence,
            chosen_labels=", ".join(s.chosen_labels),
            tracking_strategy=s.tracking_strategy,
            tracking_source=s.tracking_source,
            min_iou=s.min_iou,
            min_tracker_confidence=s.min_tracker_confidence,
            confidence_decay=s.confidence_decay,
            draw_boxes=s.draw_boxes,
            blur_enabled=s.blur_enabled,
            blur_strength=s.blur_strength,
        )

    @property
    def model_name_is_null(self) -> bool:
        """Return True if no detection model selected (""None"" or empty string)."""
        return self.detection_model_name == "None" or self.detection_model_name == ""