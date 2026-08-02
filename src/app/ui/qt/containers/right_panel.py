from typing import final, cast, TYPE_CHECKING

from PySide6.QtCore import Signal, QSignalBlocker, Slot
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.domain.tracking.tracking_strategy import TrackingStrategy
from app.domain.video.layer import VideoDataLayer
from app.ui.qt.utilities.helpers import create_qhbox_with_widgets, create_progress_bar, create_spinbox
from app.ui.qt.utilities.spinner_label import InlineSpinnerLabel
from app.ui.qt.widgets.collapsible_widget import CollapsibleBox

if TYPE_CHECKING:
    from app.ui.handlers import ExportHandler
    from app.domain.views import SessionSettingsViewModel, ModelSelectionViewModel


@final
class RightControlPanel(QScrollArea):
    """Encapsulates the Detection, Tracking, and Render controls."""

    # --- Signals ---
    # PySide Rule: Signals must be declared at the class level.
    chosen_labels_changed = Signal(str)
    model_changed = Signal(str)
    tracking_strategy_changed = Signal(str)
    tracking_source_changed = Signal(str)
    start_tracking_requested = Signal(str, str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setMinimumWidth(280)

        # Container to hold everything inside the scroll area
        self._container = QWidget()
        self._layout = QVBoxLayout(self._container)
        self._layout.setContentsMargins(5, 5, 5, 5)
        self._layout.setSpacing(10)
        # All widgets are strictly instantiated as instance attributes here.
        self._init_widgets()
        self._build_ui()
        self._connect_signals()

        self.setWidget(self._container)

    def _init_widgets(self) -> None:
        # --- Detection Widgets ---

        ############################################################################################################
        #   v Detection                                                                                            #
        ############################################################################################################
        self.detection_box = CollapsibleBox("Detection")
        #
        #               +----------------------------------------------------+
        #   Model:      | YOLOv26X                                     [ v ] |
        #               +----------------------------------------------------+
        self.model_combo_box = QComboBox()
        self.model_loading_spinner = InlineSpinnerLabel("Loading model")
        self.model_selection = create_qhbox_with_widgets(
            [QLabel("Model:"), self.model_combo_box, self.model_loading_spinner]
        )
        #
        #               +----------------------------------------------------+
        #   Min Conf:   | 0.5                                      [ ^ | v ] |
        #               +----------------------------------------------------+
        self.min_confidence_spinbox = create_spinbox(min_val=0.0, max_val=1.0, step=0.05, default=0.5)
        self.min_confidence_selection = create_qhbox_with_widgets(
            [QLabel("Min Conf:"), self.min_confidence_spinbox]
        )
        #
        #               +----------------------------------------------------+
        #   Labels:     | person, cat, dog                              [I]  |
        #               +----------------------------------------------------+
        self.chosen_labels_edit = QLineEdit()
        self.chosen_labels_edit.setPlaceholderText("person, cat, dog")
        self.labels_selection = create_qhbox_with_widgets([QLabel("Labels:"), self.chosen_labels_edit])
        #
        #   [====================================================]
        #   [               Detect Current Frame                 ]
        #   [====================================================]
        self.detect_btn = QPushButton("Detect Current Frame")
        #
        #   [====================================================]
        #   [             Start Background Detection             ]
        #   [====================================================]
        self.detect_all_btn = QPushButton("Start Background Detection")
        #
        #   [====================================================]
        #   [                   Import / Export                  ]
        #   [====================================================]
        #
        #   [NEW] Import / Export detections button
        #   Intended functionality:
        #   First, a dialog asks whether to import or export detections.
        #   There are options for choosing whether to import or export and,
        #   Which layer to target (A/B)
        #       Case 1.:
        #           - User chooses import
        #           - a open file dialog opens to select a .json / .csv file to import
        #           - The imported detections are then added to the selected layer (A/B)
        #           [NOTE] A warning dialog must tell the users that any existing data will be overwritten
        #       Case 2.:
        #           - User chooses export
        #           - a save file dialog opens to select a .json / .csv file to export
        #           - The detections from the selected layer (A/B) are then exported to the selected file

        self.imp_exp_detections_button = QPushButton("Import / Export")
        self.detection_progress_bar = create_progress_bar(0, 100, text_visible=True, visible=False)

        # --- Tracking Widgets ---

        ############################################################################################################
        #   v Tracking                                                                                             #
        ############################################################################################################
        self.tracking_box = CollapsibleBox("Tracking")
        self.tracking_config_warning_label = QLabel("⚠️ Settings changed. Re-run tracking.")
        #
        #               +----------------------------------------------------+
        #   Source:     | Raw Detections                               [ v ] |
        #               +----------------------------------------------------+
        self.tracking_source_combo_box = QComboBox()
        for name, value in [("Raw Detections", VideoDataLayer.A), ("Reviewed Detections", VideoDataLayer.B)]:
            self.tracking_source_combo_box.addItem(name, value)
        self.source_selection = create_qhbox_with_widgets(
            [QLabel("Source:"), self.tracking_source_combo_box]
        )
        #
        #               +----------------------------------------------------+
        #   Strategy:   | Dummy Tracker (Copy)                         [ v ] |
        #               +----------------------------------------------------+
        self.tracking_strategy_combo_box = QComboBox()
        for name, value in [
            ("Dummy Tracker (Copy)", TrackingStrategy.DUMMY),
            ("Hungarian IoU (Fast)", TrackingStrategy.HUNGARIAN),
            ("ByteTrack (High Perf)", TrackingStrategy.BYTRACK),
            ("DeepSORT", TrackingStrategy.DEEP_SORT),
            ("CSRT (Manual/Slow)", TrackingStrategy.CSRT),
        ]:
            self.tracking_strategy_combo_box.addItem(name, value)
            self.tracking_strategy_combo_box.setCurrentIndex(1)
        self.strategy_selection = create_qhbox_with_widgets(
            [QLabel("Strategy:"), self.tracking_strategy_combo_box]
        )
        #
        #               +----------------------------------------------------+
        #   Min IoU:    | 0.35                                     [ ^ | v ] |
        #               +----------------------------------------------------+
        self.min_iou_label = QLabel("Min IoU:")
        self.min_iou_spinbox = create_spinbox(min_val=0.0, max_val=1.0, step=0.05, default=0.35)
        self.min_iou_selection = create_qhbox_with_widgets([self.min_iou_label, self.min_iou_spinbox])
        #
        #               +----------------------------------------------------+
        #   Min Conf:   | 0.40                                     [ ^ | v ] |
        #               +----------------------------------------------------+
        self.min_tracker_confidence_spinbox = create_spinbox(
            min_val=0.0, max_val=1.0, step=0.05, default=0.4
        )
        self.min_tracker_conf_selection = create_qhbox_with_widgets(
            [QLabel("Min Conf:"), self.min_tracker_confidence_spinbox]
        )
        #
        #               +----------------------------------------------------+
        #   Decay:      | 0.05                                     [ ^ | v ] |
        #               +----------------------------------------------------+
        self.confidence_decay_spinbox = create_spinbox(min_val=0.0, max_val=1.0, step=0.01, default=0.05)
        self.decay_selection = create_qhbox_with_widgets([QLabel("Decay:"), self.confidence_decay_spinbox])
        #
        #   [====================================================]
        #   [                   Start Tracking                   ]
        #   [====================================================]
        self.track_btn = QPushButton("Start Tracking")        #
        #   [====================================================]
        #   [                   Import / Export                  ]
        #   [====================================================]
        #
        #   [NEW] Import / Export trackers button
        #   Intended functionality:
        #   First, a dialog asks whether to import or export trackers.
        #   There are options for choosing whether to import or export and,
        #   Which layer to target (C/D)
        #       Case 1.:
        #           - User chooses import
        #           - a open file dialog opens to select a .json / .csv file to import
        #           - The imported trackers are then added to the selected layer (C/D)
        #           [NOTE] A warning dialog must tell the users that any existing data will be overwritten
        #       Case 2.:
        #           - User chooses export
        #           - a save file dialog opens to select a .json / .csv file to export
        #           - The trackers from the selected layer (C/D) are then exported to the selected file

        self.imp_exp_tracks_button = QPushButton("Import / Export")
        self.tracking_progress_bar = create_progress_bar(0, 0, text_visible=True, visible=False)
        # --- Render Widgets ---

        ############################################################################################################
        #   v Preview_Render                                                                                       #
        ############################################################################################################
        self.render_box = CollapsibleBox("Preview_Render")
        #
        #   [ ] Draw bounding boxes
        #
        self.draw_boxes_checkbox = QCheckBox("Draw bounding boxes")
        #
        #   [ ] Blur bounding boxes
        #
        self.blur_checkbox = QCheckBox("Blur bounding boxes")
        #
        #   (Hidden by default)
        #               +----------------------------------------------------+
        # Blur strength:| 5.0                                      [ ^ | v ] |
        #               +----------------------------------------------------+
        self.blur_strength_label = QLabel("Blur strength:")
        self.blur_strength_spinbox = create_spinbox(0.0, 10.0, 1.0, 5.0)
        self.blur_strength_selection = create_qhbox_with_widgets(
            [self.blur_strength_label, self.blur_strength_spinbox]
        )
        #
        #   [====================================================]
        #   [                    Export Video                    ]
        #   [====================================================]
        self.export_btn = QPushButton("Export Video")
        self.export_all_btn = QPushButton("Export All")
        self.export_all_action = QAction("Export All...", self)

    def _build_ui(self) -> None:
        self.detection_box.add_layout(self.model_selection)
        self.detection_box.add_layout(self.min_confidence_selection)
        self.detection_box.add_layout(self.labels_selection)

        self.detection_box.add_widget(self.detect_btn)
        self.detection_box.add_widget(self.detect_all_btn)
        self.detection_box.add_widget(self.imp_exp_detections_button)
        self._reset_detection_progress_bar()
        self.detection_box.add_widget(self.detection_progress_bar)

        self.tracking_box.add_layout(self.source_selection)
        self.tracking_box.add_layout(self.strategy_selection)
        self.tracking_box.add_layout(self.min_iou_selection)
        self.tracking_box.add_layout(self.min_tracker_conf_selection)
        self.tracking_box.add_layout(self.decay_selection)
        self.tracking_box.add_widget(self.track_btn)
        self.tracking_box.add_widget(self.imp_exp_tracks_button)
        self._reset_tracking_progress_bar()
        self.tracking_box.add_widget(self.tracking_progress_bar)

        self.tracking_config_warning_label.setStyleSheet("color: #d9534f; font-weight: bold;")
        self.tracking_config_warning_label.setVisible(False)
        self.tracking_config_warning_label.setWordWrap(True)
        self.tracking_box.add_widget(self.tracking_config_warning_label)

        self.blur_strength_spinbox.setVisible(False)
        self.blur_strength_label.setVisible(False)

        self.render_box.add_widget(self.draw_boxes_checkbox)
        self.render_box.add_widget(self.blur_checkbox)
        self.render_box.add_layout(self.blur_strength_selection)
        self.render_box.add_widget(self.export_btn)
        self.render_box.add_widget(self.export_all_btn)

        # --- Final Assembly ---
        self._layout.addWidget(self.detection_box)
        self._layout.addWidget(self.tracking_box)
        self._layout.addWidget(self.render_box)
        self._layout.addStretch()

    def _connect_signals(self) -> None:
        # Detection Panel
        self.model_combo_box.currentIndexChanged.connect(self._emit_model_changed)
        self.chosen_labels_edit.editingFinished.connect(self._emit_chosen_labels_changed)

        # Tracking Panel
        self.track_btn.clicked.connect(self._emit_start_tracking)
        self.tracking_strategy_combo_box.currentIndexChanged.connect(self._emit_tracking_strategy_changed)
        self.tracking_source_combo_box.currentIndexChanged.connect(self._emit_tracking_source_changed)

    @Slot()
    def _emit_chosen_labels_changed(self) -> None:
        self.chosen_labels_changed.emit(self.chosen_labels_edit.text())

    @Slot()
    def _emit_model_changed(self) -> None:
        model_id: str = cast(str, self.model_combo_box.currentData())
        self.model_changed.emit(model_id)

    @Slot()
    def _emit_tracking_strategy_changed(self) -> None:
        strategy_id: str = cast(str, self.tracking_strategy_combo_box.currentData())
        self.tracking_strategy_changed.emit(strategy_id)

    @Slot()
    def _emit_tracking_source_changed(self) -> None:
        source_id: str = cast(str, self.tracking_source_combo_box.currentData())
        self.tracking_source_changed.emit(source_id)

    @Slot()
    def _emit_start_tracking(self) -> None:
        strategy_id: str = cast(str, self.tracking_strategy_combo_box.currentData())
        source_id: str = cast(str, self.tracking_source_combo_box.currentData())
        self.start_tracking_requested.emit(strategy_id, source_id)

    def update_video_related_widgets_state(self, is_enabled: bool = False) -> None:
        self._container.setEnabled(is_enabled)

    # --- Public API ---

    def restore_session_settings(self, vm: SessionSettingsViewModel) -> None:
        """Populates all right-panel widgets from the provided view model using safe signal blocking."""
        with QSignalBlocker(self.model_combo_box):
            idx: int = self.model_combo_box.findData(vm.detection_model_name)
            if idx >= 0:
                self.model_combo_box.setCurrentIndex(idx)

        with QSignalBlocker(self.tracking_strategy_combo_box):
            idx: int = self.tracking_strategy_combo_box.findData(vm.tracking_strategy)
            if idx >= 0:
                self.tracking_strategy_combo_box.setCurrentIndex(idx)

        self.set_iou_widgets_visible(vm.tracking_strategy == TrackingStrategy.HUNGARIAN)

        with QSignalBlocker(self.tracking_source_combo_box):
            idx: int = self.tracking_source_combo_box.findData(vm.tracking_source)
            if idx >= 0:
                self.tracking_source_combo_box.setCurrentIndex(idx)

        with QSignalBlocker(self.chosen_labels_edit):
            self.chosen_labels_edit.setText(vm.chosen_labels)

        with QSignalBlocker(self.min_confidence_spinbox):
            self.min_confidence_spinbox.setValue(vm.min_detection_confidence)

        with QSignalBlocker(self.min_tracker_confidence_spinbox):
            self.min_tracker_confidence_spinbox.setValue(vm.min_tracker_confidence)

        with QSignalBlocker(self.min_iou_spinbox):
            self.min_iou_spinbox.setValue(vm.min_iou)

        with QSignalBlocker(self.confidence_decay_spinbox):
            self.confidence_decay_spinbox.setValue(vm.confidence_decay)

        with QSignalBlocker(self.blur_strength_spinbox):
            self.blur_strength_spinbox.setValue(vm.blur_strength)

        with QSignalBlocker(self.draw_boxes_checkbox):
            self.draw_boxes_checkbox.setChecked(vm.draw_boxes)

        with QSignalBlocker(self.blur_checkbox):
            self.blur_checkbox.setChecked(vm.blur_enabled)

        self.set_blur_strength_visible(vm.blur_enabled)
        self.set_tracking_config_warning_visible(False)

    def set_iou_widgets_visible(self, visible: bool) -> None:
        self.min_iou_label.setVisible(visible)
        self.min_iou_spinbox.setVisible(visible)

    def set_blur_strength_visible(self, visible: bool) -> None:
        self.blur_strength_label.setVisible(visible)
        self.blur_strength_spinbox.setVisible(visible)

    def set_tracking_config_warning_visible(self, visible: bool) -> None:
        self.tracking_config_warning_label.setVisible(visible)

    def set_detection_loading_state(self, is_loading: bool) -> None:
        """Enables/disables certain widgets while a model is loading."""
        self.model_combo_box.setEnabled(not is_loading)
        self.detect_btn.setEnabled(not is_loading)
        self.detect_all_btn.setEnabled(not is_loading)
        self.imp_exp_detections_button.setEnabled(not is_loading)
        if is_loading:
            self.model_loading_spinner.start("Loading model")
        else:
            self.model_loading_spinner.stop()

    def set_tracking_loading_state(self, is_loading: bool) -> None:
        self.track_btn.setEnabled(not is_loading)
        self.imp_exp_tracks_button.setEnabled(not is_loading)
        self.tracking_strategy_combo_box.setEnabled(not is_loading)
        self.tracking_source_combo_box.setEnabled(not is_loading)

    def set_detection_progress_busy(self, is_busy: bool) -> None:
        self.detection_progress_bar.setVisible(is_busy)
        if is_busy:
            self._reset_detection_progress_bar()

    def set_detection_progress(self, current: int, total: int, label: str = "Detection", eta_msecs: float | None = None) -> None:
        maximum = max(total, 1)
        percent = (current / maximum) * 100
        percent_formatted = f"{percent:.2f} %"
        self.detection_progress_bar.setRange(0, 100)
        self.detection_progress_bar.setValue(max(0, min(percent, 100)))
        if eta_msecs is not None:
            eta_seconds = int(eta_msecs // 1000)
            eta_formatted = f"{eta_seconds // 3600:02d}:{eta_seconds % 3600 // 60:02d}:{eta_seconds % 60:02d}"
            self.detection_progress_bar.setFormat(f"{label}: {percent_formatted} [ {eta_formatted} ]")
        else:
            self.detection_progress_bar.setFormat(f"{label}: {percent_formatted}")

    def set_tracking_progress_busy(self, is_busy: bool, indeterminate: bool = False) -> None:
        self.tracking_progress_bar.setVisible(is_busy)
        if not is_busy:
            self._reset_tracking_progress_bar()
            return
        if indeterminate:
            self.tracking_progress_bar.setRange(0, 0)
            self.tracking_progress_bar.setFormat("Tracking in progress...")
            return
        self.tracking_progress_bar.setRange(0, 100)
        self.tracking_progress_bar.setValue(0)
        self.tracking_progress_bar.setFormat("Tracking: starting...")

    def set_tracking_progress(self, current: int, total: int, label: str = "Tracking") -> None:
        maximum = max(total, 1)
        percent = int((current / maximum) * 100)
        self.tracking_progress_bar.setRange(0, 100)
        self.tracking_progress_bar.setValue(max(0, min(percent, 100)))
        self.tracking_progress_bar.setFormat(f"{label}: {current}/{total}")

    def _reset_detection_progress_bar(self) -> None:
        self._reset_progress_bar(self.detection_progress_bar, "Detection: 0/0")

    def _reset_tracking_progress_bar(self) -> None:
        self._reset_progress_bar(self.tracking_progress_bar, "Tracking: 0/0")

    @staticmethod
    def _reset_progress_bar(progress_bar, label: str) -> None:
        progress_bar.setRange(0, 100)
        progress_bar.setValue(0)
        progress_bar.setFormat(label)

    def set_detection_model_boxes(self, boxes: list[ModelSelectionViewModel]) -> None:
        with QSignalBlocker(self.model_combo_box):
            self.model_combo_box.clear()
            for item in boxes:
                self.model_combo_box.addItem(item.display_name, item.model_id)

    def set_selected_detection_model(self, model_id: str) -> None:
        with QSignalBlocker(self.model_combo_box):
            index = self.model_combo_box.findData(model_id)
            if index >= 0:
                self.model_combo_box.setCurrentIndex(index)

    def connect_signals_to_export_handler(self, export_handler: ExportHandler) -> None:
        self.export_btn.clicked.connect(export_handler.on_export)
        self.export_all_btn.clicked.connect(export_handler.on_export_all)
        self.export_all_action.triggered.connect(export_handler.on_export_all)
        self.draw_boxes_checkbox.toggled.connect(export_handler.on_draw_boxes_changed)
        self.blur_checkbox.toggled.connect(export_handler.on_blur_toggled)
        self.blur_strength_spinbox.valueChanged.connect(export_handler.on_blur_strength_changed)
