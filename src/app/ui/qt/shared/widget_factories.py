"""
Module for widget factories; implements the Qt presentation components.

See Also:
    - [`create_hbox_layout`][app.ui.qt.shared.layout_shortcuts.create_hbox_layout] — provides layouts used by widget factories
    - [`RightControlPanel`][app.ui.qt.sections.right_panel.RightControlPanel] — composes reusable controls

Layer: Presentation.
Context: Implements the qt presentation components at this architectural boundary.
"""

from __future__ import annotations

from typing import TYPE_CHECKING


from PySide6.QtWidgets import (
    QTableWidget,
    QHeaderView,
    QAbstractItemView,
    QProgressBar,
    QDoubleSpinBox,
    QSpinBox,
)

from app.ui.qt.shared.layout_shortcuts import create_hbox_layout
if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget, QHBoxLayout


def create_qhbox_with_widgets(widgets: list[QWidget] | tuple[QWidget, ...]) -> QHBoxLayout:
    """
    Create a horizontal layout containing the supplied widgets.

    Args:
        widgets: Widgets to add to the layout in order.

    Returns:
        Horizontal layout containing `widgets`.
    """
    return create_hbox_layout(widgets=widgets)


def create_progress_bar(
    minimum: int, maximum: int, text_visible: bool = False, visible: bool = True
) -> QProgressBar:
    """
    Create and configure a Qt progress bar.

    Args:
        minimum: Lower end of the displayed progress range.
        maximum: Upper end of the displayed progress range.
        text_visible: Whether Qt should display progress text inside the bar.
        visible: Initial visibility of the bar.

    Returns:
        Progress bar configured with the requested range and visibility.
    """
    progress_bar = QProgressBar()
    progress_bar.setRange(minimum, maximum)
    progress_bar.setTextVisible(text_visible)
    progress_bar.setVisible(visible)
    return progress_bar


def create_spinbox(
    min_val: float, max_val: float, step: float, default: float
) -> QDoubleSpinBox:
    """
    Create a two-decimal floating-point spin box.

    Args:
        min_val: Minimum permitted value.
        max_val: Maximum permitted value.
        step: Increment for arrow-button adjustments.
        default: Initial value, clamped by Qt to the configured range.

    Returns:
        Configured `QDoubleSpinBox`.
    """
    spinbox = QDoubleSpinBox()
    spinbox.setRange(min_val, max_val)
    spinbox.setSingleStep(step)
    spinbox.setDecimals(2)
    spinbox.setValue(default)
    return spinbox


def create_int_spinbox(min_val: int, max_val: int, step: int, default: int) -> QSpinBox:
    """
    Create an integer spin box with an explicit inclusive range.

    Args:
        min_val: Smallest accepted integer.
        max_val: Largest accepted integer.
        step: Increment used by the spin-box arrows.
        default: Initial value, clamped by Qt to the supplied range.

    Returns:
        A configured `QSpinBox`.

    Note:
        Use this for settings whose values represent discrete pixels or frames.

    Example:
        gap = create_int_spinbox(1, 60, 1, 25)
    """
    spinbox = QSpinBox()
    spinbox.setRange(min_val, max_val)
    spinbox.setSingleStep(step)
    spinbox.setValue(default)
    return spinbox


def create_blur_strength_spinbox(default: float) -> QDoubleSpinBox:
    """
    Create blur strength spinbox.

    Args:
        default: Initial blur-strength value, clamped to `[0, 255]`.

    Returns:
        `QDoubleSpinBox` with range 0–255 and unit increments.
    """
    return create_spinbox(0.0, 255.0, 1.0, default)


def post_data_table_init(data_table: QTableWidget) -> None:
    """
    Apply standard setup after the data table is created.

    Args:
        data_table: Table to configure for read-only extended row selection.
    """
    data_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    data_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    data_table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
    data_table.verticalHeader().setVisible(False)
    data_table.horizontalHeader().setStretchLastSection(True)
    data_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
