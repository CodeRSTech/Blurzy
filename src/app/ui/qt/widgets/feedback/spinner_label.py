"""
Module for spinner label; implements the Qt presentation components.

See Also:
    - [`ModelLoadWorker`][app.ui.qt.workers.model_loader.ModelLoadWorker] — reports asynchronous model-loading progress
    - [`ModelHandler`][app.ui.handlers.model_handler.ModelHandler] — coordinates worker feedback with the UI

Layer: Presentation.
Context: Implements the qt presentation components at this architectural boundary.
"""

from __future__ import annotations

from typing import TYPE_CHECKING


from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QLabel
if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget


class InlineSpinnerLabel(QLabel):
    """
    Small animated inline spinner label for lightweight loading states.

    Layer: Presentation.
    Context: Supports user interaction and delegates application work through presentation contracts.


    Args:
        text: Initial text displayed by the widget.
        parent: Optional Qt parent object.
        interval_ms: Animation interval in milliseconds.
    """

    _FRAMES = ("⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏")

    def __init__(
        self,
        text: str = "Loading",
        parent: QWidget | None = None,
        interval_ms: int = 100,
    ) -> None:
        super().__init__(parent)
        self._text = text
        self._frame_index = 0
        self._timer = QTimer(self)
        self._timer.setInterval(interval_ms)
        self._timer.timeout.connect(self._advance)
        self.setVisible(False)

    def start(self, text: str | None = None) -> None:
        """
        Show the label and start its frame timer.

        Args:
            text: Optional replacement status text; when omitted, keep the current text.
        """
        if text is not None:
            self._text = text
        self._frame_index = 0
        self._advance()
        self.setVisible(True)
        if not self._timer.isActive():
            self._timer.start()

    def stop(self) -> None:
        """
        Stop the frame timer and hide the label.
"""
        if self._timer.isActive():
            self._timer.stop()
        self.setVisible(False)

    def _advance(self) -> None:
        frame = self._FRAMES[self._frame_index]
        self.setText(f"{frame} {self._text}")
        self._frame_index = (self._frame_index + 1) % len(self._FRAMES)
