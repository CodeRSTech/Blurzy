from typing import TYPE_CHECKING, final

from PySide6.QtCore import Qt, Slot, QSignalBlocker, Signal
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

        # All widgets are strictly instantiated as instance attributes here.
        self._init_widgets()
        self._build_ui()
        self._connect_signals()

    def _init_widgets(self) -> None:
        # --- UI Elements: Transport controls ---
        self.play_btn = QPushButton("Play")
        self.pause_btn = QPushButton("Pause")
        self.previous_btn = QPushButton("Previous Frame")
        self.next_btn = QPushButton("Next Frame")
        self.seek_slider = QSlider(Qt.Orientation.Horizontal)

        self.frame_label = QLabel("Waiting for user to load video(s).")

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
        btn_row.addStretch()
        btn_row.addWidget(self.frame_label)

        self.addLayout(btn_row)

    def _connect_signals(self) -> None:
        self.seek_slider.sliderReleased.connect(self._emit_seek_pos)

    @Slot()
    def _emit_seek_pos(self):
        idx = int(self.seek_slider.value())
        logger.trace(f"Seek requested: {idx}")
        self.seek_pos_changed.emit(idx)

    @Slot(bool)
    def update_video_related_widgets_state(self, is_enabled: bool = False) -> None:
        for widget in (self.play_btn,
                    self.pause_btn,
                    self.previous_btn,
                    self.next_btn,
                    self.seek_slider):
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
