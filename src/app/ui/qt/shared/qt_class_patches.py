from __future__ import annotations

from PySide6 import QtWidgets

from app.shared.logging_cfg import get_logger

logger = get_logger("Shared->QtUiShortcuts")

_PATCHED = False
OrderedWidgets = list[QtWidgets.QWidget] | tuple[QtWidgets.QWidget, ...]


def _hbox_add_widgets(self: QtWidgets.QHBoxLayout, widgets: OrderedWidgets) -> QtWidgets.QHBoxLayout:
    for widget in widgets:
        self.addWidget(widget)
    return self


def _vbox_add_widgets(self: QtWidgets.QVBoxLayout, widgets: OrderedWidgets) -> QtWidgets.QVBoxLayout:
    for widget in widgets:
        self.addWidget(widget)
    return self


def _hbox_create(
    _cls: type[QtWidgets.QHBoxLayout],
    parent: QtWidgets.QWidget | None = None,
    *,
    margins: tuple[int, int, int, int] | None = None,
    spacing: int | None = None,
    widgets: OrderedWidgets | None = None,
) -> QtWidgets.QHBoxLayout:
    from app.ui.qt.shared.layout_shortcuts import create_hbox_layout

    return create_hbox_layout(parent=parent, margins=margins, spacing=spacing, widgets=widgets)


def _vbox_create(
    _cls: type[QtWidgets.QVBoxLayout],
    parent: QtWidgets.QWidget | None = None,
    *,
    margins: tuple[int, int, int, int] | None = None,
    spacing: int | None = None,
    widgets: OrderedWidgets | None = None,
) -> QtWidgets.QVBoxLayout:
    from app.ui.qt.shared.layout_shortcuts import create_vbox_layout

    return create_vbox_layout(parent=parent, margins=margins, spacing=spacing, widgets=widgets)


def apply_qt_ui_shortcuts() -> None:
    """Inject convenience methods onto common Qt layout classes."""
    global _PATCHED
    if _PATCHED:
        logger.debug("Qt UI shortcut patches already applied.")
        return

    logger.debug("Injecting PySide6 Qt UI shortcut patches...")
    QtWidgets.QHBoxLayout.addWidgets = _hbox_add_widgets  # type: ignore[attr-defined]
    QtWidgets.QVBoxLayout.addWidgets = _vbox_add_widgets  # type: ignore[attr-defined]
    QtWidgets.QHBoxLayout.create = classmethod(_hbox_create)  # type: ignore[attr-defined]
    QtWidgets.QVBoxLayout.create = classmethod(_vbox_create)  # type: ignore[attr-defined]
    _PATCHED = True
    logger.debug("PySide6 Qt UI shortcut patches successfully applied.")
