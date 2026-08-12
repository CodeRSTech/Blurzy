from __future__ import annotations

from typing import TYPE_CHECKING, final, cast

from PySide6.QtCore import Slot
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QPushButton,
)

from app.domain import TrackingStrategy, VideoDataLayer
from app.shared.app_preferences import AppPreferences
from app.ui.qt.shared.layout_shortcuts import create_hbox_layout, create_vbox_layout
from app.ui.qt.shared.widget_factories import create_spinbox

if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget
    from app.domain import ModelSelectionViewModel


@final
class PreferencesDialog(QDialog):
    """Collect persistent app preferences and default per-session settings."""

    def __init__(
        self,
        preferences: AppPreferences,
        available_models: list[ModelSelectionViewModel],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumWidth(560)

        self._preferences = preferences
        self._available_models = available_models

        self._init_widgets()
        self._build_ui()
        self._connect_signals()
        self._populate_from_preferences(preferences)

    def _init_widgets(self) -> None:
        self._hint_label = QLabel(
            "These preferences are stored across launches. Session defaults apply to videos opened after saving."
        )
        self._hint_label.setWordWrap(True)

        self._startup_fullscreen_checkbox = QCheckBox("Launch app in fullscreen mode")

        self._model_combo_box = QComboBox()
        for model in self._available_models:
            self._model_combo_box.addItem(model.display_name, model.model_id)

        self._min_confidence_spinbox = create_spinbox(0.0, 1.0, 0.05, 0.25)
        self._labels_edit = QLineEdit()
        self._labels_edit.setPlaceholderText("person, cat, dog")

        self._tracking_strategy_combo_box = QComboBox()
        for name, value in [
            ("Dummy Tracker (Copy)", TrackingStrategy.DUMMY),
            ("Hungarian IoU (Fast)", TrackingStrategy.HUNGARIAN),
            ("ByteTrack (High Perf)", TrackingStrategy.BYTRACK),
            ("DeepSORT", TrackingStrategy.DEEP_SORT),
            ("CSRT (Manual/Slow)", TrackingStrategy.CSRT),
        ]:
            self._tracking_strategy_combo_box.addItem(name, value)

        self._tracking_source_combo_box = QComboBox()
        for name, value in [("Raw Detections", VideoDataLayer.A), ("Reviewed Detections", VideoDataLayer.B)]:
            self._tracking_source_combo_box.addItem(name, value)

        self._min_iou_spinbox = create_spinbox(0.0, 1.0, 0.05, 0.3)
        self._min_tracker_confidence_spinbox = create_spinbox(0.0, 1.0, 0.05, 0.1)
        self._confidence_decay_spinbox = create_spinbox(0.0, 1.0, 0.01, 0.05)

        self._draw_boxes_checkbox = QCheckBox("Draw bounding boxes by default")
        self._blur_enabled_checkbox = QCheckBox("Blur bounding boxes by default")
        self._blur_strength_spinbox = create_spinbox(0.0, 25.0, 1.0, 15.0)

        self._export_directory_edit = QLineEdit()
        self._export_directory_edit.setPlaceholderText("Optional default export directory")
        self._browse_export_directory_button = QPushButton("Browse…")
        self._export_prefix_edit = QLineEdit()
        self._export_suffix_edit = QLineEdit()

        self._button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )

    def _build_ui(self) -> None:
        root = create_vbox_layout(self, spacing=12)
        root.addWidget(self._hint_label)

        ui_group = QGroupBox("App")
        ui_form = QFormLayout(ui_group)
        ui_form.addRow("", self._startup_fullscreen_checkbox)
        root.addWidget(ui_group)

        detection_group = QGroupBox("Default Detection Settings")
        detection_form = QFormLayout(detection_group)
        detection_form.addRow("Model:", self._model_combo_box)
        detection_form.addRow("Min confidence:", self._min_confidence_spinbox)
        detection_form.addRow("Labels:", self._labels_edit)
        root.addWidget(detection_group)

        tracking_group = QGroupBox("Default Tracking Settings")
        tracking_form = QFormLayout(tracking_group)
        tracking_form.addRow("Strategy:", self._tracking_strategy_combo_box)
        tracking_form.addRow("Source:", self._tracking_source_combo_box)
        tracking_form.addRow("Min IoU:", self._min_iou_spinbox)
        tracking_form.addRow("Min tracker confidence:", self._min_tracker_confidence_spinbox)
        tracking_form.addRow("Confidence decay:", self._confidence_decay_spinbox)
        root.addWidget(tracking_group)

        preview_group = QGroupBox("Default Preview / Export Settings")
        preview_form = QFormLayout(preview_group)
        preview_form.addRow("", self._draw_boxes_checkbox)
        preview_form.addRow("", self._blur_enabled_checkbox)
        preview_form.addRow("Blur strength:", self._blur_strength_spinbox)
        root.addWidget(preview_group)

        export_group = QGroupBox("Default Export Naming")
        export_form = QFormLayout(export_group)
        export_form.addRow(
            "Export directory:",
            create_hbox_layout(
                widgets=(self._export_directory_edit, self._browse_export_directory_button)
            ),
        )
        export_form.addRow("Filename prefix:", self._export_prefix_edit)
        export_form.addRow("Filename suffix:", self._export_suffix_edit)
        root.addWidget(export_group)

        root.addWidget(self._button_box)

    def _connect_signals(self) -> None:
        self._blur_enabled_checkbox.toggled.connect(self._on_blur_toggled)
        self._browse_export_directory_button.clicked.connect(self._on_browse_export_directory)
        self._button_box.accepted.connect(self.accept)
        self._button_box.rejected.connect(self.reject)

    def _populate_from_preferences(self, preferences: AppPreferences) -> None:
        self._startup_fullscreen_checkbox.setChecked(preferences.startup_fullscreen)

        model_index = self._model_combo_box.findData(preferences.default_detection_model_name)
        if model_index >= 0:
            self._model_combo_box.setCurrentIndex(model_index)

        tracking_strategy_index = self._tracking_strategy_combo_box.findData(preferences.default_tracking_strategy)
        if tracking_strategy_index >= 0:
            self._tracking_strategy_combo_box.setCurrentIndex(tracking_strategy_index)

        tracking_source_index = self._tracking_source_combo_box.findData(preferences.default_tracking_source)
        if tracking_source_index >= 0:
            self._tracking_source_combo_box.setCurrentIndex(tracking_source_index)

        self._min_confidence_spinbox.setValue(preferences.default_min_detection_confidence)
        self._labels_edit.setText(preferences.chosen_labels_text)
        self._min_iou_spinbox.setValue(preferences.default_min_iou)
        self._min_tracker_confidence_spinbox.setValue(preferences.default_min_tracker_confidence)
        self._confidence_decay_spinbox.setValue(preferences.default_confidence_decay)
        self._draw_boxes_checkbox.setChecked(preferences.default_draw_boxes)
        self._blur_enabled_checkbox.setChecked(preferences.default_blur_enabled)
        self._blur_strength_spinbox.setValue(preferences.default_blur_strength)
        self._export_directory_edit.setText(preferences.default_export_directory)
        self._export_prefix_edit.setText(preferences.default_export_prefix)
        self._export_suffix_edit.setText(preferences.default_export_suffix)
        self._on_blur_toggled(preferences.default_blur_enabled)

    @Slot(bool)
    def _on_blur_toggled(self, enabled: bool) -> None:
        self._blur_strength_spinbox.setEnabled(enabled)

    @Slot()
    def _on_browse_export_directory(self) -> None:
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select Default Export Directory",
            self._export_directory_edit.text().strip(),
        )
        if directory:
            self._export_directory_edit.setText(directory)

    def get_preferences(self) -> AppPreferences:
        return AppPreferences(
            startup_fullscreen=self._startup_fullscreen_checkbox.isChecked(),
            default_detection_model_name=cast(str, self._model_combo_box.currentData()),
            default_min_detection_confidence=float(self._min_confidence_spinbox.value()),
            default_chosen_labels=[
                item.strip() for item in self._labels_edit.text().split(",") if item.strip()
            ],
            default_tracking_strategy=cast(str, self._tracking_strategy_combo_box.currentData()),
            default_tracking_source=cast(str, self._tracking_source_combo_box.currentData()),
            default_min_iou=float(self._min_iou_spinbox.value()),
            default_min_tracker_confidence=float(self._min_tracker_confidence_spinbox.value()),
            default_confidence_decay=float(self._confidence_decay_spinbox.value()),
            default_draw_boxes=self._draw_boxes_checkbox.isChecked(),
            default_blur_enabled=self._blur_enabled_checkbox.isChecked(),
            default_blur_strength=float(self._blur_strength_spinbox.value()),
            default_export_directory=self._export_directory_edit.text().strip(),
            default_export_prefix=self._export_prefix_edit.text().strip(),
            default_export_suffix=self._export_suffix_edit.text().strip(),
        )
