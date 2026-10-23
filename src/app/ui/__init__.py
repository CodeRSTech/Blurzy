"""
UI layer for EazyBlur — PySide6 Qt-based graphical interface.

See Also:
    - [`UIController`][app.ui.uicontroller.UIController] — coordinates UI handlers
    - [`Window`][app.ui.qt.window.window.Window] — provides the main application window

Layer: Presentation.
Context: Presents application behavior through user-facing components.
"""

from app.ui import handlers
from app.ui.uicontroller import UIController

__all__ = ["UIController", "handlers"]
