"""Origin classification for bounding boxes (detection/tracking/manual).

Layer: Domain.
Context: Defines application concepts independently of UI and infrastructure implementations.
"""

from __future__ import annotations

from enum import Enum


class BoxSource(str, Enum):
    """
    Source/origin of a bounding detection — used to filter and identify detection type.

    Note:
        `DETECTION` marks YOLO inference output in Layers A and B,
        `TRACKING` marks tracker-generated boxes in Layers C and D, including
        strategy-specific values such as `TRACKING_BOTSORT`, and
        `MANUAL` marks user-created boxes that should be preserved during
        layer resets and filtering operations.

    Example:
        detection.source = BoxSource.DETECTION  # From inference
        detection.source = BoxSource.MANUAL     # User-created (never filtered)


Layer: Domain.
Context: Represents application concepts without UI or infrastructure dependencies.
"""
    DETECTION = "Detection"
    MANUAL = "Manual"
    TRACKING = "Tracking"
    TRACKING_DUMMY = "Track (Dummy)"
    TRACKING_HUNGARIAN = "Track (Hungarian)"
    TRACKING_BYTETRACK = "Track (ByteTrack)"
    TRACKING_DEEPSORT = "Track (DeepSORT)"
    TRACKING_BOTSORT = "Track (BoT-SORT)"