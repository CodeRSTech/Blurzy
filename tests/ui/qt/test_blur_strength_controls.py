from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication

from app.domain.views import SessionSettingsViewModel
from app.shared.app_preferences import AppPreferences
from app.ui.qt.dialogs.preferences import PreferencesDialog
from app.ui.qt.sections.right_panel import RightControlPanel

pytestmark = pytest.mark.skipif(
    not isinstance(QApplication, type), reason="Requires a real PySide6 installation"
)


def test_preferences_form_scrolls_with_buttons_visible(qtbot):
    dialog = PreferencesDialog(AppPreferences(), available_models=[])
    qtbot.addWidget(dialog)
    dialog.resize(600, 480)
    dialog.show()

    qtbot.waitUntil(lambda: dialog._scroll_area.verticalScrollBar().maximum() > 0)

    assert dialog._button_box.isVisible()
    assert dialog._button_box.geometry().bottom() <= dialog.rect().height()
    assert dialog.maximumHeight() <= int(dialog.screen().availableGeometry().height() * 0.9)


@pytest.mark.parametrize("strength", [15.0, 101.0, 255.0])
def test_render_panel_restores_higher_blur_strength_without_clamping(qtbot, strength):
    panel = RightControlPanel()
    qtbot.addWidget(panel)

    panel.restore_session_settings(
        SessionSettingsViewModel(blur_enabled=True, blur_strength=strength)
    )

    assert panel.blur_strength_spinbox.minimum() == 0.0
    assert panel.blur_strength_spinbox.maximum() == 255.0
    assert panel.blur_strength_spinbox.value() == strength
    assert panel.blur_strength_spinbox.singleStep() == 1.0
    assert panel.blur_strength_spinbox.decimals() == 2


@pytest.mark.parametrize("strength", [51.0, 101.0, 255.0])
def test_preferences_round_trips_higher_blur_strength(qtbot, strength):
    dialog = PreferencesDialog(
        AppPreferences(default_blur_enabled=True, default_blur_strength=strength),
        available_models=[],
    )
    qtbot.addWidget(dialog)

    assert dialog._blur_strength_spinbox.minimum() == 0.0
    assert dialog._blur_strength_spinbox.maximum() == 255.0
    assert dialog._blur_strength_spinbox.value() == strength
    assert dialog.get_preferences().default_blur_strength == strength


def test_both_controls_allow_selecting_the_maximum(qtbot):
    panel = RightControlPanel()
    dialog = PreferencesDialog(AppPreferences(default_blur_enabled=True), available_models=[])
    qtbot.addWidget(panel)
    qtbot.addWidget(dialog)

    panel.blur_strength_spinbox.setValue(255.0)
    dialog._blur_strength_spinbox.setValue(255.0)

    assert panel.blur_strength_spinbox.value() == 255.0
    assert dialog.get_preferences().default_blur_strength == 255.0


def test_tracking_preview_and_render_controls_restore_bounds_tooltips_and_dependencies(qtbot):
    panel = RightControlPanel()
    qtbot.addWidget(panel)

    panel.restore_session_settings(
        SessionSettingsViewModel(
            offline_stitching_enabled=False,
            max_stitch_gap=40,
            gsi_smoothness=12.0,
            box_border_width=7,
            show_preview_mask=True,
            preview_blur_enabled=True,
            blur_enabled=False,
        )
    )

    assert panel.offline_stitching_checkbox.text() == "Bridge & Smooth Gaps (GSI)"
    assert panel.max_stitch_gap_spinbox.minimum() == 1
    assert panel.max_stitch_gap_spinbox.maximum() == 60
    assert panel.max_stitch_gap_spinbox.value() == 40
    assert panel.gsi_smoothness_spinbox.minimum() == 1.0
    assert panel.gsi_smoothness_spinbox.maximum() == 30.0
    assert panel.gsi_smoothness_spinbox.value() == 12.0
    assert panel.box_border_width_spinbox.minimum() == 1
    assert panel.box_border_width_spinbox.maximum() == 10
    assert panel.box_border_width_spinbox.value() == 7
    assert panel.show_preview_mask_checkbox.isChecked()
    assert panel.preview_blur_checkbox.isChecked()
    assert panel.preview_blur_checkbox.isEnabled() is False
    assert panel.max_stitch_gap_spinbox.isEnabled() is False
    assert panel.gsi_smoothness_spinbox.isEnabled() is False
    assert panel.blur_strength_spinbox.isHidden()

    for widget in (
        panel.offline_stitching_checkbox,
        panel.max_stitch_gap_label,
        panel.max_stitch_gap_spinbox,
        panel.gsi_smoothness_label,
        panel.gsi_smoothness_spinbox,
        panel.confidence_decay_label,
        panel.confidence_decay_spinbox,
        panel.draw_boxes_checkbox,
        panel.box_border_width_label,
        panel.box_border_width_spinbox,
        panel.show_preview_mask_checkbox,
        panel.preview_blur_checkbox,
        panel.blur_checkbox,
        panel.blur_strength_label,
        panel.blur_strength_spinbox,
    ):
        assert widget.toolTip()

    assert panel.preview_box is not panel.render_box
    assert panel.draw_boxes_checkbox.toolTip().startswith("Show or hide")
    assert panel.blur_checkbox.toolTip().startswith("Master toggle")

    panel.restore_session_settings(SessionSettingsViewModel(blur_enabled=True))
    assert panel.preview_blur_checkbox.isEnabled() is True


