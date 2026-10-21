"""Package for widgets; implements the Qt presentation components.

Layer: Presentation.
Context: Implements the qt presentation components at this architectural boundary.
"""

from app.ui.qt.widgets.preview.layer_video import VideoDisplayWidget
from app.ui.qt.widgets.preview.layer_bbox import AnnotationOverlayWidget

__all__ = ["AnnotationOverlayWidget", "VideoDisplayWidget"]