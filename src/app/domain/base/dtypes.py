"""Type aliases and callback signatures for domain layer.

Layer: Domain.
Context: Defines application concepts independently of UI and infrastructure implementations.
"""

from __future__ import annotations

from typing import TYPE_CHECKING


from typing import TypedDict, Callable
if TYPE_CHECKING:
    from typing import NotRequired


if TYPE_CHECKING:
    # Import only for the type alias below; runtime imports this module before
    # view model in several paths.
    from app.domain.session.session_id import SessionId
    from app.domain.views.bounding_box_view_model import BBoxViewModel

__all__ = ["ListOfBoxesByFrameIndexAsDict", "ProcessingSettingsKwargs", "BBoxXYXYTuple", "RenderFunction",
           "ListOfBoxes", "StopPlaybackFunction", "ProcessingSettingsKwargs"]

# Bounding detection tuple — (x1, y1, x2, y2) in pixel coordinates
type BBoxXYXYTuple = tuple[int, int, int, int]

type ListOfBoxes = list[BBoxViewModel]

# Bounding detection collection — all boxes for a session indexed by frame
type ListOfBoxesByFrameIndexAsDict = dict[int, ListOfBoxes]

# Callback signature — render frame for ``s_id`` (triggered by frame display changes)
type RenderFunction = Callable[[SessionId], None]

# Callback signature — stop playback (no arguments)
type StopPlaybackFunction = Callable[[], None]


class ProcessingSettingsKwargs(TypedDict):
    """Optional keyword fields accepted when updating ProcessingSettings.

    Note:
        Each field is optional so callers can update a subset of session settings.


Layer: Domain.
Context: Represents application concepts without UI or infrastructure dependencies.
"""
    # --- Detection ---
    detection_model_name: NotRequired[str]
    min_detection_confidence: NotRequired[float]
    chosen_labels: NotRequired[list[str]]

    # --- Tracking ---
    tracking_strategy: NotRequired[str]
    tracking_source: NotRequired[str]
    reid_embedding_dim: NotRequired[int]
    min_iou: NotRequired[float]
    min_tracker_confidence: NotRequired[float]
    confidence_decay: NotRequired[float]
    offline_stitching_enabled: NotRequired[bool]
    max_stitch_gap: NotRequired[int]
    gsi_smoothness: NotRequired[float]

    # --- Privacy Features ---
    privacy_features_enabled: NotRequired[bool]
    resist_box_shrinking: NotRequired[bool]
    shrink_resistance: NotRequired[float]
    pre_detection_padding_sec: NotRequired[float]
    post_detection_padding_sec: NotRequired[float]
    box_safety_padding_pct: NotRequired[float]

    # --- Preview ---
    draw_boxes: NotRequired[bool]
    box_border_width: NotRequired[int]
    show_preview_mask: NotRequired[bool]
    preview_blur_enabled: NotRequired[bool]

    # --- Render ---
    blur_enabled: NotRequired[bool]
    blur_strength: NotRequired[float]
