from __future__ import annotations

from typing import TYPE_CHECKING


from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QLabel
if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget



class InlineSpinnerLabel(QLabel):
    """Small animated inline spinner label for lightweight loading states."""

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
        if text is not None:
            self._text = text
        self._frame_index = 0
        self._advance()
        self.setVisible(True)
        if not self._timer.isActive():
            self._timer.start()

    def stop(self) -> None:
        if self._timer.isActive():
            self._timer.stop()
        self.setVisible(False)

    def _advance(self) -> None:
        frame = self._FRAMES[self._frame_index]
        self.setText(f"{frame} {self._text}")
        self._frame_index = (self._frame_index + 1) % len(self._FRAMES)
