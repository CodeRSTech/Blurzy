from __future__ import annotations

from PySide6.QtCore import QRect, QPoint
from PySide6.QtWidgets import (
    QWidget,
    QTableWidget,
    QHeaderView,
    QAbstractItemView,
    QHBoxLayout,
    QProgressBar,
    QDoubleSpinBox,
)


def create_qhbox_with_widgets(widgets: list[QWidget]) -> QHBoxLayout:
    parent_layout = QHBoxLayout()
    for widget in widgets:
        parent_layout.addWidget(widget)
    return parent_layout


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


def handle_points(rect: QRect) -> list[QPoint]:
    x1, y1, x2, y2 = rect.left(), rect.top(), rect.right(), rect.bottom()
    mx, my = (x1 + x2) // 2, (y1 + y2) // 2
    return [
        QPoint(x1, y1),
        QPoint(mx, y1),
        QPoint(x2, y1),
        QPoint(x1, my),
        QPoint(x2, my),
        QPoint(x1, y2),
        QPoint(mx, y2),
        QPoint(x2, y2),
    ]
