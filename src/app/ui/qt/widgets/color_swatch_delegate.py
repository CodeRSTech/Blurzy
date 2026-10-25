"""Paint annotation color values as compact, accessible table swatches.

The delegate leaves normal cell background and selection painting to Qt, then
draws the stored color value as a centered rectangle.
"""

from __future__ import annotations

from PySide6.QtCore import QModelIndex, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QPalette
from PySide6.QtWidgets import QStyleOptionViewItem, QStyledItemDelegate


COLOR_SWATCH_ROLE = Qt.ItemDataRole.UserRole + 1


class ColorSwatchDelegate(QStyledItemDelegate):
    """Render a centered color rectangle without printing the hex value."""

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex) -> None:
        """Draw the cell and, when valid, its bordered color swatch.

        Args:
            painter: Painter supplied by the item view.
            option: Cell geometry, palette, and selection state.
            index: Model index containing `COLOR_SWATCH_ROLE`.
        """
        super().paint(painter, option, index)
        color = QColor(index.data(COLOR_SWATCH_ROLE))
        if not color.isValid():
            return

        swatch_rect = option.rect.adjusted(8, 5, -8, -5)
        if swatch_rect.isEmpty():
            return
        painter.save()
        painter.setPen(QPen(option.palette.color(QPalette.ColorRole.Mid), 1))
        painter.setBrush(color)
        painter.drawRect(swatch_rect)
        painter.restore()
