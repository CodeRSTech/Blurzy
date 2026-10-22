"""Package for shared; implements the Qt presentation components.

See Also:
    - [`create_hbox_layout`][app.ui.qt.shared.layout_shortcuts.create_hbox_layout] — supplies common layout construction
    - [`get_handle_points_from_rect`][app.ui.qt.shared.geometry_ui.get_handle_points_from_rect] — calculates annotation resize handles

Layer: Presentation.
Context: Implements the qt presentation components at this architectural boundary.
"""

from .geometry_ui import get_handle_points_from_rect
from .icons import create_tinted_icon
from .layout_shortcuts import create_hbox_layout, create_vbox_layout
from .qt_class_patches import apply_qt_ui_shortcuts
from .widget_factories import (
    create_progress_bar,
    create_qhbox_with_widgets,
    create_spinbox,
    post_data_table_init,
)

__all__ = [
    "apply_qt_ui_shortcuts",
    "create_hbox_layout",
    "create_progress_bar",
    "create_qhbox_with_widgets",
    "create_spinbox",
    "create_tinted_icon",
    "create_vbox_layout",
    "get_handle_points_from_rect",
    "post_data_table_init",
]