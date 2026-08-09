"""BBox overlay package.

This package contains the concern-based split of the preview bbox overlay:
- ``layer_bbox.py``: Qt widget facade and signal emission.
- ``menu.py``: context menu action wiring.
- ``interaction.py``: drag/pan view_state transitions.
- ``geometry.py``: widget/image coordinate mapping and bbox lookup.
- ``rendering.py``: bbox drawing primitives.
- ``helpers.py`` / ``constants.py``: low-level utility math and constants.

Public API:
- ``AnnotationOverlayWidget``
"""

from .layer_bbox import AnnotationOverlayWidget

__all__ = ["AnnotationOverlayWidget"]