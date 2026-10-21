"""UI layer for EazyBlur — PySide6 Qt-based graphical interface.

Layer: Presentation.
Context: Presents application behavior through user-facing components.
"""

from app.ui import handlers
from app.ui.uicontroller import UIController

__all__ = ["UIController", "handlers"]
