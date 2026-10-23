"""
Compatibility shim for the renamed UI application protocol.

See Also:
    - [`UIApplicationInterface`][app.ui.interfaces.ui_application_interface.UIApplicationInterface]

Layer: Presentation.
Context: Defines presentation-facing contracts for controllers, application access, and windows.
"""

from app.ui.interfaces.ui_application_interface import UIApplicationInterface

__all__ = ["UIApplicationInterface"]
