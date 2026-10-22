"""Package for window; implements the Qt presentation components.

See Also:
    - [`Window`][app.ui.qt.window.window.Window] — main application window
    - [`UIController`][app.ui.uicontroller.UIController] — supplies coordinated UI behavior

Layer: Presentation.
Context: Implements the qt presentation components at this architectural boundary.
"""

from .window import Window

__all__ = ['Window']