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
        draw_boxes (bool): Whether detection outlines should be rendered.
        blur_enabled (bool): Whether blur rendering is enabled.
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

    # --- Preview / Render ---
    draw_boxes: bool = True
    blur_enabled: bool = False
    blur_strength: float = 0.5