def test_preferences_round_trip_new_tracking_and_preview_defaults(qtbot):
    preferences = AppPreferences(
        default_offline_stitching_enabled=False,
        default_max_stitch_gap=50,
        default_gsi_smoothness=21.0,
        default_box_border_width=8,
        default_show_preview_mask=True,
        default_preview_blur_enabled=True,
        default_blur_enabled=True,
    )
    dialog = PreferencesDialog(preferences, available_models=[])
    qtbot.addWidget(dialog)

    restored = dialog.get_preferences()

    assert restored.default_offline_stitching_enabled is False
    assert restored.default_max_stitch_gap == 50
    assert restored.default_gsi_smoothness == 21.0
    assert restored.default_box_border_width == 8
    assert restored.default_show_preview_mask is True
    assert restored.default_preview_blur_enabled is True
    assert dialog._preview_blur_enabled_checkbox.isEnabled() is True


def test_reid_controls_restore_dimensions_and_emit_changes(qtbot):
    panel = RightControlPanel()
    qtbot.addWidget(panel)
    emitted_dimensions = []
    panel.reid_embedding_dim_changed.connect(emitted_dimensions.append)

    panel.restore_session_settings(SessionSettingsViewModel(tracking_strategy="botsort", reid_embedding_dim=512))

    assert panel.tracking_strategy_combo_box.currentData() == "botsort"
    assert panel.reid_embedding_dim_combo_box.currentData() == 512
    assert emitted_dimensions == []
    assert panel.reid_embedding_dim_combo_box.count() == 3
    assert panel.reid_embedding_dim_label.text() == "Re-ID Embedding Size"
    assert [panel.reid_embedding_dim_combo_box.itemText(i) for i in range(3)] == [
        "128 (Fast)",
        "256 (Balanced)",
        "512 (High Precision)",
    ]
    assert panel.reid_embedding_dim_combo_box.toolTip()
    assert panel.reid_embedding_dim_label.toolTip()
    assert panel.strategy_label.toolTip()
    assert panel.reid_embedding_dim_combo_box.toolTip() == panel.reid_embedding_dim_tooltip
    assert panel.tracking_strategy_combo_box.toolTip() == panel.strategy_tooltip
    assert panel.tracking_strategy_combo_box.findData("botsort") >= 0

    panel.reid_embedding_dim_combo_box.setCurrentIndex(0)
    assert emitted_dimensions == [128]


def test_preferences_include_botsort_and_restore_reid_dimension(qtbot):
    dialog = PreferencesDialog(
        AppPreferences(default_tracking_strategy="botsort", default_reid_embedding_dim=512),
        available_models=[],
    )
    qtbot.addWidget(dialog)

    assert dialog._tracking_strategy_combo_box.currentData() == "botsort"
    assert dialog._tracking_strategy_combo_box.findData("botsort") >= 0
    assert dialog._reid_embedding_dim_combo_box.currentData() == 512
    assert dialog._reid_embedding_dim_label.toolTip()
    assert dialog._reid_embedding_dim_combo_box.toolTip()

    dialog._reid_embedding_dim_combo_box.setCurrentIndex(0)
    assert dialog.get_preferences().default_reid_embedding_dim == 128


