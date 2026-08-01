from __future__ import annotations

from typing import TYPE_CHECKING, override

from PySide6.QtCore import QObject, QEvent
from PySide6.QtGui import QKeyEvent

from app.domain.base.dtypes import RenderFunction

if TYPE_CHECKING:
    from app.ui.handlers import AnnotationHandler


class FrameTableKeyFilter(QObject):
    def __init__(self, annotation_handler: AnnotationHandler, render_fn: RenderFunction) -> None:
        super().__init__()
        self._handler: AnnotationHandler = annotation_handler
        self._render_fn: RenderFunction = render_fn

    @override
    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Type.KeyPress and isinstance(event, QKeyEvent):
            return self._handler.handle_nudge_key(event)
        return False
