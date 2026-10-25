from __future__ import annotations

from types import SimpleNamespace

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPalette
from PySide6.QtWidgets import QApplication, QPushButton

from app.shared.app_preferences import AppPreferences
from app.ui.qt.dialogs.preferences import PreferencesDialog
from app.ui.qt.sections.bottom_data_panel import BottomDataPanelContainer
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


def test_empty_preview_open_video_action_emits_request(qtbot) -> None:
    preview = PreviewContainer()
    qtbot.addWidget(preview)
    preview.set_message("Select a video to continue.")
    assert preview._empty_state_message.text() == "Select a video to continue."
    button = preview.empty_state_layer.findChild(QPushButton)
    assert button is not None

    with qtbot.waitSignal(preview.open_video_requested):
        button.click()
