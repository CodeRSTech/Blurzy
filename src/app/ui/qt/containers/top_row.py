from typing import final

from PySide6.QtCore import Signal, Slot
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QHBoxLayout, QWidget, QPushButton, QFileDialog


@final
class TopRow(QHBoxLayout):

    open_videos_requested = Signal(list)

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self._parent = parent
        # Container to hold everything inside the scroll area
        #self._container = QWidget()
        self._layout = QHBoxLayout()

        # All widgets are strictly instantiated as instance attributes here.
        self._init_widgets()
        self._build_ui()
        self._connect_signals()

    def _build_ui(self):
        self._layout.addWidget(self.open_btn)
        self._layout.addWidget(self.rotate_ccw_btn)
        self._layout.addWidget(self.rotate_cw_btn)
        self._layout.addWidget(self.export_all_btn)
        self._layout.addStretch()

    def _init_widgets(self) -> None:
        self.open_btn = QPushButton("Open File")
        self.rotate_ccw_btn = QPushButton("Rotate CCW")
        self.rotate_cw_btn = QPushButton("Rotate CW")
        self.export_all_btn = QPushButton("Export All")
        self.open_action = QAction("Open Video(s)...", self)
        self.export_all_action = QAction("Export All...", self)

    def _connect_signals(self) -> None:
        self.open_btn.clicked.connect(self.choose_video_files)
        self.open_action.triggered.connect(self.choose_video_files)
        #self.export_all_btn.clicked.connect()
        #self.export_all_action.triggered.connect()

    def as_layout(self) -> QHBoxLayout:
        """Expose the populated row layout for alternate window shells that embed it inside a host widget."""
        return self._layout


    @Slot()
    def choose_video_files(self) -> None:
        # SIGNAL CHAIN / CASCADE DEFINITION
        # ---------------------------------
        # Originates here and triggers the following downstream pipeline:
        # TopRow.choose_video_files()
        #   ├──> Launch `QFileDialog.getOpenFileNames()` and get list of file paths.
        #   └──> Emit `open_videos_requested` with list of paths
        #               └──> SessionHandler.on_open_videos(paths: list[str])
        #                       └──> Handles open-video logic.
        #
        paths, _ = QFileDialog.getOpenFileNames(
            self._parent,
            "Open Video Files",
            "",
            "Video Files (*.mp4 *.avi *.mov *.mkv *.wmv *.m4v);;All Files (*)",
        )
        if paths:
            self.open_videos_requested.emit(paths)

    #@Slot(bool)
    #def update_video_related_widgets_state(self, is_enabled: bool = False) -> None:
    #    for btn in (self.reset_frame_btn,
    #                self.reset_all_btn,
    #                self.reset_tracker_frame_btn,
    #                self.reset_all_trackers_btn):
    #        btn.setEnabled(is_enabled)
