"""Module for right panel; implements the Qt presentation components.

See Also:
    - [`VideoDataLayerGroup`][app.domain.video.layer_group.VideoDataLayerGroup] — groups layer controls shown in the panel
    - [`TrackingStrategy`][app.domain.tracking.tracking_strategy.TrackingStrategy] — supplies tracking choices

Layer: Presentation.
Context: Implements the qt presentation components at this architectural boundary.
"""

from __future__ import annotations

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
    QWidget,
)

from app.domain import TrackingStrategy, VideoDataLayer
from app.infrastructure.detection.model.helpers import (
    DETECTION_MODEL_PROVIDER_ALL,
    get_detection_model_provider_options,
    resolve_detection_model_provider,
)
from app.ui.qt.shared.layout_shortcuts import create_vbox_layout
from app.ui.qt.shared.widget_factories import (
    create_blur_strength_spinbox,
    create_int_spinbox,
    create_qhbox_with_widgets,
    create_progress_bar,
    create_spinbox,
)
from app.ui.qt.widgets.feedback.spinner_label import InlineSpinnerLabel
from app.ui.qt.widgets.collapsible_panel import CollapsiblePanel

if TYPE_CHECKING:
    from app.ui.handlers import ExportHandler
    from app.domain.views import SessionSettingsViewModel, ModelSelectionViewModel


