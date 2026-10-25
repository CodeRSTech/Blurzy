from __future__ import annotations

from types import SimpleNamespace

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPalette
from PySide6.QtWidgets import QApplication, QPushButton

from app.shared.app_preferences import AppPreferences
from app.domain.detection import BoxSource
from app.domain.views import BBoxViewModel
from app.ui.qt.dialogs.preferences import PreferencesDialog
from app.ui.qt.sections.bottom_data_panel import BottomDataPanelContainer
from app.ui.qt.sections.right_panel import RightControlPanel
from app.ui.qt.shared.theme import apply_application_theme
from app.ui.qt.widgets.color_swatch_delegate import COLOR_SWATCH_ROLE, ColorSwatchDelegate
from app.ui.qt.widgets.preview.preview_container import PreviewContainer

pytestmark = pytest.mark.skipif(not isinstance(QApplication, type), reason="Requires a real PySide6 installation")


def test_default_theme_setting_round_trips_through_preferences_dialog(qtbot) -> None:
    dialog = PreferencesDialog(AppPreferences(), available_models=[])
    qtbot.addWidget(dialog)

    assert dialog._theme_combo_box.currentData() == "system"
    dialog._theme_combo_box.setCurrentIndex(dialog._theme_combo_box.findData("dark"))
    assert dialog.get_preferences().default_theme == "dark"


