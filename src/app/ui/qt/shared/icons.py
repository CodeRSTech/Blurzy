"""Module for icons; implements the Qt presentation components.

See Also:
    - [`TransportControlsPanel`][app.ui.qt.sections.transport_controls_panel.TransportControlsPanel] — uses tinted icons for playback controls
    - [`bundled_resource_path`][app.shared.distribution.bundled_resource_path] — resolves packaged icon assets

Layer: Presentation.
Context: Implements the qt presentation components at this architectural boundary.
"""

from __future__ import annotations

from typing import TYPE_CHECKING





from PySide6.QtGui import QPixmap, QIcon, Qt, QPainter
if TYPE_CHECKING:
    from pathlib import Path
    from PySide6.QtCore import QSize



def create_tinted_icon(icon_path: Path, icon_size: QSize, normal_tint, disabled_tint) -> QIcon:
    """Create normal, active, and disabled icon pixmaps tinted for the UI palette.

Args:
    icon_path: Path to the source icon.
    icon_size: Size at which to load the source pixmap.
    normal_tint: Color applied to normal and active icon states.
    disabled_tint: Color applied to the disabled icon state.

Returns:
    Tinted icon, or an empty icon if the source pixmap cannot be loaded.
"""
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