@final
class RightControlPanel(QScrollArea):
    """Scrollable panel containing Detection, Tracking, Preview, and Render controls.

    Controls emit state changes and execution requests.

    Args:
        parent: Optional owner widget.

    Note:
        Preview controls affect the editor viewport only; Render controls define
        final export behavior and gate the optional live preview blur.

    Example:
        ```python
        panel = RightControlPanel()
        ```

    ??? abstract "Sample Preview"
        <img class="api-example-image"
        src="api-asset:ui/right-panel/preview.png"
        alt="Sample preview of the right panel, some components are not shown.">


Layer: Presentation.
Context: Supports user interaction and delegates application work through presentation contracts.
"""

    # --- Signals ---
    # PySide Rule: Signals must be declared at the class level.
    chosen_labels_changed = Signal(str)
    model_changed = Signal(str)
    tracking_strategy_changed = Signal(str)
    tracking_source_changed = Signal(str)
    reid_embedding_dim_changed = Signal(int)
    start_tracking_requested = Signal(str, str)
    privacy_features_enabled_changed = Signal(bool)
    resist_box_shrinking_changed = Signal(bool)
    shrink_resistance_changed = Signal(float)
    pre_detection_padding_sec_changed = Signal(float)
    post_detection_padding_sec_changed = Signal(float)
    box_safety_padding_pct_changed = Signal(float)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setMinimumWidth(280)

        # Container to hold everything inside the scroll area
        self._container = QWidget()
        self._layout = create_vbox_layout(self._container, margins=(5, 5, 5, 5), spacing=10)
        # All widgets are strictly instantiated as instance attributes here.
        self._init_widgets()
        self._build_ui()
        self._connect_signals()

        self.setWidget(self._container)

    def _init_widgets(self) -> None:
        """Create every control and label before layout construction.


        Note:
            Tracking and preview numeric ranges match ProcessingSettings validation.

        Example:
            ```python
            panel._init_widgets()
            ```
        """
        # --- Detection Widgets ---

        ############################################################################################################
        #   v Detection                                                                                            #
        ############################################################################################################
        self.detection_box = CollapsiblePanel("Detection")
        self._all_detection_models: list[ModelSelectionViewModel] = []
        self._active_provider_id = DETECTION_MODEL_PROVIDER_ALL
        self.provider_combo_box = QComboBox()
        for provider_id, label in get_detection_model_provider_options():
            self.provider_combo_box.addItem(label, provider_id)
        self.provider_selection = create_qhbox_with_widgets([QLabel("Provider:"), self.provider_combo_box])
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
        self.tracking_box = CollapsiblePanel("Tracking")
        self.privacy_features_box = CollapsiblePanel("Privacy Features")
        self.privacy_features_box_tooltip = (
            "Configure optional privacy-first box protection and temporal padding. "
            "These settings affect tracking results only when Enable Privacy Shield is checked."
        )
        self.privacy_features_box.setToolTip(self.privacy_features_box_tooltip)
        self.privacy_features_box.toggle_button.setToolTip(self.privacy_features_box_tooltip)
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
            ("BoT-SORT", TrackingStrategy.BOT_SORT),
            ("ByteTrack (High Perf)", TrackingStrategy.BYTRACK),
            ("DeepSORT", TrackingStrategy.DEEP_SORT),
            ("CSRT (Manual/Slow)", TrackingStrategy.CSRT),
        ]:
            self.tracking_strategy_combo_box.addItem(name, value)
            self.tracking_strategy_combo_box.setCurrentIndex(1)
        self.strategy_tooltip = (
            "Selects the Multi-Object Tracking (MOT) algorithm:\n"
            "• Hungarian: Fast IoU/GIoU motion tracker.\n"
            "• ByteTrack: Two-stage motion tracker that recovers low-confidence occluded boxes.\n"
            "• DeepSORT: Combines motion cascade with a multi-view Re-ID appearance gallery.\n"
            "• BoT-SORT: High-HOTA/MOTA tracker combining ByteTrack's two-stage association, "
            "direct width/height Kalman filtering, and EMA Re-ID appearance fusion."
        )
        self.strategy_label = QLabel("Strategy:")
        self.strategy_label.setToolTip(self.strategy_tooltip)
        self.tracking_strategy_combo_box.setToolTip(self.strategy_tooltip)
        self.strategy_selection = create_qhbox_with_widgets([self.strategy_label, self.tracking_strategy_combo_box])
        self.reid_embedding_dim_label = QLabel("Re-ID Embedding Size")
        self.reid_embedding_dim_combo_box = QComboBox()
        for label, dimension in (
            ("128 (Fast)", 128),
            ("256 (Balanced)", 256),
            ("512 (High Precision)", 512),
        ):
            self.reid_embedding_dim_combo_box.addItem(label, dimension)
        self.reid_embedding_dim_combo_box.setCurrentIndex(1)
        self.reid_embedding_dim_tooltip = (
            "Selects the vector dimension (128, 256, or 512) of the Appearance Embedding "
            "(Re-ID biometric/visual fingerprint) extracted from each bounding box crop. Used by "
            "DeepSORT, BoT-SORT, and offline track stitching to keep track of individuals running "
            "in zigzags, crossing paths, or reappearing after occlusion. 128 is fastest for 4K video; "
            "256 is balanced; 512 captures finer color and texture detail in crowded scenes."
        )
        self.reid_embedding_dim_label.setToolTip(self.reid_embedding_dim_tooltip)
        self.reid_embedding_dim_combo_box.setToolTip(self.reid_embedding_dim_tooltip)
        self.reid_embedding_dim_selection = create_qhbox_with_widgets(
            [self.reid_embedding_dim_label, self.reid_embedding_dim_combo_box]
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
            min_val=0.1, max_val=0.5, step=0.05, default=0.1
        )
        self.min_tracker_confidence_label = QLabel("Min Conf:")
        self.min_tracker_confidence_tooltip = (
            "Sets the minimum confidence retained for tracked boxes (0.10–0.50). "
            "Lower values preserve weaker coasting predictions; this floor is separate "
            "from ByteTrack's adaptive Stage 1 and Stage 2 association thresholds."
        )
        self.min_tracker_confidence_label.setToolTip(self.min_tracker_confidence_tooltip)
        self.min_tracker_confidence_spinbox.setToolTip(self.min_tracker_confidence_tooltip)
        self.min_tracker_conf_selection = create_qhbox_with_widgets(
            [self.min_tracker_confidence_label, self.min_tracker_confidence_spinbox]
        )
        #
        #               +----------------------------------------------------+
        #   Decay:      | 0.05                                     [ ^ | v ] |
        #               +----------------------------------------------------+
        self.confidence_decay_spinbox = create_spinbox(min_val=0.0, max_val=1.0, step=0.01, default=0.05)
        self.confidence_decay_label = QLabel("Confidence Decay:")
        self.confidence_decay_tooltip = (
            "Per-frame confidence penalty applied when a tracker coasts without a matching detection. "
            "Unbridged tracks that never reconnect decay at 2x this rate so boxes disappear quickly "
            "when a subject exits the frame."
        )
        self.confidence_decay_label.setToolTip(self.confidence_decay_tooltip)
        self.confidence_decay_spinbox.setToolTip(self.confidence_decay_tooltip)
        self.decay_selection = create_qhbox_with_widgets(
            [self.confidence_decay_label, self.confidence_decay_spinbox]
        )
        #
        #   [ ] Bridge & Smooth Gaps (GSI)
        #
        self.offline_stitching_checkbox = QCheckBox("Bridge & Smooth Gaps (GSI)")
        self.offline_stitching_tooltip = (
            "When enabled, runs a two-pass bidirectional stitcher after tracking to reconnect broken "
            "tracks across missed detections and smoothly interpolates the gap using Gaussian Smoothed "
            "Interpolation (GSI). Unbridged tracks that leave the frame decay rapidly to prevent "
            "floating ghost blurs."
        )
        self.offline_stitching_checkbox.setToolTip(self.offline_stitching_tooltip)
        self.max_stitch_gap_label = QLabel("Max Stitch Gap (frames):")
        self.max_stitch_gap_spinbox = create_int_spinbox(1, 60, 1, 25)
        self.max_stitch_gap_tooltip = (
            "Maximum number of consecutive missed frames (1–60) over which two broken track segments "
            "can be stitched together and smoothly interpolated. At 25 FPS, 25 frames equals 1 second "
            "of occlusion."
        )
        self.max_stitch_gap_label.setToolTip(self.max_stitch_gap_tooltip)
        self.max_stitch_gap_spinbox.setToolTip(self.max_stitch_gap_tooltip)
        self.max_stitch_gap_selection = create_qhbox_with_widgets(
            [self.max_stitch_gap_label, self.max_stitch_gap_spinbox]
        )
        self.gsi_smoothness_label = QLabel("GSI Smoothness:")
        self.gsi_smoothness_spinbox = create_spinbox(1.0, 30.0, 0.5, 10.0)
        self.gsi_smoothness_tooltip = (
            "Controls the Gaussian kernel lengthscale (tau) used to smooth bounding box trajectories "
            "across bridged gaps. Higher values produce smoother, more gradual curves; lower values "
            "hug the raw detector boxes more tightly."
        )
        self.gsi_smoothness_label.setToolTip(self.gsi_smoothness_tooltip)
        self.gsi_smoothness_spinbox.setToolTip(self.gsi_smoothness_tooltip)
        self.gsi_smoothness_selection = create_qhbox_with_widgets(
            [self.gsi_smoothness_label, self.gsi_smoothness_spinbox]
        )
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
        self.privacy_features_checkbox = QCheckBox("Enable Privacy Shield")
        self.privacy_features_tooltip = (
            "Activates conservative, privacy-first tracking rules designed to eliminate missed redactions. "
            "Prevents sudden bounding-box shrinkage, backfills boxes before a subject is first detected, "
            "holds boxes after the last detection, and adds a safety border."
        )
        self.privacy_features_checkbox.setToolTip(self.privacy_features_tooltip)
        self.resist_box_shrinking_checkbox = QCheckBox("Resist Box Shrinking")
        self.resist_box_shrinking_tooltip = (
            "Prevents tracked bounding boxes from shrinking abruptly when a detector temporarily sees only "
            "part of a subject, such as a torso or head instead of the full body. Boxes still expand "
            "immediately when the subject grows larger."
        )
        self.resist_box_shrinking_checkbox.setToolTip(self.resist_box_shrinking_tooltip)
        self.shrink_resistance_label = QLabel("Shrink Resistance:")
        self.shrink_resistance_spinbox = create_spinbox(0.0, 0.99, 0.05, 0.85)
        self.shrink_resistance_tooltip = (
            "Controls how strongly bounding boxes resist contracting over short intervals "
            "(0.00 = allow normal shrinking, 0.85 = strong damping, 0.99 = lock to maximum observed size). "
            "Top/head anchors are preserved when lower-body detections drop out."
        )
        self.shrink_resistance_label.setToolTip(self.shrink_resistance_tooltip)
        self.shrink_resistance_spinbox.setToolTip(self.shrink_resistance_tooltip)
        self.shrink_resistance_selection = create_qhbox_with_widgets(
            [self.shrink_resistance_label, self.shrink_resistance_spinbox]
        )
        self.pre_detection_padding_sec_label = QLabel("Pre-Detection Buffer (s):")
        self.pre_detection_padding_sec_spinbox = create_spinbox(0.0, 5.0, 0.1, 0.5)
        self.pre_detection_padding_sec_tooltip = (
            "Time in seconds (0.0–5.0 s) to display and backfill a tracked bounding box before the "
            "subject's first confirmed detection. Protects subjects who were partially visible or "
            "occluded for a few frames before the detector first recognized them."
        )
        self.pre_detection_padding_sec_label.setToolTip(self.pre_detection_padding_sec_tooltip)
        self.pre_detection_padding_sec_spinbox.setToolTip(self.pre_detection_padding_sec_tooltip)
        self.pre_detection_padding_sec_selection = create_qhbox_with_widgets(
            [self.pre_detection_padding_sec_label, self.pre_detection_padding_sec_spinbox]
        )
        self.post_detection_padding_sec_label = QLabel("Post-Detection Hold (s):")
        self.post_detection_padding_sec_spinbox = create_spinbox(0.0, 5.0, 0.1, 0.5)
        self.post_detection_padding_sec_tooltip = (
            "Time in seconds (0.0–5.0 s) to keep displaying a tracked bounding box after the subject's "
            "last confirmed detection. Ensures subjects remain blurred while lingering in partial "
            "occlusion or exiting the scene."
        )
        self.post_detection_padding_sec_label.setToolTip(self.post_detection_padding_sec_tooltip)
        self.post_detection_padding_sec_spinbox.setToolTip(self.post_detection_padding_sec_tooltip)
        self.post_detection_padding_sec_selection = create_qhbox_with_widgets(
            [self.post_detection_padding_sec_label, self.post_detection_padding_sec_spinbox]
        )
        self.box_safety_padding_pct_label = QLabel("Safety Margin (%):")
        self.box_safety_padding_pct_spinbox = create_spinbox(0.0, 50.0, 1.0, 10.0)
        self.box_safety_padding_pct_tooltip = (
            "Expands tracked bounding boxes outward by a safety percentage (0–50%) so fast-moving faces, "
            "hair, or limbs near the edge of a detector box never poke outside the blur mask."
        )
        self.box_safety_padding_pct_label.setToolTip(self.box_safety_padding_pct_tooltip)
        self.box_safety_padding_pct_spinbox.setToolTip(self.box_safety_padding_pct_tooltip)
        self.box_safety_padding_pct_selection = create_qhbox_with_widgets(
            [self.box_safety_padding_pct_label, self.box_safety_padding_pct_spinbox]
        )

        # --- Render Widgets ---

        ############################################################################################################
        #   v Preview                                                                                              #
        ############################################################################################################
        self.preview_box = CollapsiblePanel("Preview")
        #
        #   [ ] Draw Boxes
        #
        self.draw_boxes_checkbox = QCheckBox("Draw Boxes")
        self.draw_boxes_tooltip = (
            "Show or hide bounding box outlines and ID/label tags in the video editor preview. "
            "This setting only affects the editor viewport and never draws boxes on the exported video."
        )
        self.draw_boxes_checkbox.setToolTip(self.draw_boxes_tooltip)
        self.box_border_width_label = QLabel("Box Border Width:")
        self.box_border_width_spinbox = create_int_spinbox(1, 10, 1, 2)
        self.box_border_width_tooltip = (
            "Adjust the line thickness (1–10 px) of bounding box borders in the editor preview. "
            "Useful for high-resolution 4K footage where thin borders are hard to see."
        )
        self.box_border_width_label.setToolTip(self.box_border_width_tooltip)
        self.box_border_width_spinbox.setToolTip(self.box_border_width_tooltip)
        self.box_border_width_selection = create_qhbox_with_widgets(
            [self.box_border_width_label, self.box_border_width_spinbox]
        )
        self.show_preview_mask_checkbox = QCheckBox("Show Mask")
        self.show_preview_mask_tooltip = (
            "Overlay a semi-transparent highlight showing the exact combined alpha mask footprint "
            "(including the 10-pixel outward feather zone) that will be blurred during video export."
        )
        self.show_preview_mask_checkbox.setToolTip(self.show_preview_mask_tooltip)
        self.preview_blur_checkbox = QCheckBox("Blur Preview")
        self.preview_blur_tooltip = (
            "Render the feathered Gaussian blur live in the editor preview. Only available when "
            "'Enable Blur' is turned on in the Render panel. Disabling this speeds up 4K playback "
            "in the editor while keeping blur active for the final export."
        )
        self.preview_blur_checkbox.setToolTip(self.preview_blur_tooltip)
        #
        #   v Render
        #
        self.render_box = CollapsiblePanel("Render")
        self.blur_checkbox = QCheckBox("Enable Blur")
        self.blur_tooltip = (
            "Master toggle to apply Gaussian blur over tracked bounding boxes when exporting the final "
            "video. Turning this on also unlocks the 'Blur Preview' toggle in the Preview panel."
        )
        self.blur_checkbox.setToolTip(self.blur_tooltip)
        #
        #   (Hidden by default)
        #               +----------------------------------------------------+
        # Blur strength:| 5.0                                      [ ^ | v ] |
        #               +----------------------------------------------------+
        self.blur_strength_label = QLabel("Blur Strength:")
        self.blur_strength_spinbox = create_blur_strength_spinbox(15.0)
        self.blur_strength_tooltip = (
            "Controls the Gaussian blur kernel size (sigma/radius) applied to redact subjects in the "
            "exported video (and in the live editor when 'Blur Preview' is active). Higher values "
            "produce stronger anonymization."
        )
        self.blur_strength_label.setToolTip(self.blur_strength_tooltip)
        self.blur_strength_spinbox.setToolTip(self.blur_strength_tooltip)
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
        """Arrange controls into independent collapsible sections.

        Note:
            Export actions remain in Render; editor-only controls are in Preview.

        Example:
            ```python
            panel._build_ui()
            ```
        """
        self.detection_box.add_layout(self.provider_selection)
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
        self.tracking_box.add_layout(self.reid_embedding_dim_selection)
        self.tracking_box.add_layout(self.min_iou_selection)
        self.tracking_box.add_layout(self.min_tracker_conf_selection)
        self.tracking_box.add_layout(self.decay_selection)
        self.tracking_box.add_widget(self.offline_stitching_checkbox)
        self.tracking_box.add_layout(self.max_stitch_gap_selection)
        self.tracking_box.add_layout(self.gsi_smoothness_selection)
        self.tracking_box.add_widget(self.track_btn)
        self.tracking_box.add_widget(self.imp_exp_tracks_button)
        self._reset_tracking_progress_bar()
        self.tracking_box.add_widget(self.tracking_progress_bar)

        self.privacy_features_box.add_widget(self.privacy_features_checkbox)
        self.privacy_features_box.add_widget(self.resist_box_shrinking_checkbox)
        self.privacy_features_box.add_layout(self.shrink_resistance_selection)
        self.privacy_features_box.add_layout(self.pre_detection_padding_sec_selection)
        self.privacy_features_box.add_layout(self.post_detection_padding_sec_selection)
        self.privacy_features_box.add_layout(self.box_safety_padding_pct_selection)
        self.set_privacy_controls_enabled(False, False)

        self.tracking_config_warning_label.setStyleSheet("color: #d9534f; font-weight: bold;")
        self.tracking_config_warning_label.setVisible(False)
        self.tracking_config_warning_label.setWordWrap(True)
        self.tracking_box.add_widget(self.tracking_config_warning_label)

        self.blur_strength_spinbox.setVisible(False)
        self.blur_strength_label.setVisible(False)

        self.preview_box.add_widget(self.draw_boxes_checkbox)
        self.preview_box.add_layout(self.box_border_width_selection)
        self.preview_box.add_widget(self.show_preview_mask_checkbox)
        self.preview_box.add_widget(self.preview_blur_checkbox)
        self.render_box.add_widget(self.blur_checkbox)
        self.render_box.add_layout(self.blur_strength_selection)
        self.render_box.add_widget(self.export_btn)
        self.render_box.add_widget(self.export_all_btn)

        # --- Final Assembly ---
        self._layout.addWidget(self.detection_box)
        self._layout.addWidget(self.tracking_box)
        self._layout.addWidget(self.privacy_features_box)
        self._layout.addWidget(self.preview_box)
        self._layout.addWidget(self.render_box)
        self._layout.addStretch()

    def _connect_signals(self) -> None:
        """Connect locally handled input signals to panel actions.

        Note:
            Session-setting updates are connected by TrackingHandler and ExportHandler.

        Example:
            ```python
            panel._connect_signals()
            ```
        """
        # Detection Panel
        self.provider_combo_box.currentIndexChanged.connect(self._on_provider_changed)
        self.model_combo_box.currentIndexChanged.connect(self._emit_model_changed)
        self.chosen_labels_edit.editingFinished.connect(self._emit_chosen_labels_changed)

        # Tracking Panel
        self.track_btn.clicked.connect(self._emit_start_tracking)
        self.tracking_strategy_combo_box.currentIndexChanged.connect(self._emit_tracking_strategy_changed)
        self.tracking_source_combo_box.currentIndexChanged.connect(self._emit_tracking_source_changed)
        self.reid_embedding_dim_combo_box.currentIndexChanged.connect(self._emit_reid_embedding_dim_changed)
        self.privacy_features_checkbox.toggled.connect(self._on_privacy_features_toggled)
        self.resist_box_shrinking_checkbox.toggled.connect(self._on_resist_box_shrinking_toggled)
        self.shrink_resistance_spinbox.valueChanged.connect(self.shrink_resistance_changed.emit)
        self.pre_detection_padding_sec_spinbox.valueChanged.connect(
            self.pre_detection_padding_sec_changed.emit
        )
        self.post_detection_padding_sec_spinbox.valueChanged.connect(
            self.post_detection_padding_sec_changed.emit
        )
        self.box_safety_padding_pct_spinbox.valueChanged.connect(
            self._emit_box_safety_padding_pct_changed
        )

    @Slot()
    def _emit_chosen_labels_changed(self) -> None:
        self.chosen_labels_changed.emit(self.chosen_labels_edit.text())

    @Slot()
    def _emit_model_changed(self) -> None:
        model_id: str = cast(str, self.model_combo_box.currentData())
        self.model_changed.emit(model_id)

    @Slot()
    def _on_provider_changed(self) -> None:
        self._active_provider_id = cast(
            str,
            self.provider_combo_box.currentData() or DETECTION_MODEL_PROVIDER_ALL,
        )
        self._apply_model_provider_filter(emit_model_signal=True)

    @Slot()
    def _emit_tracking_strategy_changed(self) -> None:
        strategy_id: str = cast(str, self.tracking_strategy_combo_box.currentData())
        self.tracking_strategy_changed.emit(strategy_id)

    @Slot()
    def _emit_tracking_source_changed(self) -> None:
        source_id: str = cast(str, self.tracking_source_combo_box.currentData())
        self.tracking_source_changed.emit(source_id)

    @Slot()
    def _emit_reid_embedding_dim_changed(self) -> None:
        dimension = cast(int, self.reid_embedding_dim_combo_box.currentData())
        self.reid_embedding_dim_changed.emit(dimension)

    @Slot()
    def _emit_start_tracking(self) -> None:
        strategy_id: str = cast(str, self.tracking_strategy_combo_box.currentData())
        source_id: str = cast(str, self.tracking_source_combo_box.currentData())
        self.start_tracking_requested.emit(strategy_id, source_id)

    def update_video_related_widgets_state(self, is_enabled: bool = False) -> None:
        """Enable or disable the video-dependent controls as a group.

        Args:
            is_enabled: Whether those controls should be enabled.
        """
        self._container.setEnabled(is_enabled)

    # --- Public API ---

    def restore_session_settings(self, vm: SessionSettingsViewModel) -> None:
        """Restore widgets from a session snapshot without emitting edits.

        Args:
            vm: Settings view model for the active session.

        Note:
            Signal blockers prevent session writes while restoring; dependent
            controls are enabled explicitly after values have been assigned.

        Example:
            ```python
            panel.restore_session_settings(session.settings.as_view_model())
            ```
        """
        self.set_selected_detection_model(vm.detection_model_name)

        with QSignalBlocker(self.tracking_strategy_combo_box):
            idx: int = self.tracking_strategy_combo_box.findData(vm.tracking_strategy)
            if idx >= 0:
                self.tracking_strategy_combo_box.setCurrentIndex(idx)

        self.set_iou_widgets_visible(vm.tracking_strategy == TrackingStrategy.HUNGARIAN)

        with QSignalBlocker(self.tracking_source_combo_box):
            idx: int = self.tracking_source_combo_box.findData(vm.tracking_source)
            if idx >= 0:
                self.tracking_source_combo_box.setCurrentIndex(idx)

        with QSignalBlocker(self.reid_embedding_dim_combo_box):
            idx = self.reid_embedding_dim_combo_box.findData(vm.reid_embedding_dim)
            if idx >= 0:
                self.reid_embedding_dim_combo_box.setCurrentIndex(idx)

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

        with QSignalBlocker(self.offline_stitching_checkbox):
            self.offline_stitching_checkbox.setChecked(vm.offline_stitching_enabled)
        with QSignalBlocker(self.max_stitch_gap_spinbox):
            self.max_stitch_gap_spinbox.setValue(vm.max_stitch_gap)
        with QSignalBlocker(self.gsi_smoothness_spinbox):
            self.gsi_smoothness_spinbox.setValue(vm.gsi_smoothness)

        with QSignalBlocker(self.privacy_features_checkbox):
            self.privacy_features_checkbox.setChecked(vm.privacy_features_enabled)
        with QSignalBlocker(self.resist_box_shrinking_checkbox):
            self.resist_box_shrinking_checkbox.setChecked(vm.resist_box_shrinking)
        with QSignalBlocker(self.shrink_resistance_spinbox):
            self.shrink_resistance_spinbox.setValue(vm.shrink_resistance)
        with QSignalBlocker(self.pre_detection_padding_sec_spinbox):
            self.pre_detection_padding_sec_spinbox.setValue(vm.pre_detection_padding_sec)
        with QSignalBlocker(self.post_detection_padding_sec_spinbox):
            self.post_detection_padding_sec_spinbox.setValue(vm.post_detection_padding_sec)
        with QSignalBlocker(self.box_safety_padding_pct_spinbox):
            self.box_safety_padding_pct_spinbox.setValue(vm.box_safety_padding_pct * 100.0)

        with QSignalBlocker(self.blur_strength_spinbox):
            self.blur_strength_spinbox.setValue(vm.blur_strength)

        with QSignalBlocker(self.draw_boxes_checkbox):
            self.draw_boxes_checkbox.setChecked(vm.draw_boxes)
        with QSignalBlocker(self.box_border_width_spinbox):
            self.box_border_width_spinbox.setValue(vm.box_border_width)
        with QSignalBlocker(self.show_preview_mask_checkbox):
            self.show_preview_mask_checkbox.setChecked(vm.show_preview_mask)
        with QSignalBlocker(self.preview_blur_checkbox):
            self.preview_blur_checkbox.setChecked(vm.preview_blur_enabled)

        with QSignalBlocker(self.blur_checkbox):
            self.blur_checkbox.setChecked(vm.blur_enabled)

        self.set_stitching_controls_enabled(vm.offline_stitching_enabled)
        self.set_privacy_controls_enabled(
            vm.privacy_features_enabled,
            vm.resist_box_shrinking,
        )
        self.set_blur_strength_visible(vm.blur_enabled)
        self.set_preview_blur_enabled(vm.blur_enabled)
        self.set_tracking_config_warning_visible(False)

    def set_iou_widgets_visible(self, visible: bool) -> None:
        """Show or hide the minimum-IoU label and spin box.

        Args:
            visible: Whether the controls should be visible.
        """
        self.min_iou_label.setVisible(visible)
        self.min_iou_spinbox.setVisible(visible)

    def set_blur_strength_visible(self, visible: bool) -> None:
        """Show or hide the blur-strength label and spin box.

        Args:
            visible: Whether the controls should be visible.
        """
        self.blur_strength_label.setVisible(visible)
        self.blur_strength_spinbox.setVisible(visible)

    def set_stitching_controls_enabled(self, enabled: bool) -> None:
        """Enable gap-bridging parameters only while offline stitching is active.

        Args:
            enabled: Whether the stitching checkbox is checked.

        Note:
            The checkbox remains enabled so users can turn stitching back on.

        Example:
            panel.set_stitching_controls_enabled(True)
        """
        self.max_stitch_gap_label.setEnabled(enabled)
        self.max_stitch_gap_spinbox.setEnabled(enabled)
        self.gsi_smoothness_label.setEnabled(enabled)
        self.gsi_smoothness_spinbox.setEnabled(enabled)

    def set_privacy_controls_enabled(
        self,
        privacy_enabled: bool,
        resist_shrinking: bool,
    ) -> None:
        """Enable privacy options according to the master and anti-shrink toggles.

        Args:
            privacy_enabled: Whether the Privacy Shield is active.
            resist_shrinking: Whether anti-shrink behavior is selected.

        Note:
            The master checkbox remains interactive. Shrink resistance requires
            both toggles, while temporal padding and safety margin require only
            the master toggle.

        Example:
            panel.set_privacy_controls_enabled(True, True)
        """
        self.resist_box_shrinking_checkbox.setEnabled(privacy_enabled)
        shrink_enabled = privacy_enabled and resist_shrinking
        self.shrink_resistance_label.setEnabled(shrink_enabled)
        self.shrink_resistance_spinbox.setEnabled(shrink_enabled)
        for label, spinbox in (
            (self.pre_detection_padding_sec_label, self.pre_detection_padding_sec_spinbox),
            (self.post_detection_padding_sec_label, self.post_detection_padding_sec_spinbox),
            (self.box_safety_padding_pct_label, self.box_safety_padding_pct_spinbox),
        ):
            label.setEnabled(privacy_enabled)
            spinbox.setEnabled(privacy_enabled)

    @Slot(bool)
    def _on_privacy_features_toggled(self, enabled: bool) -> None:
        """Update child-control enablement and emit the master setting change.

        Args:
            enabled: New Privacy Shield state.

        Example:
            panel._on_privacy_features_toggled(True)
        """
        self.set_privacy_controls_enabled(
            enabled,
            self.resist_box_shrinking_checkbox.isChecked(),
        )
        self.privacy_features_enabled_changed.emit(enabled)

    @Slot(bool)
    def _on_resist_box_shrinking_toggled(self, enabled: bool) -> None:
        """Update shrink-control enablement and emit the anti-shrink setting.

        Args:
            enabled: New anti-shrink state.

        Example:
            panel._on_resist_box_shrinking_toggled(True)
        """
        self.set_privacy_controls_enabled(
            self.privacy_features_checkbox.isChecked(),
            enabled,
        )
        self.resist_box_shrinking_changed.emit(enabled)

    @Slot(float)
    def _emit_box_safety_padding_pct_changed(self, value: float) -> None:
        """Emit the UI percentage as a proportional setting value.

        Args:
            value: Percentage displayed in the 0–50 range.

        Example:
            panel._emit_box_safety_padding_pct_changed(10.0)
        """
        self.box_safety_padding_pct_changed.emit(value / 100.0)

    def set_preview_blur_enabled(self, enabled: bool) -> None:
        """Gate live preview blur on the Render panel's master blur setting.

        Args:
            enabled: Whether export blur is enabled.

        Note:
            Disabling the master does not alter `preview_blur_enabled`; it only
            disables the control and preview rendering.

        Example:
            panel.set_preview_blur_enabled(False)
        """
        self.preview_blur_checkbox.setEnabled(enabled)

    def set_tracking_config_warning_visible(self, visible: bool) -> None:
        """Show or hide the tracking configuration warning.

        Args:
            visible: Whether the warning label should be visible.
        """
        self.tracking_config_warning_label.setVisible(visible)

    def set_detection_loading_state(self, is_loading: bool) -> None:
        """Disable detection controls and show the model-loading spinner while loading.

Args:
    is_loading: Whether a detection model is currently loading.
"""
        self.model_combo_box.setEnabled(not is_loading)
        self.detect_btn.setEnabled(not is_loading)
        self.detect_all_btn.setEnabled(not is_loading)
        self.imp_exp_detections_button.setEnabled(not is_loading)
        if is_loading:
            self.model_loading_spinner.start("Loading model")
        else:
            self.model_loading_spinner.stop()

    def set_tracking_loading_state(self, is_loading: bool) -> None:
        """Disable tracking controls while the tracking worker is running.

        Args:
            is_loading: Whether tracking is currently loading or running.
        """
        self.track_btn.setEnabled(not is_loading)
        self.imp_exp_tracks_button.setEnabled(not is_loading)
        self.tracking_strategy_combo_box.setEnabled(not is_loading)
        self.tracking_source_combo_box.setEnabled(not is_loading)

    def set_detection_progress_busy(self, is_busy: bool) -> None:
        """Show or hide detection progress and reset it when work starts.

        Args:
            is_busy: Whether detection work is active.
        """
        self.detection_progress_bar.setVisible(is_busy)
        if is_busy:
            self._reset_detection_progress_bar()

    def set_detection_progress(self, current: int, total: int, label: str = "Detection", eta_msecs: float | None = None) -> None:
        """Display detection completion percentage and optional elapsed-time estimate.

        Args:
            current: Number of items completed.
            total: Total number of items; values below one use a denominator of one.
            label: Prefix shown in the progress-bar text.
            eta_msecs: Optional remaining-time estimate in milliseconds.
        """
        maximum = max(total, 1)
        percent = (current / maximum) * 100
        percent_formatted = f"{percent:.2f} %"
        self.detection_progress_bar.setRange(0, 100)
        self.detection_progress_bar.setValue(int(max(0, min(percent, 100))))
        if eta_msecs is not None:
            eta_seconds = int(eta_msecs // 1000)
            eta_formatted = f"{eta_seconds // 3600:02d}:{eta_seconds % 3600 // 60:02d}:{eta_seconds % 60:02d}"
            self.detection_progress_bar.setFormat(f"{label}: {percent_formatted} [ {eta_formatted} ]")
        else:
            self.detection_progress_bar.setFormat(f"{label}: {percent_formatted}")

    def set_tracking_progress_busy(self, is_busy: bool, indeterminate: bool = False) -> None:
        """Show tracking progress, selecting indeterminate or initial determinate mode.

        Args:
            is_busy: Whether tracking work is active.
            indeterminate: Whether to use Qt's continuously animated busy indicator.
        """
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
        """Display the completed/total tracking count and corresponding percentage.

        Args:
            current: Number of items completed.
            total: Total number of items; values below one use a denominator of one.
            label: Prefix shown in the progress-bar text.
        """
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
        """Replace the available detection models and refresh the provider-filtered list.

        Args:
            boxes: Model choices to make available in the detection model selector.
        """
        self._all_detection_models = list(boxes)
        self._apply_model_provider_filter(emit_model_signal=False)

    def _apply_model_provider_filter(
        self,
        *,
        selected_model_id: str | None = None,
        emit_model_signal: bool,
    ) -> None:
        previous_model_id = cast(str | None, self.model_combo_box.currentData())
        target_model_id = selected_model_id or previous_model_id or "None"
        filtered = [
            item
            for item in self._all_detection_models
            if item.model_id == "None"
            or self._active_provider_id == DETECTION_MODEL_PROVIDER_ALL
            or item.provider_id == self._active_provider_id
        ]
        if not filtered:
            filtered = list(self._all_detection_models)

        with QSignalBlocker(self.model_combo_box):
            self.model_combo_box.clear()
            for item in filtered:
                self.model_combo_box.addItem(item.display_name, item.model_id)
            target_index = self.model_combo_box.findData(target_model_id)
            if target_index < 0:
                target_index = self.model_combo_box.findData("None")
            if target_index < 0 and self.model_combo_box.count() > 0:
                target_index = 0
            if target_index >= 0:
                self.model_combo_box.setCurrentIndex(target_index)

        current_model_id = cast(str | None, self.model_combo_box.currentData())
        if emit_model_signal and current_model_id and current_model_id != previous_model_id:
            self.model_changed.emit(current_model_id)

    def set_selected_detection_model(self, model_id: str) -> None:
        """Select the model's provider and model entry without emitting a model-change signal.

        Args:
            model_id: Model identifier, or `"None"` to select the all-providers entry.
        """
        provider_id = (
            DETECTION_MODEL_PROVIDER_ALL
            if model_id == "None"
            else resolve_detection_model_provider(model_id)
        )
        with QSignalBlocker(self.provider_combo_box):
            provider_index = self.provider_combo_box.findData(provider_id)
            if provider_index >= 0:
                self.provider_combo_box.setCurrentIndex(provider_index)
        self._active_provider_id = provider_id
        self._apply_model_provider_filter(selected_model_id=model_id, emit_model_signal=False)

    def connect_signals_to_export_handler(self, export_handler: ExportHandler) -> None:
        """Connect preview/render and export actions to the export handler.

        Args:
            export_handler: Handler updating session settings and starting exports.

        Note:
            Preview-only changes re-render the editor but do not affect export pixels.

        Example:
            panel.connect_signals_to_export_handler(handler)
        """
        self.export_btn.clicked.connect(export_handler.on_export)
        self.export_all_btn.clicked.connect(export_handler.on_export_all)
        self.export_all_action.triggered.connect(export_handler.on_export_all)
        self.draw_boxes_checkbox.toggled.connect(export_handler.on_draw_boxes_changed)
        self.box_border_width_spinbox.valueChanged.connect(export_handler.on_box_border_width_changed)
        self.show_preview_mask_checkbox.toggled.connect(export_handler.on_show_preview_mask_changed)
        self.preview_blur_checkbox.toggled.connect(export_handler.on_preview_blur_changed)
        self.blur_checkbox.toggled.connect(export_handler.on_blur_toggled)
        self.blur_strength_spinbox.valueChanged.connect(export_handler.on_blur_strength_changed)
