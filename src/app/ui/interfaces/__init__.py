"""UI-layer protocols for handler dependencies.

See Also:
    - [`UIControllerInterface`][app.ui.interfaces.controller_interface.UIControllerInterface] — describes controller operations used by handlers
    - [`UIApplicationInterface`][app.ui.interfaces.ui_application_interface.UIApplicationInterface] — describes application operations used by handlers

Layer: Presentation.
Context: Defines presentation-facing contracts for controllers, application access, and windows.
"""

from app.ui.interfaces.application_interface import UIApplicationInterface
from app.ui.interfaces.controller_interface import UIControllerInterface

__all__ = [
    "UIApplicationInterface",
    "UIControllerInterface",
]

