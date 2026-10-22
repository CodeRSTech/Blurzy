"""Compatibility shim for the renamed UI application adapter.

See Also:
    - [`UIApplicationAdapter`][app.ui.adapters.ui_application_adapter.UIApplicationAdapter] — current adapter implementation
    - [`UIApplicationInterface`][app.ui.interfaces.ui_application_interface.UIApplicationInterface] — application facade contract

Layer: Presentation.
Context: Bridges UI-facing contracts to application operations.
"""

from app.ui.adapters.ui_application_adapter import UIApplicationAdapter

__all__ = ["UIApplicationAdapter"]
