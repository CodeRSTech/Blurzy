from __future__ import annotations

from typing import TYPE_CHECKING


from PySide6.QtWidgets import QTableWidget, QHeaderView, QAbstractItemView, QProgressBar, QDoubleSpinBox

from app.ui.qt.shared.layout_shortcuts import create_hbox_layout
if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget, QHBoxLayout



def create_qhbox_with_widgets(widgets: list[QWidget] | tuple[QWidget, ...]) -> QHBoxLayout:
    return create_hbox_layout(widgets=widgets)


def create_progress_bar(
    minimum: int, maximum: int, text_visible: bool = False, visible: bool = True
) -> QProgressBar:
    progress_bar = QProgressBar()
    progress_bar.setRange(minimum, maximum)
    progress_bar.setTextVisible(text_visible)
    progress_bar.setVisible(visible)
    return progress_bar


def create_spinbox(min_val: float, max_val: float, step: float, default: float) -> QDoubleSpinBox:
    spinbox = QDoubleSpinBox()
    spinbox.setRange(min_val, max_val)
    spinbox.setSingleStep(step)
    spinbox.setDecimals(2)
    spinbox.setValue(default)
    return spinbox


def post_data_table_init(data_table: QTableWidget) -> None:
    data_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    data_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    data_table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
    data_table.verticalHeader().setVisible(False)
    data_table.horizontalHeader().setStretchLastSection(True)
    data_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