def test_color_column_renders_a_swatch_and_keeps_hex_accessible(qtbot) -> None:
    panel = BottomDataPanelContainer()
    qtbot.addWidget(panel)
    panel.resize(900, 360)
    table = panel.detection_tab_frame_data_table
    box = SimpleNamespace(
        id="box-1",
        key="box-key",
        source="Detection",
        label="person",
        confidence_txt="0.92",
        bbox_txt="(10, 20), (100, 200)",
        color_hex="#12ab34",
    )
    BottomDataPanelContainer.set_data_table_boxes([box], table, set())
    panel.show()
    qtbot.wait(20)
    table.scrollToItem(table.item(0, 5))

    color_item = table.item(0, 5)
    assert color_item.text() == ""
    assert color_item.data(COLOR_SWATCH_ROLE) == "#12ab34"
    assert color_item.toolTip() == "Color: #12ab34"
    assert isinstance(table.itemDelegateForColumn(5), ColorSwatchDelegate)
    assert table.columnWidth(5) == 56

    image = QImage(table.viewport().size(), QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    table.viewport().render(painter, QPoint())
    painter.end()
    x = table.columnViewportPosition(5) + table.columnWidth(5) // 2
    y = table.rowViewportPosition(0) + table.rowHeight(0) // 2
    assert image.pixelColor(x, y) == QColor("#12ab34")


def test_annotation_action_buttons_use_compact_accessible_icons(qtbot) -> None:
    panel = BottomDataPanelContainer()
    qtbot.addWidget(panel)

    buttons = (
        panel.edit_box_btn,
        panel.relabel_box_btn,
        panel.delete_box_btn,
        panel.delete_next_occurrences_btn,
        panel.delete_prev_occurrences_btn,
        panel.copy_to_prev_btn,
        panel.copy_to_next_btn,
    )
    assert all(button.text() == "" for button in buttons)
    assert all(not button.icon().isNull() for button in buttons)
    assert all(button.toolTip() == button.accessibleName() for button in buttons)
    assert all(button.height() <= 28 for button in buttons)


def test_explicit_theme_updates_palette_and_stylesheet(qtbot) -> None:
    application = QApplication.instance()
    assert application is not None
    try:
        apply_application_theme(application, "dark")
        assert application.palette().color(QPalette.ColorRole.Window).name() == "#171a20"
        assert 'QPushButton[emphasis="primary"]' in application.styleSheet()

        apply_application_theme(application, "light")
        assert application.palette().color(QPalette.ColorRole.Window).name() == "#f3f5f8"
    finally:
        apply_application_theme(application, "system")


def test_right_panel_fits_compact_desktop_width_without_horizontal_scrolling(qtbot) -> None:
    application = QApplication.instance()
    assert application is not None
    apply_application_theme(application, "dark")
    panel = RightControlPanel()
    qtbot.addWidget(panel)
    panel.resize(320, 760)
    panel.show()
    qtbot.wait(20)

    assert panel.widget().width() <= panel.viewport().width()
    assert panel.widget().minimumSizeHint().width() <= panel.viewport().width()
    assert panel.horizontalScrollBar().maximum() == 0
    assert panel.detect_btn.text() == "Detect Frame"
    assert panel.detect_all_btn.text() == "Detect All Frames"
    assert panel.provider_combo_box.x() == panel.min_confidence_spinbox.x()
    assert panel.model_combo_box.x() == panel.min_confidence_spinbox.x()
    assert panel.detect_btn.y() == panel.detect_all_btn.y()
    assert panel.track_btn.y() == panel.imp_exp_tracks_button.y()

    apply_application_theme(application, "system")


def test_empty_preview_open_video_action_emits_request(qtbot) -> None:
    preview = PreviewContainer()
    qtbot.addWidget(preview)
    preview.set_message("Select a video to continue.")
    assert preview._empty_state_message.text() == "Select a video to continue."
    assert preview.video_layer._placeholder_text == ""
    assert not preview.empty_state_layer.isHidden()

    preview.set_image(QImage(4, 4, QImage.Format.Format_RGB32))
    assert preview.empty_state_layer.isHidden()
    assert preview._layout.currentWidget() is preview.bbox_layer

    preview.set_message("Video closed.")
    assert not preview.empty_state_layer.isHidden()

    button = preview.empty_state_layer.findChild(QPushButton)
    assert button is not None

    with qtbot.waitSignal(preview.open_video_requested):
        button.click()


def test_preview_annotations_remain_readable_independently_of_source_resolution(qtbot) -> None:
    preview = PreviewContainer()
    qtbot.addWidget(preview)
    preview.resize(960, 540)
    preview.show()
    outline_samples = []

    for width, height in ((640, 360), (1920, 1080), (3840, 2160)):
        image = QImage(width, height, QImage.Format.Format_RGB32)
        image.fill(Qt.GlobalColor.white)
        box = BBoxViewModel(
            id="person-1",
            source=BoxSource.DETECTION,
            label="person",
            bbox_xyxy=(width // 4, height // 4, width * 3 // 4, height * 3 // 4),
            color_hex="#00ff00",
            confidence=0.9,
            key="box-1",
        )
        preview.set_annotations([box])
        preview.set_image(image)
        qtbot.wait(10)

        rect = preview.bbox_layer._image_rect_to_widget_space(*box.bbox_xyxy)
        rendered = QImage(preview.bbox_layer.size(), QImage.Format.Format_ARGB32)
        rendered.fill(Qt.GlobalColor.transparent)
        painter = QPainter(rendered)
        preview.bbox_layer.render(painter, QPoint())
        painter.end()
        sample = [
            rendered.pixelColor(rect.left() + offset, rect.center().y()).name()
            for offset in range(-5, 6)
        ]
        outline_samples.append(sample)
        assert sample.count("#00ff00") >= 2
        assert rendered.pixelColor(rect.left() + 4, rect.top() - 4).name() == "#151a22"
        assert image.pixelColor(width // 4, height // 4) == QColor(Qt.GlobalColor.white)

    assert outline_samples[0] == outline_samples[1] == outline_samples[2]

    preview.set_annotations([])
    assert not preview.bbox_layer._annotations


def test_intersecting_box_outlines_do_not_cross_captions(qtbot) -> None:
    preview = PreviewContainer()
    qtbot.addWidget(preview)
    preview.resize(960, 540)
    image = QImage(960, 540, QImage.Format.Format_RGB32)
    image.fill(Qt.GlobalColor.white)
    preview.set_image(image)
    preview.set_annotations([
        BBoxViewModel(
            id="first", source=BoxSource.DETECTION, label="person",
            bbox_xyxy=(200, 200, 600, 500), color_hex="#00ff00", confidence=0.9, key="first",
        ),
        BBoxViewModel(
            id="second", source=BoxSource.DETECTION, label="person",
            bbox_xyxy=(240, 100, 500, 400), color_hex="#ff0000", confidence=0.8, key="second",
        ),
    ])
    preview.show()
    qtbot.wait(10)
    rendered = QImage(preview.bbox_layer.size(), QImage.Format.Format_ARGB32)
    rendered.fill(Qt.GlobalColor.transparent)
    painter = QPainter(rendered)
    preview.bbox_layer.render(painter, QPoint())
    painter.end()

    first = preview.bbox_layer._image_rect_to_widget_space(200, 200, 600, 500)
    second = preview.bbox_layer._image_rect_to_widget_space(240, 100, 500, 400)
    assert rendered.pixelColor(second.left(), first.top() - 3).name() == "#151a22"
