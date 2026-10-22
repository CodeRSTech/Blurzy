"""BBox overlay package.

This package contains the concern-based split of the preview bbox overlay:
- `layer_bbox.py`: Qt widget facade and signal emission.
- `menu.py`: context menu action wiring.
- `interaction.py`: drag/pan view_state transitions.
- `geometry.py`: widget/image coordinate mapping and bbox lookup.
- `rendering.py`: bbox drawing primitives.
- `helpers.py` / `constants.py`: low-level utility math and constants.

Public API:
- `AnnotationOverlayWidget`

See Also:
    - [`FrameBoxesViewModel`][app.domain.views.frame_boxes_view_model.FrameBoxesViewModel] — represents boxes rendered by the overlay
    - [`AnnotationHandler`][app.ui.handlers.annotation_handler.AnnotationHandler] — handles actions emitted by the widget


Layer: Presentation.
Context: Contains concrete Qt presentation components and supporting utilities.
"""

from .layer_bbox import AnnotationOverlayWidget

__all__ = ["AnnotationOverlayWidget"]