def test_privacy_features_controls_restore_tooltips_ranges_and_enablement(qtbot):
    panel = RightControlPanel()
    qtbot.addWidget(panel)
    emitted_master = []
    emitted_safety_margin = []
    panel.privacy_features_enabled_changed.connect(emitted_master.append)
    panel.box_safety_padding_pct_changed.connect(emitted_safety_margin.append)

    panel.restore_session_settings(
        SessionSettingsViewModel(
            privacy_features_enabled=True,
            resist_box_shrinking=False,
            shrink_resistance=0.65,
            pre_detection_padding_sec=1.2,
            post_detection_padding_sec=2.3,
            box_safety_padding_pct=0.2,
        )
    )

    assert panel.privacy_features_box.toggle_button.text().endswith("Privacy Features")
    assert panel.privacy_features_checkbox.isChecked()
    assert panel.resist_box_shrinking_checkbox.isChecked() is False
    assert panel.resist_box_shrinking_checkbox.isEnabled()
    assert panel.shrink_resistance_spinbox.value() == 0.65
    assert panel.pre_detection_padding_sec_spinbox.value() == 1.2
    assert panel.post_detection_padding_sec_spinbox.value() == 2.3
    assert panel.box_safety_padding_pct_spinbox.value() == 20.0
    assert panel.box_safety_padding_pct_spinbox.maximum() == 50.0
    assert panel.shrink_resistance_spinbox.isEnabled() is False
    assert panel.pre_detection_padding_sec_spinbox.isEnabled()
    assert panel.post_detection_padding_sec_spinbox.isEnabled()
    assert panel.box_safety_padding_pct_spinbox.isEnabled()

    controls = (
        panel.privacy_features_checkbox,
        panel.resist_box_shrinking_checkbox,
        panel.shrink_resistance_label,
        panel.shrink_resistance_spinbox,
        panel.pre_detection_padding_sec_label,
        panel.pre_detection_padding_sec_spinbox,
        panel.post_detection_padding_sec_label,
        panel.post_detection_padding_sec_spinbox,
        panel.box_safety_padding_pct_label,
        panel.box_safety_padding_pct_spinbox,
    )
    assert all(control.toolTip() for control in controls)
    assert panel.min_tracker_confidence_spinbox.minimum() == 0.1
    assert panel.min_tracker_confidence_spinbox.maximum() == 0.5
    assert panel.min_tracker_confidence_spinbox.value() == 0.1
    panel.box_safety_padding_pct_spinbox.setValue(25.0)
    assert emitted_safety_margin == [0.25]

    panel.resist_box_shrinking_checkbox.setChecked(True)
    assert panel.shrink_resistance_spinbox.isEnabled()
    panel.privacy_features_checkbox.setChecked(False)
    assert emitted_master == [False]
    assert not panel.resist_box_shrinking_checkbox.isEnabled()
    assert not panel.shrink_resistance_spinbox.isEnabled()
    assert not panel.pre_detection_padding_sec_spinbox.isEnabled()
    assert not panel.post_detection_padding_sec_spinbox.isEnabled()
    assert not panel.box_safety_padding_pct_spinbox.isEnabled()


def test_privacy_settings_round_trip_through_processing_settings():
    from app.domain.export import ProcessingSettings

    settings = ProcessingSettings(
        privacy_features_enabled=True,
        resist_box_shrinking=False,
        shrink_resistance=0.7,
        pre_detection_padding_sec=1.0,
        post_detection_padding_sec=2.0,
        box_safety_padding_pct=0.25,
    )
    view_model = settings.as_view_model()

    assert view_model.privacy_features_enabled is True
    assert view_model.resist_box_shrinking is False
    assert view_model.shrink_resistance == 0.7
    assert view_model.pre_detection_padding_sec == 1.0
    assert view_model.post_detection_padding_sec == 2.0
    assert view_model.box_safety_padding_pct == 0.25
