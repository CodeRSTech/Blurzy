"""Module for table key filter; stores transient interaction state.

Layer: Presentation.
Context: Stores transient interaction state at this architectural boundary.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, override

from PySide6.QtCore import QObject, QEvent
from PySide6.QtGui import QKeyEvent
if TYPE_CHECKING:
    from app.domain.base.dtypes import RenderFunction




if TYPE_CHECKING:
    from app.ui.handlers import AnnotationHandler


class FrameTableKeyFilter(QObject):
    """Represent frame table key filter.

Layer: Presentation.
Context: Supports user interaction and delegates application work through presentation contracts.


    Args:
        annotation_handler: Handler that applies annotation interactions.
        render_fn: Callback used to render the selected frame.
"""
    def __init__(self, annotation_handler: AnnotationHandler, render_fn: RenderFunction) -> None:
        super().__init__()
        self._handler: AnnotationHandler = annotation_handler
        self._render_fn: RenderFunction = render_fn

    @override
    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """Handle annotation shortcuts and consume recognized key-press events.

        Args:
            watched: Object watched by this event filter (unused).
            event: Qt event to inspect.

        Returns:
            `True` if a selection, delete, or nudge shortcut was handled; otherwise `False`.
        """
        if event.type() == QEvent.Type.KeyPress and isinstance(event, QKeyEvent):
            if self._handler.handle_selection_shortcut(event):
                return True
            if self._handler.handle_delete_key(event):
                return True
            return self._handler.handle_nudge_key(event)
        return False
