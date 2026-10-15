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
        offline_stitching_enabled (bool): Whether post-processing bridges fragmented tracks.
        max_stitch_gap (int): Maximum number of missed frames to bridge.
        gsi_smoothness (float): Gaussian interpolation lengthscale.
        draw_boxes (bool): Whether box outlines are shown in the editor preview.
        box_border_width (int): Preview outline width in pixels.
        show_preview_mask (bool): Whether to show the export blur mask in preview.
        preview_blur_enabled (bool): Whether to render blur in the editor preview.
        blur_enabled (bool): Whether Gaussian blur is applied during export.
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
    offline_stitching_enabled: bool = True
    max_stitch_gap: int = 25
    gsi_smoothness: float = 10.0

    # --- Preview ---
    draw_boxes: bool = True
    box_border_width: int = 2
    show_preview_mask: bool = False
    preview_blur_enabled: bool = False

    # --- Render ---
    blur_enabled: bool = False
    blur_strength: float = 15.0

    def __post_init__(self) -> None:
        """Validate user-configurable limits before a session uses the settings.

        Args:
            None.

        Returns:
            None.

        Raises:
            ValueError: If a bounded setting is outside its documented range.

        Note:
            UI widgets use the same ranges; this protects settings restored from
            preferences or constructed by non-UI callers.

        Example:
            settings = ProcessingSettings(max_stitch_gap=25)
        """
        if not 1 <= self.max_stitch_gap <= 60:
            raise ValueError("max_stitch_gap must be between 1 and 60.")
        if not 1.0 <= self.gsi_smoothness <= 30.0:
            raise ValueError("gsi_smoothness must be between 1.0 and 30.0.")
        if not 1 <= self.box_border_width <= 10:
            raise ValueError("box_border_width must be between 1 and 10.")

    def as_view_model(self) -> SessionSettingsViewModel:
        """Create the widget-ready view of this session's processing settings.

        Args:
            None.

        Returns:
            A view model with labels joined for direct text-field assignment.

        Raises:
            None.

        Note:
            This conversion is a snapshot; later UI edits update the settings
            through the application service rather than mutating the snapshot.

        Example:
            view_model = settings.as_view_model()
        """
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
            offline_stitching_enabled=s.offline_stitching_enabled,
            max_stitch_gap=s.max_stitch_gap,
            gsi_smoothness=s.gsi_smoothness,
            draw_boxes=s.draw_boxes,
            box_border_width=s.box_border_width,
            show_preview_mask=s.show_preview_mask,
            preview_blur_enabled=s.preview_blur_enabled,
            blur_enabled=s.blur_enabled,
            blur_strength=s.blur_strength,
        )

    @property
    def model_name_is_null(self) -> bool:
        """Return True if no detection model selected (""None"" or empty string)."""
        return self.detection_model_name == "None" or self.detection_model_name == ""