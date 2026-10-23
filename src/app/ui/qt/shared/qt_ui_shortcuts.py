"""
Module for qt ui shortcuts; implements the Qt presentation components.

See Also:
    - [`apply_qt_ui_shortcuts`][app.ui.qt.shared.qt_class_patches.apply_qt_ui_shortcuts] — implementation re-exported by this compatibility module

Layer: Presentation.
Context: Implements the qt presentation components at this architectural boundary.
"""

from app.ui.qt.shared.qt_class_patches import apply_qt_ui_shortcuts

__all__ = ["apply_qt_ui_shortcuts"]
