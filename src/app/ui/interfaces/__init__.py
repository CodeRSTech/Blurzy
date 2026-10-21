"""UI-layer protocols for handler dependencies.

Layer: Presentation.
Context: Defines presentation-facing contracts for controllers, application access, and windows.
"""

from app.ui.interfaces.application_interface import UIApplicationInterface
from app.ui.interfaces.controller_interface import UIControllerInterface

__all__ = [
    "UIApplicationInterface",
    "UIControllerInterface",
]

