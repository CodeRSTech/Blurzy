from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class SessionSettingsViewModel:
    """
    UI-ready snapshot of settings (pre-formatted for widget binding).

    Attributes:
        detection_model_name (str): Selected detection model name.
        min_detection_confidence (float): Detection confidence threshold.
        chosen_labels (str): Comma-separated labels string for direct widget binding.
        tracking_strategy (str): Selected tracking strategy name.
        tracking_source (str): Layer used as tracker input.
        min_iou (float): IoU threshold for track matching.
        min_tracker_confidence (float): Confidence floor for tracked boxes.
        confidence_decay (float): Per-frame confidence decay value.
        offline_stitching_enabled (bool): Whether broken tracks are bridged offline.
        max_stitch_gap (int): Maximum number of missed frames to bridge.
        gsi_smoothness (float): Gaussian interpolation lengthscale.
        draw_boxes (bool): Whether detection outlines should be rendered.
        box_border_width (int): Preview box outline width in pixels.
        show_preview_mask (bool): Whether the export mask is overlaid in preview.
        preview_blur_enabled (bool): Whether blur is rendered live in preview.
        blur_enabled (bool): Whether blur is enabled for export.
        blur_strength (float): Blur intensity used for rendering.

    Note:
        Unlike ``ProcessingSettings``, ``chosen_labels`` is pre-joined into a
        comma-separated string such as ``"person, cat, dog"`` so it can be
        assigned directly to UI widgets without parsing. Created when a session
        is opened or switched, treated as read-only by domain code, and rebuilt
        from ``ProcessingSettings`` whenever the UI needs a fresh snapshot.
    """

    # --- Detection ---
    detection_model_name: str = "None"
    min_detection_confidence: float = 0.5
    # NOTE: This is the point where chosen_labels differs from ProcessingSettings.chosen_labels
    chosen_labels: str = "person, cat, dog"  # comma-separated, e.g. "person, cat, dog"

    # --- Tracking ---
    tracking_strategy: str = "hungarian"
    tracking_source: str = "layer_b"
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
