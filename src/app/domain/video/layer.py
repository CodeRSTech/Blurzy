"""Annotation layer enumeration for managing bounding detection data.

Layer: Domain.
Context: Defines application concepts independently of UI and infrastructure implementations.
"""

from __future__ import annotations

from enum import Enum


class VideoDataLayer(str, Enum):
    """
    Four-layer detection system for bounding detection management.

    Note:
        Layer A stores immutable raw detections from YOLO, Layer B stores
        editable reviewed detections seeded from A, Layer C stores immutable
        tracker output, and Layer D stores editable final tracks seeded from C.
        This separation preserves machine output for reproducibility while still
        allowing user corrections. Typical workflow is A → B for detection
        review, then B → C → D for tracking, with export using Layer B or D.

    Example:
        boxes = session.get_layer_by_name(VideoDataLayer.B)
        original = session.get_layer_by_name(VideoDataLayer.A)


Layer: Domain.
Context: Represents application concepts without UI or infrastructure dependencies.
"""
    A = "a"
    B = "b"
    C = "c"
    D = "d"

    def __str__(self) -> str:
        return self.value
