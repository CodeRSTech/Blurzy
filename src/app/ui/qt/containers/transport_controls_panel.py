from pathlib import Path
from typing import TYPE_CHECKING, final

from PySide6.QtCore import Qt, Slot, QSignalBlocker, Signal, QSize
from PySide6.QtGui import QIcon, QPainter, QPalette, QPixmap
from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QSlider, QHBoxLayout, QLabel

from app.shared.logging_cfg import get_logger

if TYPE_CHECKING:
    pass

logger = get_logger("UI-> Transport Control Panel")


@final
class TransportControlsPanel(QVBoxLayout):
    seek_pos_changed = Signal(int)

    def __init__(self, parent: QWidget):
        self._parent = parent
        super().__init__(parent)

        # Keep resource resolution local so this layout is self-contained.
        self._icons_dir = Path(__file__).resolve().parent.parent / "resources" / "icons"

        # All widgets are strictly instantiated as instance attributes here.
        self._init_widgets()
        self._configure_icon_buttons()
        self._build_ui()
        self._connect_signals()
        self.refresh_theme_icons()

    def _init_widgets(self) -> None:
        # --- UI Elements: Transport controls ---
        self.play_btn = QPushButton("")
        self.pause_btn = QPushButton("")
        self.previous_btn = QPushButton("")
        self.next_btn = QPushButton("")
        self.rotate_ccw_btn = QPushButton("")
        self.rotate_cw_btn = QPushButton("")
        self.seek_slider = QSlider(Qt.Orientation.Horizontal)

        self.play_btn.setToolTip("Play")
        self.pause_btn.setToolTip("Pause")
        self.previous_btn.setToolTip("Previous Frame")
        self.next_btn.setToolTip("Next Frame")
        self.rotate_ccw_btn.setToolTip("Rotate CCW")
        self.rotate_cw_btn.setToolTip("Rotate CW")

        self.frame_label = QLabel("Waiting for user to load video(s).")

    def _configure_icon_buttons(self) -> None:
        """Make transport buttons icon-only with a minimal hoverable surface."""
        for button in (
            self.play_btn,
            self.pause_btn,
            self.previous_btn,
            self.next_btn,
            self.rotate_ccw_btn,
            self.rotate_cw_btn,
        ):
            button.setFlat(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setFixedSize(30, 30)
            button.setStyleSheet(
                "QPushButton {"
                " border: none;"
                " background: transparent;"
                " padding: 2px;"
                " }"
                "QPushButton:hover {"
                " background: rgba(127, 127, 127, 0.14);"
                " border-radius: 5px;"
                " }"
                "QPushButton:pressed {"
                " background: rgba(127, 127, 127, 0.24);"
                " border-radius: 5px;"
                " }"
                "QPushButton:disabled {"
                " background: transparent;"
                " }"
            )

    def _apply_transport_icons(self) -> None:
        """Apply bundled icons to transport controls using palette-aware tint colors."""
        icon_bindings: tuple[tuple[QPushButton, str], ...] = (
            (self.play_btn, "play-line.svg"),
            (self.pause_btn, "pause-line.svg"),
            (self.previous_btn, "skip-back-line.svg"),
            (self.next_btn, "skip-forward-line.svg"),
            (self.rotate_ccw_btn, "anticlockwise-2-line.svg"),
            (self.rotate_cw_btn, "clockwise-2-line.svg"),
        )

        palette = self.play_btn.palette()
        normal_tint = palette.color(QPalette.ColorGroup.Active, QPalette.ColorRole.ButtonText)
        disabled_tint = palette.color(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText)
        icon_size = QSize(16, 16)

        for button, filename in icon_bindings:
            icon_path = self._icons_dir / filename
            if not icon_path.exists():
                logger.warning("Transport icon missing: {}", icon_path)
                continue

            tinted_icon = self._create_tinted_icon(icon_path, icon_size, normal_tint, disabled_tint)
            if tinted_icon.isNull():
                # Fallback to plain icon if tint pipeline fails unexpectedly.
                button.setIcon(QIcon(str(icon_path)))
            else:
                button.setIcon(tinted_icon)
            button.setIconSize(icon_size)

    @staticmethod
    def _create_tinted_icon(icon_path: Path, icon_size: QSize, normal_tint, disabled_tint) -> QIcon:
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

    def refresh_theme_icons(self) -> None:
        """Recompute transport icons after runtime palette/style changes."""
        self._apply_transport_icons()

    def _build_ui(self) -> None:
        self.seek_slider.setMinimum(0)
        self.seek_slider.setMaximum(0)
        self.seek_slider.setValue(0)

        self.addWidget(self.seek_slider)

        btn_row = QHBoxLayout()

        btn_row.addWidget(self.play_btn)
        btn_row.addWidget(self.pause_btn)
        btn_row.addWidget(self.previous_btn)
        btn_row.addWidget(self.next_btn)
        btn_row.addWidget(self.rotate_ccw_btn)
        btn_row.addWidget(self.rotate_cw_btn)
        btn_row.addStretch()
        btn_row.addWidget(self.frame_label)

        self.addLayout(btn_row)

    def _connect_signals(self) -> None:
        self.seek_slider.sliderReleased.connect(self._emit_seek_pos)
        self.rotate_ccw_btn.clicked.connect(self._on_rotate_ccw_clicked)
        self.rotate_cw_btn.clicked.connect(self._on_rotate_cw_clicked)

    @Slot()
    def _emit_seek_pos(self):
        idx = int(self.seek_slider.value())
        logger.trace(f"Seek requested: {idx}")
        self.seek_pos_changed.emit(idx)

    @Slot()
    def _on_rotate_ccw_clicked(self) -> None:
        """Temporary placeholder until rotation flow is reconnected to session/video state."""
        logger.warning("Rotate CCW clicked, but rotation handling is not wired yet.")

    @Slot()
    def _on_rotate_cw_clicked(self) -> None:
        """Temporary placeholder until rotation flow is reconnected to session/video state."""
        logger.warning("Rotate CW clicked, but rotation handling is not wired yet.")

    @Slot(bool)
    def update_video_related_widgets_state(self, is_enabled: bool = False) -> None:
        for widget in (
            self.play_btn,
            self.pause_btn,
            self.previous_btn,
            self.next_btn,
            self.rotate_ccw_btn,
            self.rotate_cw_btn,
            self.seek_slider,
        ):
            widget.setEnabled(is_enabled)

    def set_seek_value(self, frame_index: int) -> None:
        """Set the seek position to the given frame index."""
        with QSignalBlocker(self.seek_slider):
            self.seek_slider.setValue(max(0, frame_index))

    def set_seek_range(self, maximum_frame_index: int) -> None:
        """Update seek slider with maximum frame index."""
        self.seek_slider.setMinimum(0)
        self.seek_slider.setMaximum(max(0, maximum_frame_index))

    def set_frame_label_text(self, text: str):
        self.frame_label.setText(text)
