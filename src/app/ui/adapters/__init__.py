"""UI-layer adapters for handler dependency protocols.

See Also:
    - [`UIControllerInterface`][app.ui.interfaces.controller_interface.UIControllerInterface] — contract adapted by the controller facade
    - [`UIApplicationInterface`][app.ui.interfaces.ui_application_interface.UIApplicationInterface] — contract adapted for application calls

Layer: Presentation.
Context: Bridges UI-facing contracts to application operations.
"""

from app.ui.adapters.application_adapter import UIApplicationAdapter
from app.ui.adapters.controller_adapter import UIControllerAdapter

__all__ = [
    "UIApplicationAdapter",
    "UIControllerAdapter",
]

