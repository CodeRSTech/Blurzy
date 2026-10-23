"""
Package for widgets; implements the Qt presentation components.

See Also:
    - [`PreviewContainer`][app.ui.qt.widgets.preview.preview_container.PreviewContainer] — combines video and annotation widgets
    - [`AnnotationOverlayWidget`][app.ui.qt.widgets.preview.layer_bbox.layer_bbox.AnnotationOverlayWidget] — edits boxes over video

Layer: Presentation.
Context: Implements the qt presentation components at this architectural boundary.
"""

from app.ui.qt.widgets.preview.layer_video import VideoDisplayWidget
from app.ui.qt.widgets.preview.layer_bbox import AnnotationOverlayWidget

__all__ = ["AnnotationOverlayWidget", "VideoDisplayWidget"]