from __future__ import annotations

from typing import TYPE_CHECKING

from typing import final

from PySide6.QtCore import Qt, Slot, QSignalBlocker, Signal, QSize
from PySide6.QtGui import QIcon, QPalette
from PySide6.QtWidgets import QVBoxLayout, QPushButton, QSlider, QLabel, QRadioButton, QButtonGroup

from app.shared.distribution import bundled_resource_path
from app.shared.logging_cfg import get_logger
from app.ui.qt.shared.layout_shortcuts import create_hbox_layout
from app.ui.qt.shared.icons import create_tinted_icon
from app.ui.view_state.preview_state import ToolMode
if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget


logger = get_logger("UI-> Transport Control Panel")


@final
class TransportControlsPanel(QVBoxLayout):
    seek_pos_changed = Signal(int)
    rotate_requested = Signal(int)
    fit_view_requested = Signal()

    def __init__(self, parent: QWidget):
        self._parent = parent
        super().__init__(parent)

        # Keep resource resolution local so this layout is self-contained.
        self._icons_dir = bundled_resource_path("icons")

        # All widgets are strictly instantiated as instance attributes here.
        self._init_widgets()
        self._init_mode_controls()
        self._configure_mode_buttons()
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
        self.fit_view_btn = QPushButton("Fit View")
        self.seek_slider = QSlider(Qt.Orientation.Horizontal)
        self.add_mode_btn = QRadioButton("Add")
        self.edit_mode_btn = QRadioButton("Edit")
        self.delete_mode_btn = QRadioButton("Delete")
        self.delete_mode_btn.setVisible(False)
        self.edit_mode_btn.setChecked(True)
        self._rotation_degrees = 0
        self._zoom_factor = 1.0
        self._is_panned = False

        self.play_btn.setToolTip("Play")
        self.pause_btn.setToolTip("Pause")
        self.previous_btn.setToolTip("Previous Frame")
        self.next_btn.setToolTip("Next Frame")
        self.rotate_ccw_btn.setToolTip("Rotate CCW")
        self.rotate_cw_btn.setToolTip("Rotate CW")
        self.fit_view_btn.setToolTip("Fit preview back to the available viewport")

        self.frame_label = QLabel("Waiting for user to load video(s).")
        self.view_state_label = QLabel("")
        self._refresh_view_state_label()

    def _init_mode_controls(self) -> None:
        self.tool_group = QButtonGroup(self._parent)
        self.tool_group.addButton(self.add_mode_btn, ToolMode.ADD.value)
        self.tool_group.addButton(self.edit_mode_btn, ToolMode.EDIT.value)
        self.tool_group.addButton(self.delete_mode_btn, ToolMode.DELETE.value)

    def _configure_mode_buttons(self) -> None:
        for button in (self.add_mode_btn, self.edit_mode_btn, self.delete_mode_btn):
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setMinimumHeight(24)
            button.setStyleSheet(
                "QRadioButton {"
                " spacing: 6px;"
                " margin: 0px;"
                " padding: 0px;"
                " }"
                "QRadioButton::indicator {"
                " margin-right: 2px;"
                " }"
            )

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
            button.setFixedSize(40, 40)
            button.setStyleSheet(
                "QPushButton {"
                " border: none;"
                " background: transparent;"
                " padding: 0px;"
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
        self.fit_view_btn.setCursor(Qt.CursorShape.PointingHandCursor)

    def _apply_transport_icons(self) -> None:
        """Apply bundled icons to transport controls using palette-aware tint colors."""
        palette = self.play_btn.palette()
        normal_tint = palette.color(QPalette.ColorGroup.Active, QPalette.ColorRole.ButtonText)
        disabled_tint = palette.color(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText)
        transport_icon_size = QSize(24, 24)
        mode_icon_size = QSize(18, 18)

        icon_bindings = (
            (self.play_btn, "play-line.svg", transport_icon_size),
            (self.pause_btn, "pause-line.svg", transport_icon_size),
            (self.previous_btn, "skip-back-line.svg", transport_icon_size),
            (self.next_btn, "skip-forward-line.svg", transport_icon_size),
            (self.rotate_ccw_btn, "anticlockwise-2-line.svg", transport_icon_size),
            (self.rotate_cw_btn, "clockwise-2-line.svg", transport_icon_size),
            (self.add_mode_btn, "add-box-line.svg", mode_icon_size),
            (self.edit_mode_btn, "edit-box-line.svg", mode_icon_size),
            (self.delete_mode_btn, "eraser-line.svg", mode_icon_size),
        )

        for button, filename, icon_size in icon_bindings:
            icon_path = self._icons_dir / filename
            if not icon_path.exists():
                logger.warning("Control icon missing: {}", icon_path)
                continue

            tinted_icon = create_tinted_icon(icon_path, icon_size, normal_tint, disabled_tint)
            if tinted_icon.isNull():
                # Fallback to plain icon if tint pipeline fails unexpectedly.
                button.setIcon(QIcon(str(icon_path)))
            else:
                button.setIcon(tinted_icon)
            button.setIconSize(icon_size)



    def refresh_theme_icons(self) -> None:
        """Recompute transport icons after runtime palette/style changes."""
        self._apply_transport_icons()

    def _build_ui(self) -> None:
        self.seek_slider.setMinimum(0)
        self.seek_slider.setMaximum(0)
        self.seek_slider.setValue(0)

        self.addWidgets((self.seek_slider,))  # type: ignore[attr-defined]

        btn_row = create_hbox_layout(
            widgets=(
                self.play_btn,
                self.pause_btn,
                self.previous_btn,
                self.next_btn,
                self.rotate_ccw_btn,
                self.rotate_cw_btn,
                self.fit_view_btn,
            )
        )

        btn_row.addSpacing(12)
        btn_row.addWidgets((self.add_mode_btn, self.edit_mode_btn))  # type: ignore[attr-defined]
        btn_row.addSpacing(12)
        btn_row.addWidget(self.view_state_label)
        btn_row.addSpacing(12)
        btn_row.addStretch()
        btn_row.addWidget(self.frame_label)

        self.addLayout(btn_row)

    def _connect_signals(self) -> None:
        self.seek_slider.sliderReleased.connect(self._emit_seek_pos)
        self.rotate_ccw_btn.clicked.connect(lambda _checked=False: self.rotate_requested.emit(-90))
        self.rotate_cw_btn.clicked.connect(lambda _checked=False: self.rotate_requested.emit(90))
        self.fit_view_btn.clicked.connect(lambda _checked=False: self.fit_view_requested.emit())

    @Slot()
    def _emit_seek_pos(self):
        idx = int(self.seek_slider.value())
        logger.trace(f"Seek requested: {idx}")
        self.seek_pos_changed.emit(idx)

    @Slot(bool)
    def update_video_related_widgets_state(self, is_enabled: bool = False) -> None:
        for widget in (
            self.play_btn,
            self.pause_btn,
            self.previous_btn,
            self.next_btn,
            self.rotate_ccw_btn,
            self.rotate_cw_btn,
            self.fit_view_btn,
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

    @Slot(float, float, float)
    def set_viewport_state(self, zoom_factor: float, pan_x: float, pan_y: float) -> None:
        self._zoom_factor = zoom_factor
        self._is_panned = abs(pan_x) > 0.5 or abs(pan_y) > 0.5
        self._refresh_view_state_label()

    def set_rotation_degrees(self, rotation_degrees: int) -> None:
        self._rotation_degrees = rotation_degrees % 360
        self._refresh_view_state_label()

    def _refresh_view_state_label(self) -> None:
        position_label = "Panned" if self._is_panned else "Fit"
        self.view_state_label.setText(
            f"View: {int(round(self._zoom_factor * 100))}% · {position_label} · Rot: {self._rotation_degrees}°"
        )
