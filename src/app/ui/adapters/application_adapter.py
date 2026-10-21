"""Compatibility shim for the renamed UI application adapter.

Layer: Presentation.
Context: Bridges UI-facing contracts to application operations.
"""

from app.ui.adapters.ui_application_adapter import UIApplicationAdapter

__all__ = ["UIApplicationAdapter"]
