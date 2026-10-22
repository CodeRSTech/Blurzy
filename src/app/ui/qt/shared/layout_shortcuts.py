"""Module for layout shortcuts; implements the Qt presentation components.

See Also:
    - [`widget_factories`][app.ui.qt.shared.widget_factories] — combines reusable layouts with widget constructors
    - [`CollapsiblePanel`][app.ui.qt.widgets.collapsible_panel.CollapsiblePanel] — uses the shared layout helpers

Layer: Presentation.
Context: Implements the qt presentation components at this architectural boundary.
"""

from __future__ import annotations

from typing import TypeVar

from PySide6 import QtWidgets

Margins = tuple[int, int, int, int]
OrderedWidgets = list[QtWidgets.QWidget] | tuple[QtWidgets.QWidget, ...]

_BoxLayoutT = TypeVar("_BoxLayoutT", QtWidgets.QHBoxLayout, QtWidgets.QVBoxLayout)


def _validate_widgets(widgets: OrderedWidgets) -> None:
    if not isinstance(widgets, (list, tuple)):
        raise TypeError("widgets must be an ordered sequence (list or tuple)")


def _add_widgets(layout: _BoxLayoutT, widgets: OrderedWidgets) -> _BoxLayoutT:
    _validate_widgets(widgets)
    for widget in widgets:
        layout.addWidget(widget)
    return layout


def _apply_layout_config(
    layout: _BoxLayoutT,
    margins: Margins | None = None,
    spacing: int | None = None,
) -> _BoxLayoutT:
    if margins is not None:
        layout.setContentsMargins(*margins)
    if spacing is not None:
        layout.setSpacing(spacing)
    return layout


def create_hbox_layout(
    parent: QtWidgets.QWidget | None = None,
    *,
    margins: Margins | None = None,
    spacing: int | None = None,
    widgets: OrderedWidgets | None = None,
) -> QtWidgets.QHBoxLayout:
    """Create a horizontal layout with optional margins, spacing, and widgets.

    Args:
        parent: Widget that owns the layout, if any.
        margins: Optional left, top, right, and bottom content margins.
        spacing: Optional spacing between child widgets.
        widgets: Optional ordered list or tuple of widgets to add.

    Returns:
        Configured horizontal layout.
    """
    layout = _apply_layout_config(QtWidgets.QHBoxLayout(parent), margins=margins, spacing=spacing)
    if widgets is not None:
        _add_widgets(layout, widgets)
    return layout


def create_vbox_layout(
    parent: QtWidgets.QWidget | None = None,
    *,
    margins: Margins | None = None,
    spacing: int | None = None,
    widgets: OrderedWidgets | None = None,
) -> QtWidgets.QVBoxLayout:
    """Create a vertical layout with optional margins, spacing, and widgets.

    Args:
        parent: Widget that owns the layout, if any.
        margins: Optional left, top, right, and bottom content margins.
        spacing: Optional spacing between child widgets.
        widgets: Optional ordered list or tuple of widgets to add.

    Returns:
        Configured vertical layout.
    """
    layout = _apply_layout_config(QtWidgets.QVBoxLayout(parent), margins=margins, spacing=spacing)
    if widgets is not None:
        _add_widgets(layout, widgets)
    return layout
