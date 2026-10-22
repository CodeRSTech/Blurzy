"""Package for qt; implements the Qt presentation components.

See Also:
    - [`Window`][app.ui.qt.window.window.Window] — main Qt application window
    - [`UIController`][app.ui.uicontroller.UIController] — coordinates user-facing operations

Layer: Presentation.
Context: Implements the qt presentation components at this architectural boundary.
"""

from app.ui.qt.window import Window

__all__ = ["Window"]
