from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import final, override

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QButtonGroup,
    QLabel,
    QMainWindow,
    QMessageBox,
    QRadioButton,
    QSplitter,
    QStatusBar,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from app.domain.session.session_id import SessionId
from app.domain.video.layer_group import VideoDataLayerGroup
from app.domain.views import ModelSelectionViewModel, SessionSettingsViewModel
from app.shared.logging_cfg import get_logger
from app.ui.qt.containers import (
    BottomDataPanelContainer,
    PreviewContainer,
    RightControlPanel,
    TopRow,
    TransportControlsPanel,
)
from app.ui.qt.utilities.helpers import create_progress_bar
from app.ui.state.preview_state import ToolMode

logger = get_logger("UI->MainWindow")


@dataclass(frozen=True, slots=True)
class _WindowSplitterDefaults:
    main_sizes: tuple[int, int] = (980, 320)
    left_sizes: tuple[int, int] = (620, 230)
    main_stretch: tuple[int, int] = (4, 1)
    left_stretch: tuple[int, int] = (5, 2)
    progress_range: tuple[int, int] = (0, 100)
    handle_width: int = 8


@final
class MainWindow(QMainWindow):
    """Alternative window shell that preserves the current UI API while using a cleaner layout assembly."""

    open_file_requested = Signal()
    tool_mode_changed = Signal(ToolMode)
    session_selected = Signal(object)

    def __init__(self) -> None:
        logger.info("Initializing modular UI window...")
        super().__init__()

        self._splitter_defaults = _WindowSplitterDefaults()
        self._close_request_handler: Callable[[], bool] | None = None

        self.setWindowTitle("EasyBlur")
        self.resize(1300, 850)

        self._init_mode_controls()
        self._init_sections()
        self._build_toolbar()
        self._build_ui()
        self._build_status_bar()
        self._connect_signals()

        logger.info("Modular UI window initialized.")

    @override
    def __repr__(self) -> str:
        return "MainWindow()"

    @override
    def __str__(self) -> str:
        return f"MainWindow [{self.size().width()}x{self.size().height()}]"

    def _init_mode_controls(self) -> None:
        self.add_mode_btn = QRadioButton("Add Box")
        self.edit_mode_btn = QRadioButton("Edit / Select")
        self.delete_mode_btn = QRadioButton("Delete Box")
        self.edit_mode_btn.setChecked(True)

        self.tool_group = QButtonGroup(self)
        self.tool_group.addButton(self.add_mode_btn, ToolMode.ADD.value)
        self.tool_group.addButton(self.edit_mode_btn, ToolMode.EDIT.value)
        self.tool_group.addButton(self.delete_mode_btn, ToolMode.DELETE.value)

    def _init_sections(self) -> None:
        self.preview_container = PreviewContainer()
        self.top_row = TopRow(self)
        self.right_panel = RightControlPanel(self)
        self.bottom_panel = BottomDataPanelContainer(self)
        self.transport_panel = TransportControlsPanel(self)

        self.right_panel.setMinimumWidth(0)
        self.bottom_panel.setMinimumHeight(0)

        self.info_label = QLabel("No session loaded")
        progress_minimum, progress_maximum = self._splitter_defaults.progress_range
        self.export_progress_bar = create_progress_bar(
            minimum=progress_minimum,
            maximum=progress_maximum,
            text_visible=True,
            visible=False,
        )
        self.export_overall_progress_bar = create_progress_bar(
            minimum=progress_minimum,
            maximum=progress_maximum,
            text_visible=True,
            visible=False,
        )

    @property
    def active_tab_index(self) -> VideoDataLayerGroup:
        return VideoDataLayerGroup(self.bottom_panel.active_tab_index)

    @property
    def selected_s_id(self) -> SessionId:
        return self.bottom_panel.selected_s_id

    @property
    def selected_frame_box_keys(self) -> list[str]:
        return self.bottom_panel.get_selected_box_keys_from_active_tab

    @override
    def closeEvent(self, event: QCloseEvent) -> None:
        if self._close_request_handler is not None and not self._close_request_handler():
            event.ignore()
            return
        super().closeEvent(event)

    def confirm_export_in_progress_exit(self) -> bool:
        result = QMessageBox.question(
            self,
            "Export in Progress",
            "An export is currently in progress. Exit anyway?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return result == QMessageBox.StandardButton.Yes

    def set_export_enabled(self, enabled: bool) -> None:
        self.right_panel.export_btn.setEnabled(enabled)

    def set_export_busy(self, is_busy: bool, status_text: str | None = None) -> None:
        self.right_panel.export_btn.setEnabled(not is_busy)
        self.top_row.export_all_btn.setEnabled(not is_busy)
        self.top_row.export_all_action.setEnabled(not is_busy)
        self.export_progress_bar.setVisible(is_busy)
        self._reset_export_progress_bar()
        if not is_busy:
            self.export_overall_progress_bar.setVisible(False)
            self._reset_export_overall_progress_bar()
        if status_text is not None:
            self.set_status_text(status_text)

    def set_export_progress(self, current: int, total: int, label: str = "Exporting") -> None:
        maximum = max(total, 1)
        _, progress_maximum = self._splitter_defaults.progress_range
        percent = int((current / maximum) * progress_maximum)
        self.export_progress_bar.setValue(max(0, min(percent, progress_maximum)))
        self.export_progress_bar.setFormat(f"{label}: {current}/{total}")

    def set_export_progress_status(self, label: str) -> None:
        self.export_progress_bar.setValue(0)
        self.export_progress_bar.setFormat(label)

    def set_export_overall_busy(self, is_busy: bool) -> None:
        self.export_overall_progress_bar.setVisible(is_busy)
        self._reset_export_overall_progress_bar()

    def set_export_overall_progress(self, current: int, total: int, label: str = "Batch") -> None:
        maximum = max(total, 1)
        _, progress_maximum = self._splitter_defaults.progress_range
        percent = int((current / maximum) * progress_maximum)
        self.export_overall_progress_bar.setValue(max(0, min(percent, progress_maximum)))
        self.export_overall_progress_bar.setFormat(f"{label}: {current}/{total}")

    def set_close_request_handler(self, handler: Callable[[], bool]) -> None:
        self._close_request_handler = handler

    def set_tracking_config_warning_visible(self, visible: bool) -> None:
        self.right_panel.set_tracking_config_warning_visible(visible)

    def set_iou_widgets_visible(self, visible: bool) -> None:
        self.right_panel.set_iou_widgets_visible(visible)

    def set_blur_strength_visible(self, visible: bool) -> None:
        self.right_panel.set_blur_strength_visible(visible)

    def set_detection_loading_state(self, is_loading: bool, model_name: str | None = None) -> None:
        self.right_panel.set_detection_loading_state(is_loading)
        if is_loading and model_name:
            self.set_status_text(f"Loading model: {model_name}")

    def set_tracking_loading_state(self, is_loading: bool) -> None:
        self.right_panel.set_tracking_loading_state(is_loading)

    def set_detection_progress_busy(self, is_busy: bool) -> None:
        self.right_panel.set_detection_progress_busy(is_busy)

    def set_detection_progress(self, current: int, total: int, label: str = "Detection", eta_msecs: float | None = None) -> None:
        self.right_panel.set_detection_progress(current, total, label, eta_msecs)

    def set_tracking_progress_busy(self, is_busy: bool, indeterminate: bool = False) -> None:
        self.right_panel.set_tracking_progress_busy(is_busy, indeterminate)

    def set_tracking_progress(self, current: int, total: int, label: str = "Tracking") -> None:
        self.right_panel.set_tracking_progress(current, total, label)

    def set_detection_model_boxes(self, boxes: list[ModelSelectionViewModel]) -> None:
        self.right_panel.set_detection_model_boxes(boxes)

    def set_selected_detection_model(self, model_id: str) -> None:
        self.right_panel.set_selected_detection_model(model_id)

    def set_frame_label_text(self, text: str) -> None:
        self.transport_panel.set_frame_label_text(text)

    def set_status_text(self, text: str) -> None:
        self.info_label.setText(text)

    def show_info(self, title: str, msg: str) -> None:
        QMessageBox.information(self, title, msg)

    def show_warning(self, title: str, msg: str) -> None:
        QMessageBox.warning(self, title, msg)

    def show_error(self, title: str, msg: str) -> None:
        QMessageBox.critical(self, title, msg)

    def restore_session_settings(self, vm: SessionSettingsViewModel) -> None:
        self.right_panel.restore_session_settings(vm)

    def _build_status_bar(self) -> None:
        status = QStatusBar()
        status.addPermanentWidget(self.info_label, 1)
        status.addPermanentWidget(self.export_progress_bar)
        status.addPermanentWidget(self.export_overall_progress_bar)
        self.setStatusBar(status)

    def _build_toolbar(self) -> None:
        toolbar = QToolBar("Main")
        toolbar.addAction(self.top_row.open_action)
        toolbar.addSeparator()
        toolbar.addWidget(self.add_mode_btn)
        toolbar.addWidget(self.edit_mode_btn)
        toolbar.addWidget(self.delete_mode_btn)
        toolbar.addSeparator()
        toolbar.addAction(self.top_row.export_all_action)
        self.addToolBar(toolbar)

    def _build_ui(self) -> None:
        central = QWidget()
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(6, 6, 6, 6)
        root_layout.setSpacing(6)
        root_layout.addWidget(self._build_top_row_host())
        root_layout.addWidget(self._build_main_splitter(), 1)
        self.setCentralWidget(central)

    def _build_top_row_host(self) -> QWidget:
        host = QWidget(self)
        host.setLayout(self.top_row.as_layout())
        return host

    def _build_main_splitter(self) -> QSplitter:
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(self._splitter_defaults.handle_width)
        splitter.addWidget(self._build_left_splitter())
        splitter.addWidget(self.right_panel)
        left_stretch, right_stretch = self._splitter_defaults.main_stretch
        splitter.setStretchFactor(0, left_stretch)
        splitter.setStretchFactor(1, right_stretch)
        splitter.setCollapsible(0, False)
        splitter.setCollapsible(1, True)
        splitter.setSizes(list(self._splitter_defaults.main_sizes))
        return splitter

    def _build_left_splitter(self) -> QSplitter:
        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setHandleWidth(self._splitter_defaults.handle_width)
        splitter.addWidget(self._build_preview_stack())
        splitter.addWidget(self.bottom_panel)
        top_stretch, bottom_stretch = self._splitter_defaults.left_stretch
        splitter.setStretchFactor(0, top_stretch)
        splitter.setStretchFactor(1, bottom_stretch)
        splitter.setCollapsible(0, False)
        splitter.setCollapsible(1, True)
        splitter.setSizes(list(self._splitter_defaults.left_sizes))
        return splitter

    def _build_preview_stack(self) -> QWidget:
        container = QWidget(self)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(self.preview_container, 1)
        layout.addLayout(self.transport_panel)
        return container

    def _connect_signals(self) -> None:
        logger.debug("Connecting modular UI signals...")
        self.tool_group.idClicked.connect(self._emit_tool_mode_changed)
        self.bottom_panel.tab_changed.connect(self._on_tab_changed)
        self.bottom_panel.session_selected.connect(self.session_selected.emit)
        self.top_row.open_btn.clicked.connect(self.open_file_requested.emit)
        self.top_row.open_action.triggered.connect(self.open_file_requested.emit)
        logger.debug("Modular UI signals connected.")

    def _reset_export_progress_bar(self) -> None:
        self.export_progress_bar.setValue(0)
        self.export_progress_bar.setFormat("Exporting: 0/0")

    def _reset_export_overall_progress_bar(self) -> None:
        self.export_overall_progress_bar.setValue(0)
        self.export_overall_progress_bar.setFormat("Batch: 0/0")

    @Slot(int)
    def _on_tab_changed(self, index: int) -> None:
        self.preview_container.set_tracker_actions_enabled(VideoDataLayerGroup(index) == VideoDataLayerGroup.TRACKING)

    @Slot(int)
    def _emit_tool_mode_changed(self, mode: int) -> None:
        self.tool_mode_changed.emit(ToolMode(mode))
