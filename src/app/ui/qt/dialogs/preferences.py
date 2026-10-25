"""
Module for preferences; implements the Qt presentation components.

See Also:
    - [`AppPreferences`][app.shared.app_preferences.AppPreferences] — stores the preference values edited here
    - [`PreferencesHandler`][app.ui.handlers.preferences_handler.PreferencesHandler] — applies dialog changes

Layer: Presentation.
Context: Implements the qt presentation components at this architectural boundary.
"""

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
    QScrollArea,
    QWidget,
)

from app.domain import TrackingStrategy, VideoDataLayer
from app.shared.app_preferences import AppPreferences, SUPPORTED_THEMES
from app.ui.qt.shared.layout_shortcuts import create_hbox_layout, create_vbox_layout
from app.ui.qt.shared.widget_factories import (
    create_blur_strength_spinbox,
    create_int_spinbox,
    create_spinbox,
)

if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget
    from app.domain import ModelSelectionViewModel


@final
class PreferencesDialog(QDialog):
    """
    Collect persistent app preferences and default per-session settings.

    Layer: Presentation.
    Context: Supports user interaction and delegates application work through presentation contracts.
    """

    def __init__(
        self,
        preferences: AppPreferences,
        available_models: list[ModelSelectionViewModel],
        parent: QWidget | None = None,
    ) -> None:
        """
        Build the persistent preference dialog and populate saved defaults.

        Args:
            preferences: Current persisted preferences.
            available_models: Detection models offered by the application.
            parent: Optional parent widget.

        Note:
            Session defaults apply to sessions opened after the preferences are saved.

        Example:
            dialog = PreferencesDialog(preferences, available_models)
        """
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumWidth(560)
        self.setMaximumHeight(int(self.screen().availableGeometry().height() * 0.9))

        self._preferences = preferences
        self._available_models = available_models

        self._content_widget = QWidget()
        self._scroll_area = QScrollArea()
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setWidget(self._content_widget)

        self._init_widgets()
        self._build_ui()
        self._connect_signals()
        self._populate_from_preferences(preferences)

    def _init_widgets(self) -> None:
        """
        Create preference widgets and assign explanatory hover text.


        Note:
            Numeric ranges mirror the corresponding right-panel settings.

        Example:
            dialog._init_widgets()
        """
        self._hint_label = QLabel(
            "These preferences are stored across launches. Session defaults apply to videos opened after saving."
        )
        self._hint_label.setWordWrap(True)

        self._startup_fullscreen_checkbox = QCheckBox("Launch app in fullscreen mode")
        self._theme_combo_box = QComboBox()
        for theme in SUPPORTED_THEMES:
            self._theme_combo_box.addItem(theme.title(), theme)

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
            ("BoT-SORT", TrackingStrategy.BOT_SORT),
            ("ByteTrack (High Perf)", TrackingStrategy.BYTRACK),
            ("DeepSORT", TrackingStrategy.DEEP_SORT),
            ("CSRT (Manual/Slow)", TrackingStrategy.CSRT),
        ]:
            self._tracking_strategy_combo_box.addItem(name, value)
        self._tracking_strategy_tooltip = (
            "Selects the Multi-Object Tracking (MOT) algorithm:\n"
            "• Hungarian: Fast IoU/GIoU motion tracker.\n"
            "• ByteTrack: Two-stage motion tracker that recovers low-confidence occluded boxes.\n"
            "• DeepSORT: Combines motion cascade with a multi-view Re-ID appearance gallery.\n"
            "• BoT-SORT: High-HOTA/MOTA tracker combining ByteTrack's two-stage association, "
            "direct width/height Kalman filtering, and EMA Re-ID appearance fusion."
        )
        self._tracking_strategy_combo_box.setToolTip(self._tracking_strategy_tooltip)
        self._reid_embedding_dim_combo_box = QComboBox()
        for label, dimension in (
            ("128 (Fast)", 128),
            ("256 (Balanced)", 256),
            ("512 (High Precision)", 512),
        ):
            self._reid_embedding_dim_combo_box.addItem(label, dimension)
        self._reid_embedding_dim_tooltip = (
            "Select the Re-ID embedding vector size used to compare object appearance across frames. "
            "Larger sizes retain more appearance detail but require more memory and computation."
        )
        self._reid_embedding_dim_combo_box.setToolTip(self._reid_embedding_dim_tooltip)

        self._tracking_source_combo_box = QComboBox()
        for name, value in [("Raw Detections", VideoDataLayer.A), ("Reviewed Detections", VideoDataLayer.B)]:
            self._tracking_source_combo_box.addItem(name, value)

        self._min_iou_spinbox = create_spinbox(0.0, 1.0, 0.05, 0.3)
        self._min_tracker_confidence_spinbox = create_spinbox(0.0, 1.0, 0.05, 0.1)
        self._confidence_decay_spinbox = create_spinbox(0.0, 1.0, 0.01, 0.05)
        self._confidence_decay_tooltip = (
            "Per-frame confidence penalty applied when a tracker coasts without a matching detection. "
            "Unbridged tracks that never reconnect decay at 2x this rate so boxes disappear quickly "
            "when a subject exits the frame."
        )
        self._confidence_decay_label = QLabel("Confidence decay:")
        self._confidence_decay_label.setToolTip(self._confidence_decay_tooltip)
        self._confidence_decay_spinbox.setToolTip(self._confidence_decay_tooltip)
        self._offline_stitching_checkbox = QCheckBox("Bridge and smooth tracking gaps by default")
        self._max_stitch_gap_spinbox = create_int_spinbox(1, 60, 1, 25)
        self._gsi_smoothness_spinbox = create_spinbox(1.0, 30.0, 0.5, 10.0)

        self._draw_boxes_checkbox = QCheckBox("Draw bounding boxes by default")
        self._box_border_width_spinbox = create_int_spinbox(1, 10, 1, 2)
        self._show_preview_mask_checkbox = QCheckBox("Show blur mask in preview by default")
        self._preview_blur_enabled_checkbox = QCheckBox("Blur editor preview by default")
        self._blur_enabled_checkbox = QCheckBox("Blur bounding boxes by default")
        self._blur_strength_spinbox = create_blur_strength_spinbox(15.0)

        self._offline_stitching_tooltip = (
            "When enabled, new sessions use offline track stitching and Gaussian Smoothed "
            "Interpolation after tracking. This default can be changed per session in the Tracking panel."
        )
        self._max_stitch_gap_tooltip = (
            "Default maximum number of consecutive missed frames to bridge, from 1 to 60. "
            "This value applies to videos opened after saving these preferences."
        )
        self._gsi_smoothness_tooltip = (
            "Default Gaussian interpolation lengthscale (tau), from 1 to 30. "
            "Higher values produce smoother curves across gaps."
        )
        self._box_border_width_tooltip = (
            "Default editor-preview outline weight, scaled with the displayed video size and zoom. "
            "This setting does not affect exported video."
        )
        self._show_preview_mask_tooltip = (
            "Show the combined blur-mask footprint in the editor preview by default. "
            "This overlay is not included in exported video."
        )
        self._preview_blur_tooltip = (
            "Render Gaussian blur in the editor preview by default when export blur is enabled. "
            "This preference does not change the final export setting."
        )
        self._default_blur_tooltip = (
            "Master toggle to apply Gaussian blur over tracked bounding boxes in exported videos. "
            "Turning this on also makes the 'Blur Preview' option available in the editor."
        )
        self._blur_strength_tooltip = (
            "Controls the Gaussian blur kernel size (sigma/radius) used to redact subjects in exported "
            "video and in the live editor when 'Blur Preview' is active. Higher values produce stronger "
            "anonymization."
        )
        for widget, tooltip in (
            (
                self._draw_boxes_checkbox,
                "Show bounding box outlines and labels in the editor preview by default. "
                "This preference does not affect exported video.",
            ),
            (self._offline_stitching_checkbox, self._offline_stitching_tooltip),
            (self._max_stitch_gap_spinbox, self._max_stitch_gap_tooltip),
            (self._gsi_smoothness_spinbox, self._gsi_smoothness_tooltip),
            (self._box_border_width_spinbox, self._box_border_width_tooltip),
            (self._show_preview_mask_checkbox, self._show_preview_mask_tooltip),
            (self._preview_blur_enabled_checkbox, self._preview_blur_tooltip),
            (self._blur_enabled_checkbox, self._default_blur_tooltip),
            (self._blur_strength_spinbox, self._blur_strength_tooltip),
        ):
            widget.setToolTip(tooltip)

        self._export_directory_edit = QLineEdit()
        self._export_directory_edit.setPlaceholderText("Optional default export directory")
        self._browse_export_directory_button = QPushButton("Browse…")
        self._export_prefix_edit = QLineEdit()
        self._export_suffix_edit = QLineEdit()

        self._button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )

    def _build_ui(self) -> None:
        """
        Arrange preference controls into app, detection, tracking, and render groups.


        Note:
            Preview-only defaults and export rendering defaults use separate groups.

        Example:
            dialog._build_ui()
        """
        root = create_vbox_layout(self, spacing=12)
        content = create_vbox_layout(self._content_widget, spacing=12)
        content.addWidget(self._hint_label)

        ui_group = QGroupBox("App")
        ui_form = QFormLayout(ui_group)
        ui_form.addRow("Default theme:", self._theme_combo_box)
        ui_form.addRow("", self._startup_fullscreen_checkbox)
        content.addWidget(ui_group)

        detection_group = QGroupBox("Default Detection Settings")
        detection_form = QFormLayout(detection_group)
        detection_form.addRow("Model:", self._model_combo_box)
        detection_form.addRow("Min confidence:", self._min_confidence_spinbox)
        detection_form.addRow("Labels:", self._labels_edit)
        content.addWidget(detection_group)

        tracking_group = QGroupBox("Default Tracking Settings")
        tracking_form = QFormLayout(tracking_group)
        self._tracking_strategy_label = QLabel("Strategy:")
        self._tracking_strategy_label.setToolTip(self._tracking_strategy_tooltip)
        tracking_form.addRow(self._tracking_strategy_label, self._tracking_strategy_combo_box)
        tracking_form.addRow("Source:", self._tracking_source_combo_box)
        self._reid_embedding_dim_label = QLabel("Re-ID Embedding Size")
        self._reid_embedding_dim_label.setToolTip(self._reid_embedding_dim_tooltip)
        tracking_form.addRow(self._reid_embedding_dim_label, self._reid_embedding_dim_combo_box)
        tracking_form.addRow("Min IoU:", self._min_iou_spinbox)
        tracking_form.addRow("Min tracker confidence:", self._min_tracker_confidence_spinbox)
        tracking_form.addRow(self._confidence_decay_label, self._confidence_decay_spinbox)
        tracking_form.addRow("", self._offline_stitching_checkbox)
        self._max_stitch_gap_label = QLabel("Max stitch gap (frames):")
        self._max_stitch_gap_label.setToolTip(self._max_stitch_gap_tooltip)
        tracking_form.addRow(self._max_stitch_gap_label, self._max_stitch_gap_spinbox)
        self._gsi_smoothness_label = QLabel("GSI smoothness:")
        self._gsi_smoothness_label.setToolTip(self._gsi_smoothness_tooltip)
        tracking_form.addRow(self._gsi_smoothness_label, self._gsi_smoothness_spinbox)
        content.addWidget(tracking_group)

        preview_group = QGroupBox("Default Preview Settings")
        preview_form = QFormLayout(preview_group)
        preview_form.addRow("", self._draw_boxes_checkbox)
        self._box_border_width_label = QLabel("Outline weight:")
        self._box_border_width_label.setToolTip(self._box_border_width_tooltip)
        preview_form.addRow(self._box_border_width_label, self._box_border_width_spinbox)
        preview_form.addRow("", self._show_preview_mask_checkbox)
        preview_form.addRow("", self._preview_blur_enabled_checkbox)
        render_group = QGroupBox("Default Render Settings")
        render_form = QFormLayout(render_group)
        render_form.addRow("", self._blur_enabled_checkbox)
        self._blur_strength_label = QLabel("Blur strength:")
        self._blur_strength_label.setToolTip(self._blur_strength_tooltip)
        render_form.addRow(self._blur_strength_label, self._blur_strength_spinbox)
        content.addWidget(preview_group)
        content.addWidget(render_group)

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
        content.addWidget(export_group)

        root.addWidget(self._scroll_area)
        root.addWidget(self._button_box)

    def _connect_signals(self) -> None:
        """
        Connect preference controls to dialog state and browse actions.


        Note:
            Master blur and offline stitching toggles gate their dependent settings.

        Example:
            dialog._connect_signals()
        """
        self._blur_enabled_checkbox.toggled.connect(self._on_blur_toggled)
        self._offline_stitching_checkbox.toggled.connect(self._on_offline_stitching_toggled)
        self._browse_export_directory_button.clicked.connect(self._on_browse_export_directory)
        self._button_box.accepted.connect(self.accept)
        self._button_box.rejected.connect(self.reject)

    def _populate_from_preferences(self, preferences: AppPreferences) -> None:
        """
        Restore preference values and dependent control enabled states.

        Args:
            preferences: Values to display.

        Note:
            Signal state changes are applied explicitly after restoring checkboxes.

        Example:
            dialog._populate_from_preferences(preferences)
        """
        self._startup_fullscreen_checkbox.setChecked(preferences.startup_fullscreen)
        theme_index = self._theme_combo_box.findData(preferences.default_theme)
        if theme_index >= 0:
            self._theme_combo_box.setCurrentIndex(theme_index)

        model_index = self._model_combo_box.findData(preferences.default_detection_model_name)
        if model_index >= 0:
            self._model_combo_box.setCurrentIndex(model_index)

        tracking_strategy_index = self._tracking_strategy_combo_box.findData(preferences.default_tracking_strategy)
        if tracking_strategy_index >= 0:
            self._tracking_strategy_combo_box.setCurrentIndex(tracking_strategy_index)

        tracking_source_index = self._tracking_source_combo_box.findData(preferences.default_tracking_source)
        if tracking_source_index >= 0:
            self._tracking_source_combo_box.setCurrentIndex(tracking_source_index)

        reid_embedding_dim_index = self._reid_embedding_dim_combo_box.findData(preferences.default_reid_embedding_dim)
        if reid_embedding_dim_index >= 0:
            self._reid_embedding_dim_combo_box.setCurrentIndex(reid_embedding_dim_index)

        self._min_confidence_spinbox.setValue(preferences.default_min_detection_confidence)
        self._labels_edit.setText(preferences.chosen_labels_text)
        self._min_iou_spinbox.setValue(preferences.default_min_iou)
        self._min_tracker_confidence_spinbox.setValue(preferences.default_min_tracker_confidence)
        self._confidence_decay_spinbox.setValue(preferences.default_confidence_decay)
        self._offline_stitching_checkbox.setChecked(preferences.default_offline_stitching_enabled)
        self._max_stitch_gap_spinbox.setValue(preferences.default_max_stitch_gap)
        self._gsi_smoothness_spinbox.setValue(preferences.default_gsi_smoothness)
        self._draw_boxes_checkbox.setChecked(preferences.default_draw_boxes)
        self._box_border_width_spinbox.setValue(preferences.default_box_border_width)
        self._show_preview_mask_checkbox.setChecked(preferences.default_show_preview_mask)
        self._preview_blur_enabled_checkbox.setChecked(preferences.default_preview_blur_enabled)
        self._blur_enabled_checkbox.setChecked(preferences.default_blur_enabled)
        self._blur_strength_spinbox.setValue(preferences.default_blur_strength)
        self._export_directory_edit.setText(preferences.default_export_directory)
        self._export_prefix_edit.setText(preferences.default_export_prefix)
        self._export_suffix_edit.setText(preferences.default_export_suffix)
        self._on_blur_toggled(preferences.default_blur_enabled)
        self._on_offline_stitching_toggled(preferences.default_offline_stitching_enabled)

    @Slot(bool)
    def _on_blur_toggled(self, enabled: bool) -> None:
        """
        Gate export-strength and preview-blur defaults on master blur.

        Args:
            enabled: Whether blur is enabled by default for new sessions.

        Note:
            Disabling the master keeps the saved preview preference intact but unavailable.

        Example:
            dialog._on_blur_toggled(False)
        """
        self._blur_strength_spinbox.setEnabled(enabled)
        self._preview_blur_enabled_checkbox.setEnabled(enabled)

    @Slot(bool)
    def _on_offline_stitching_toggled(self, enabled: bool) -> None:
        """
        Gate gap length and GSI smoothness preference controls.

        Args:
            enabled: Whether offline stitching is enabled by default.

        Note:
            Values are retained while disabled so toggling back on restores them.

        Example:
            dialog._on_offline_stitching_toggled(True)
        """
        self._max_stitch_gap_spinbox.setEnabled(enabled)
        self._max_stitch_gap_label.setEnabled(enabled)
        self._gsi_smoothness_spinbox.setEnabled(enabled)
        self._gsi_smoothness_label.setEnabled(enabled)

    @Slot()
    def _on_browse_export_directory(self) -> None:
        """
        Open a directory chooser for the default export location.


        Note:
            Cancelling the chooser leaves the existing preference unchanged.

        Example:
            dialog._on_browse_export_directory()
        """
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select Default Export Directory",
            self._export_directory_edit.text().strip(),
        )
        if directory:
            self._export_directory_edit.setText(directory)

    def get_preferences(self) -> AppPreferences:
        """
        Create a preference value object from the current controls.


        Returns:
            Updated preferences ready to persist.


        Note:
            Labels are split and whitespace-trimmed before storing.

        Example:
            updated = dialog.get_preferences()
        """
        return AppPreferences(
            startup_fullscreen=self._startup_fullscreen_checkbox.isChecked(),
            default_theme=cast(str, self._theme_combo_box.currentData()),
            default_detection_model_name=cast(str, self._model_combo_box.currentData()),
            default_min_detection_confidence=float(self._min_confidence_spinbox.value()),
            default_chosen_labels=[
                item.strip() for item in self._labels_edit.text().split(",") if item.strip()
            ],
            default_tracking_strategy=cast(str, self._tracking_strategy_combo_box.currentData()),
            default_tracking_source=cast(str, self._tracking_source_combo_box.currentData()),
            default_reid_embedding_dim=cast(int, self._reid_embedding_dim_combo_box.currentData()),
            default_min_iou=float(self._min_iou_spinbox.value()),
            default_min_tracker_confidence=float(self._min_tracker_confidence_spinbox.value()),
            default_confidence_decay=float(self._confidence_decay_spinbox.value()),
            default_offline_stitching_enabled=self._offline_stitching_checkbox.isChecked(),
            default_max_stitch_gap=int(self._max_stitch_gap_spinbox.value()),
            default_gsi_smoothness=float(self._gsi_smoothness_spinbox.value()),
            default_draw_boxes=self._draw_boxes_checkbox.isChecked(),
            default_box_border_width=int(self._box_border_width_spinbox.value()),
            default_show_preview_mask=self._show_preview_mask_checkbox.isChecked(),
            default_preview_blur_enabled=self._preview_blur_enabled_checkbox.isChecked(),
            default_blur_enabled=self._blur_enabled_checkbox.isChecked(),
            default_blur_strength=float(self._blur_strength_spinbox.value()),
            default_export_directory=self._export_directory_edit.text().strip(),
            default_export_prefix=self._export_prefix_edit.text().strip(),
            default_export_suffix=self._export_suffix_edit.text().strip(),
        )
