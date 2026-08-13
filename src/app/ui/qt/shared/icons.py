from __future__ import annotations

from typing import TYPE_CHECKING





from PySide6.QtGui import QPixmap, QIcon, Qt, QPainter
if TYPE_CHECKING:
    from pathlib import Path
    from PySide6.QtCore import QSize



def create_tinted_icon(icon_path: Path, icon_size: QSize, normal_tint, disabled_tint) -> QIcon:
    """Tint a monochrome icon so it matches active light/dark palettes."""
    base_icon = QIcon(str(icon_path))
    source = base_icon.pixmap(icon_size)
    if source.isNull():
        return QIcon()

    def _tint_pixmap(tint_color) -> QPixmap:
        tinted = QPixmap(source.size())
        tinted.fill(Qt.GlobalColor.transparent)

        painter = QPainter(tinted)
        painter.drawPixmap(0, 0, source)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
        painter.fillRect(tinted.rect(), tint_color)
        painter.end()
        return tinted

    icon = QIcon()
    icon.addPixmap(_tint_pixmap(normal_tint), QIcon.Mode.Normal)
    icon.addPixmap(_tint_pixmap(normal_tint), QIcon.Mode.Active)
    icon.addPixmap(_tint_pixmap(disabled_tint), QIcon.Mode.Disabled)
    return icon
