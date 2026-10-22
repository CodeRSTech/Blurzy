"""Module for preview state; stores transient interaction state.

See Also:
    - [`PreviewContainer`][app.ui.qt.widgets.preview.preview_container.PreviewContainer] — presents the preview state
    - [`AnnotationOverlayWidget`][app.ui.qt.widgets.preview.layer_bbox.layer_bbox.AnnotationOverlayWidget] — consumes preview tool mode

Layer: Presentation.
Context: Stores transient interaction state at this architectural boundary.
"""

# app/ui/view_state/preview_state.py
from enum import Enum, auto


class ToolMode(Enum):
    """
    Defines the current interactive mode of the preview canvas.

    ADD: Clicking starts a new bounding detection. Ignores existing boxes.
    EDIT: Clicking selects, moves, or resizes an existing detection.
    DELETE: Clicking an existing detection deletes it instantly.


Layer: Presentation.
Context: Supports user interaction and delegates application work through presentation contracts.
"""
    ADD = auto()
    EDIT = auto()
    DELETE = auto()