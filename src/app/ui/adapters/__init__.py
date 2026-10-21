"""UI-layer adapters for handler dependency protocols.

Layer: Presentation.
Context: Bridges UI-facing contracts to application operations.
"""

from app.ui.adapters.application_adapter import UIApplicationAdapter
from app.ui.adapters.controller_adapter import UIControllerAdapter

__all__ = [
    "UIApplicationAdapter",
    "UIControllerAdapter",
]

