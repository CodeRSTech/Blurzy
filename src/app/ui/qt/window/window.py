"""
Module for window; implements the Qt presentation components.

See Also:
    - [`UIController`][app.ui.uicontroller.UIController] — coordinates application behavior for the window
    - [`RightControlPanel`][app.ui.qt.sections.right_panel.RightControlPanel] — provides the main control area

Layer: Presentation.
Context: Implements the qt presentation components at this architectural boundary.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from typing import final, override

from PySide6 import QtWidgets
from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QAction

from app.domain import VideoDataLayerGroup
from app.shared.logging_cfg import get_logger
from app.ui.qt import sections
from app.ui.qt.shared.layout_shortcuts import create_vbox_layout
from app.ui.qt.shared.widget_factories import create_progress_bar
from app.ui.qt.window.splitter_defaults import _WindowSplitterDefaults
from app.ui.view_state.preview_state import ToolMode
from app.ui.view_state.bbox_selection_state import BBoxSelectionState
from app.ui.view_state.selection_history_state import SelectionHistoryState
if TYPE_CHECKING:
    from collections.abc import Callable, Iterable
    from PySide6.QtGui import QCloseEvent
    from app.domain import SessionId, ModelSelectionViewModel, SessionSettingsViewModel


logger = get_logger("UI->MainWindow")


def _reset_qt_progress_bar(progress_bar: QtWidgets.QProgressBar, label: str) -> None:
    progress_bar.setValue(0)
    progress_bar.setFormat(f"{label}: 0/0")


@final
class Window(QtWidgets.QMainWindow):
    """
    Alternative window shell that preserves the current UI API while using a cleaner layout assembly.

    Layer: Presentation.
    Context: Supports user interaction and delegates application work through presentation contracts.
    """

    open_videos_requested = Signal(list)
    tool_mode_changed = Signal(ToolMode)
    session_selected = Signal(object)

    def __init__(self) -> None:
        logger.info("Initializing modular UI window...")
        super().__init__()

        self._splitter_defaults = _WindowSplitterDefaults()
        self._close_request_handler: Callable[[], bool] | None = None
        self._bbox_selection_state = BBoxSelectionState()
        self._selection_history_state = SelectionHistoryState()
        self._base_window_title = ""
        self._current_project_path = ""

        self.setWindowTitle(self._base_window_title)
        self.resize(1300, 850)

        self._init_sections()
        self._init_menu_actions()
        self._build_menu_bar()
        self._build_ui()
        self._build_status_bar()
        self._connect_signals()

        logger.info("Modular UI window initialized.")

    @override
    def __repr__(self) -> str:
        return "Window()"

    @override
    def __str__(self) -> str:
        return f"Window [{self.size().width()}x{self.size().height()}]"

    def _build_status_bar(self) -> None:
        status = QtWidgets.QStatusBar()
        status.addPermanentWidget(self.info_label, 1)
        status.addPermanentWidget(self.export_progress_bar)
        status.addPermanentWidget(self.export_overall_progress_bar)
        self.setStatusBar(status)

    def _build_menu_bar(self) -> None:
        """
        Build a real top menu bar hosted in the window's custom top bar.
        """
        menu_bar = QtWidgets.QMenuBar(self)
        # Keep menu rendering inside the window consistently across platforms.
        menu_bar.setNativeMenuBar(False)

        file_menu = menu_bar.addMenu("&File")
        file_menu.addAction(self.new_project_action)
        file_menu.addAction(self.open_project_action)
        file_menu.addAction(self.save_project_action)
        file_menu.addAction(self.save_project_as_action)
        file_menu.addSeparator()
        file_menu.addAction(self.open_videos_action)
        file_menu.addSeparator()
        file_menu.addAction(self.right_panel.export_all_action)

        edit_menu = menu_bar.addMenu("&Edit")
        edit_menu.addAction(self.preferences_action)
        edit_menu.addSeparator()
        reset_trackers_menu = edit_menu.addMenu("Reset Trackers")
        reset_trackers_menu.addAction(self.reset_trackers_current_frame_action)
        reset_trackers_menu.addAction(self.reset_trackers_all_frames_action)

        reset_detections_menu = edit_menu.addMenu("Reset Detections")
        reset_detections_menu.addAction(self.reset_detections_current_frame_action)
        reset_detections_menu.addAction(self.reset_detections_all_frames_action)

        # Register actions on the window so shortcuts remain active.
        self._register_window_actions(
            (
                self.open_videos_action,
                self.new_project_action,
                self.open_project_action,
                self.save_project_action,
                self.save_project_as_action,
                self.preferences_action,
                self.right_panel.export_all_action,
                self.reset_trackers_current_frame_action,
                self.reset_trackers_all_frames_action,
                self.reset_detections_current_frame_action,
                self.reset_detections_all_frames_action,
            )
        )

        top_bar = QtWidgets.QWidget(self)
        top_bar_layout = create_vbox_layout(top_bar, margins=(10, 6, 10, 6), spacing=0)
        menu_row = QtWidgets.QHBoxLayout()
        menu_row.setContentsMargins(0, 0, 0, 0)
        menu_row.setSpacing(8)
        menu_row.addWidget(menu_bar)
        menu_row.addStretch(1)
        menu_row.addWidget(self.project_label)
        top_bar_layout.addLayout(menu_row)

        self.setMenuWidget(top_bar)

    def _build_ui(self) -> None:
        central = QtWidgets.QWidget()
        central.setObjectName("centralWidget")
        root_layout = create_vbox_layout(central, margins=(8, 8, 8, 8), spacing=8)

        root_layout.addWidget(self._build_main_splitter(), 1)
        self.setCentralWidget(central)

    def _build_splitter(self, orientation: Qt.Orientation, widgets: list[QtWidgets.QWidget], stretch_factors: list[int],
                        sizes: list[int]) -> QtWidgets.QSplitter:
        splitter = QtWidgets.QSplitter(orientation)
        splitter.setHandleWidth(self._splitter_defaults.handle_width)
        for widget in widgets:
            splitter.addWidget(widget)
        for index, stretch in enumerate(stretch_factors):
            splitter.setStretchFactor(index, stretch)
        splitter.setSizes(sizes)
        return splitter

    def _build_main_splitter(self) -> QtWidgets.QSplitter:
        """
        Build the main horizontal splitter with left and right panels.
        """
        splitter = self._build_splitter(Qt.Orientation.Horizontal,
                                        [self._build_left_splitter(), self.right_panel],
                                        list(self._splitter_defaults.main_stretch),
                                        list(self._splitter_defaults.main_sizes))
        return splitter

    def _build_left_splitter(self) -> QtWidgets.QSplitter:
        """
        Build the left vertical splitter with preview and bottom panels.
        """
        splitter = self._build_splitter(Qt.Orientation.Vertical,
                                        [self._build_preview_stack(), self.bottom_panel],
                                        list(self._splitter_defaults.left_stretch),
                                        list(self._splitter_defaults.left_sizes))
        return splitter

    def _build_preview_stack(self) -> QtWidgets.QWidget:
        container = QtWidgets.QWidget(self)
        layout = create_vbox_layout(container, margins=(0, 0, 0, 0), spacing=6)
        layout.addWidget(self.preview_container, 1)
        layout.addLayout(self.transport_panel)
        return container

    def _connect_signals(self) -> None:
        logger.debug("Connecting modular UI signals...")
        self.transport_panel.tool_group.idClicked.connect(self._emit_tool_mode_changed)
        self.bottom_panel.tab_changed.connect(self._on_tab_changed)
        self.bottom_panel.session_selected.connect(self.session_selected.emit)
        self.open_videos_action.triggered.connect(self._choose_video_files)
        self.preview_container.open_video_requested.connect(self._choose_video_files)
        self.preview_container.viewport_state_changed.connect(self.transport_panel.set_viewport_state)
        # Route menu reset actions through the existing reset buttons to preserve handler connections.
        self._connect_reset_actions()
        logger.debug("Modular UI signals connected.")

    def _init_sections(self) -> None:
        self.preview_container = sections.PreviewContainer(self)
        self.right_panel = sections.RightControlPanel(self)
        self.bottom_panel = sections.BottomDataPanelContainer(self)
        self.transport_panel = sections.TransportControlsPanel(self)

        self.right_panel.setMinimumWidth(0)
        self.bottom_panel.setMinimumHeight(0)

        self.info_label = QtWidgets.QLabel("No session loaded")
        self.info_label.setObjectName("mutedText")
        self.project_label = QtWidgets.QLabel("Project: none")
        self.project_label.setObjectName("mutedText")
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

    def _init_menu_actions(self) -> None:
        """
        Initialize top-level menu actions once so handlers can reuse stable action objects.
        """
        self.open_videos_action = QAction("Open Videos...", self)
        self.open_videos_action.setShortcut("Ctrl+O")
        self.open_videos_action.setStatusTip("Open one or more video files")

        self.new_project_action = QAction("New Project", self)
        self.new_project_action.setShortcut("Ctrl+N")
        self.new_project_action.setStatusTip("Close current project and start a new one")

        self.open_project_action = QAction("Open Project...", self)
        self.open_project_action.setShortcut("Ctrl+Shift+O")
        self.open_project_action.setStatusTip("Open a saved project file")

        self.save_project_action = QAction("Save Project", self)
        self.save_project_action.setShortcut("Ctrl+S")
        self.save_project_action.setStatusTip("Save the current project")

        self.save_project_as_action = QAction("Save Project As...", self)
        self.save_project_as_action.setShortcut("Ctrl+Shift+S")
        self.save_project_as_action.setStatusTip("Save the current project to a new file")

        self.preferences_action = QAction("Settings...", self)
        self.preferences_action.setShortcut("Ctrl+,")
        self.preferences_action.setStatusTip("Edit persistent app settings and defaults")

        self.reset_trackers_current_frame_action = QAction("Reset at current frame", self)
        self.reset_trackers_all_frames_action = QAction("Reset for all frames", self)
        self.reset_detections_current_frame_action = QAction("Reset at current frame", self)
        self.reset_detections_all_frames_action = QAction("Reset for all frames", self)

    def _register_window_actions(self, actions: Iterable[QAction]) -> None:
        for action in actions:
            self.addAction(action)

    def _connect_reset_actions(self) -> None:
        self.reset_trackers_current_frame_action.triggered.connect(self.bottom_panel.reset_tracker_frame_btn.click)
        self.reset_trackers_all_frames_action.triggered.connect(self.bottom_panel.reset_all_trackers_btn.click)
        self.reset_detections_current_frame_action.triggered.connect(self.bottom_panel.reset_frame_btn.click)
        self.reset_detections_all_frames_action.triggered.connect(self.bottom_panel.reset_all_btn.click)

    def _set_fraction_progress(
            self,
            progress_bar: QtWidgets.QProgressBar,
            current: int,
            total: int,
            label: str,
    ) -> None:
        maximum = max(total, 1)
        _, progress_maximum = self._splitter_defaults.progress_range
        percent = int((current / maximum) * progress_maximum)
        progress_bar.setValue(max(0, min(percent, progress_maximum)))
        progress_bar.setFormat(f"{label}: {current}/{total}")

    def _set_export_controls_enabled(self, enabled: bool) -> None:
        self.right_panel.export_btn.setEnabled(enabled)
        self.right_panel.export_all_btn.setEnabled(enabled)
        self.right_panel.export_all_action.setEnabled(enabled)

    def _reset_export_progress_bar(self) -> None:
        _reset_qt_progress_bar(self.export_progress_bar, "Exporting")

    def _reset_export_overall_progress_bar(self) -> None:
        _reset_qt_progress_bar(self.export_overall_progress_bar, "Batch")

    # ================================================
    # SLOTS
    # ================================================

    @Slot()
    def _choose_video_files(self) -> None:
        """
        Open a file chooser and emit selected paths for SessionHandler.
        """
        paths, _ = QtWidgets.QFileDialog.getOpenFileNames(
            self,
            "Open Video Files",
            "",
            "Video Files (*.mp4 *.avi *.mov *.mkv *.wmv *.m4v);;All Files (*)",
        )
        if paths:
            self.open_videos_requested.emit(paths)

    @Slot(int)
    def _on_tab_changed(self, index: int) -> None:
        self.preview_container.set_tracker_actions_enabled(VideoDataLayerGroup(index) == VideoDataLayerGroup.TRACKING)

    @Slot(int)
    def _emit_tool_mode_changed(self, mode: int) -> None:
        self.tool_mode_changed.emit(ToolMode(mode))

    # ========
    # PROPERTIES
    # =========

    @property
    def bbox_selection_state(self) -> BBoxSelectionState:
        """
        Return the current bbox selection state.

        Returns:
            Shared preview-selection state containing the selected bounding-box keys.
        """
        return self._bbox_selection_state

    @property
    def selection_history_state(self) -> SelectionHistoryState:
        """
        Return selection history and clipboard state.

        Returns:
            State object containing selection undo/redo history and copied boxes.
        """
        return self._selection_history_state

    @property
    def active_tab_index(self) -> VideoDataLayerGroup:
        """
        Return the index of the active data tab.

        Returns:
            Active tab as a `VideoDataLayerGroup` enum.
        """
        return VideoDataLayerGroup(self.bottom_panel.active_tab_index)

    @property
    def selected_s_id(self) -> SessionId:
        """
        Return the selected session identifier.

        Returns:
            Identifier of the session selected in the bottom panel.
        """
        return self.bottom_panel.selected_s_id

    @property
    def selected_frame_box_keys(self) -> list[str]:
        """
        Return keys of boxes selected on the current frame.

        Returns:
            Keys in the shared bounding-box selection state.
        """
        return self.bbox_selection_state.get_selected_keys()

    # ========
    # PUBLIC METHODS
    # =========

    @override
    def closeEvent(self, event: QCloseEvent) -> None:
        """
        Handle window close and any pending-export confirmation.

        Args:
            event: Close event to accept unless the registered handler rejects it.
        """
        if self._close_request_handler is not None and not self._close_request_handler():
            event.ignore()
            return
        super().closeEvent(event)

    def confirm_export_in_progress_exit(self) -> bool:
        """
        Ask whether to exit while an export is running.

        Returns:
            `True` when the user chooses Yes.
        """
        result = QtWidgets.QMessageBox.question(
            self,
            "Export in Progress",
            "An export is currently in progress. Exit anyway?",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
            QtWidgets.QMessageBox.StandardButton.No,
        )
        return result == QtWidgets.QMessageBox.StandardButton.Yes

    def set_export_enabled(self, enabled: bool) -> None:
        """
        Enable or disable the single-session export button.

        Args:
            enabled: Whether the export button should be enabled.
        """
        self.right_panel.export_btn.setEnabled(enabled)

    def set_export_busy(self, is_busy: bool, status_text: str | None = None) -> None:
        """
        Update single-session export controls and progress visibility.

        Args:
            is_busy: Whether an export is currently in progress.
            status_text: Optional status-bar text to display.
        """
        self._set_export_controls_enabled(not is_busy)
        self.export_progress_bar.setVisible(is_busy)
        self._reset_export_progress_bar()
        if not is_busy:
            self.export_overall_progress_bar.setVisible(False)
            self._reset_export_overall_progress_bar()
        if status_text is not None:
            self.set_status_text(status_text)

    def set_export_progress(self, current: int, total: int, label: str = "Exporting") -> None:
        """
        Display progress for the current export.

        Args:
            current: Number of completed units.
            total: Total number of units.
            label: Text prefix shown beside the progress fraction.
        """
        self._set_fraction_progress(self.export_progress_bar, current, total, label)

    def set_export_progress_status(self, label: str) -> None:
        """
        Set the export progress-bar label and reset its value.

        Args:
            label: Status text to show in the progress bar.
        """
        self.export_progress_bar.setValue(0)
        self.export_progress_bar.setFormat(label)

    def set_export_overall_busy(self, is_busy: bool) -> None:
        """
        Show or hide the all-session export progress bar and reset it.

        Args:
            is_busy: Whether an all-session export is in progress.
        """
        self.export_overall_progress_bar.setVisible(is_busy)
        self._reset_export_overall_progress_bar()

    def set_export_overall_progress(self, current: int, total: int, label: str = "Batch") -> None:
        """
        Display overall progress for a batch export.

        Args:
            current: Number of completed sessions or units.
            total: Total number of sessions or units.
            label: Text prefix shown beside the progress fraction.
        """
        self._set_fraction_progress(self.export_overall_progress_bar, current, total, label)

    def set_close_request_handler(self, handler: Callable[[], bool]) -> None:
        """
        Register a callback that decides whether the window may close.

        Args:
            handler: Callback returning `True` to allow close, or `False` to cancel it.
        """
        self._close_request_handler = handler

    def set_tracking_config_warning_visible(self, visible: bool) -> None:
        """
        Show or hide the tracking-configuration warning.

        Args:
            visible: Whether the warning should be visible.
        """
        self.right_panel.set_tracking_config_warning_visible(visible)

    def set_iou_widgets_visible(self, visible: bool) -> None:
        """
        Show or hide the IoU threshold controls.

        Args:
            visible: Whether the controls should be visible.
        """
        self.right_panel.set_iou_widgets_visible(visible)

    def set_blur_strength_visible(self, visible: bool) -> None:
        """
        Show or hide the export blur-strength control.

        Args:
            visible: Whether the control should be visible.
        """
        self.right_panel.set_blur_strength_visible(visible)

    def set_detection_loading_state(self, is_loading: bool, model_name: str | None = None) -> None:
        """
        Update detection-loading controls and optionally show the model name.

        Args:
            is_loading: Whether a detection model is loading.
            model_name: Name of the model being loaded, when available.
        """
        self.right_panel.set_detection_loading_state(is_loading)
        if is_loading and model_name:
            self.set_status_text(f"Loading model: {model_name}")

    def set_tracking_loading_state(self, is_loading: bool) -> None:
        """
        Enable or disable controls affected by tracker loading.

        Args:
            is_loading: Whether a tracking model is loading.
        """
        self.right_panel.set_tracking_loading_state(is_loading)

    def set_detection_progress_busy(self, is_busy: bool) -> None:
        """
        Set the detection-progress bar's busy state.

        Args:
            is_busy: Whether detection is active.
        """
        self.right_panel.set_detection_progress_busy(is_busy)

    def set_detection_progress(self, current: int, total: int, label: str = "Detection",
                               eta_msecs: float | None = None) -> None:
        """
        Set detection progress.

        Args:
            current: Number of frames processed.
            total: Total number of frames to process.
            label: Text prefix shown beside the progress fraction.
            eta_msecs: Estimated remaining time in milliseconds, if known.
        """
        self.right_panel.set_detection_progress(current, total, label, eta_msecs)

    def set_tracking_progress_busy(self, is_busy: bool, indeterminate: bool = False) -> None:
        """
        Set the tracking-progress bar's visibility and indeterminate mode.

        Args:
            is_busy: Whether tracking is active.
            indeterminate: Whether to show progress without a numeric range.
        """
        self.right_panel.set_tracking_progress_busy(is_busy, indeterminate)

    def set_tracking_progress(self, current: int, total: int, label: str = "Tracking") -> None:
        """
        Display tracking progress.

        Args:
            current: Number of frames processed.
            total: Total number of frames to process.
            label: Text prefix shown beside the progress fraction.
        """
        self.right_panel.set_tracking_progress(current, total, label)

    def set_detection_model_boxes(self, boxes: list[ModelSelectionViewModel]) -> None:
        """
        Populate the detection-model selector.

        Args:
            boxes: Model choices to display in the selector.
        """
        self.right_panel.set_detection_model_boxes(boxes)

    def set_selected_detection_model(self, model_id: str) -> None:
        """
        Select a detection model in the right panel.

        Args:
            model_id: Identifier of the model to select.
        """
        self.right_panel.set_selected_detection_model(model_id)

    def set_frame_label_text(self, text: str) -> None:
        """
        Set the transport panel's frame label.

        Args:
            text: Formatted frame information to display.
        """
        self.transport_panel.set_frame_label_text(text)

    def set_status_text(self, text: str) -> None:
        """
        Set the status-bar message.

        Args:
            text: Message to display in the window's status label.
        """
        self.info_label.setText(text)

    def set_current_project_path(self, project_path: str) -> None:
        """
        Update the project label, tooltip, and window title for the active project.

        Args:
            project_path: Project file path, or an empty string when no project is active.
        """
        self._current_project_path = project_path
        if project_path:
            project_name = os.path.basename(project_path)
            self.project_label.setText(f"Project: {project_name}")
            self.project_label.setToolTip(project_path)
            self.setWindowTitle(f"{self._base_window_title} — {project_name}")
            return
        self.project_label.setText("Project: none")
        self.project_label.setToolTip("")
        self.setWindowTitle(self._base_window_title)

    def show_info(self, title: str, msg: str) -> None:
        """
        Show an informational message dialog.

        Args:
            title: Dialog title.
            msg: Informational message.
        """
        QtWidgets.QMessageBox.information(self, title, msg)

    def show_warning(self, title: str, msg: str) -> None:
        """
        Show a warning message dialog.

        Args:
            title: Dialog title.
            msg: Warning message.
        """
        QtWidgets.QMessageBox.warning(self, title, msg)

    def show_error(self, title: str, msg: str) -> None:
        """
        Show an error message dialog.

        Args:
            title: Dialog title.
            msg: Error message.
        """
        QtWidgets.QMessageBox.critical(self, title, msg)

    def restore_session_settings(self, vm: SessionSettingsViewModel) -> None:
        """
        Restore session settings in the window controls.

        Args:
            vm: Settings values to apply to the controls.
        """
        self.right_panel.restore_session_settings(vm)
