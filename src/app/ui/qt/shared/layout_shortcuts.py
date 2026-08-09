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
    layout = _apply_layout_config(QtWidgets.QVBoxLayout(parent), margins=margins, spacing=spacing)
    if widgets is not None:
        _add_widgets(layout, widgets)
    return layout
