from __future__ import annotations

from dataclasses import asdict
from types import SimpleNamespace
from unittest.mock import MagicMock

import numpy as np
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QTableWidget

from app.domain import SessionId, VideoDataLayer, VideoDataLayerGroup
from app.domain.detection import BoxSource
from app.domain.views import BBoxViewModel, SessionSettingsViewModel
from app.shared.masked_blur import apply_masked_blur, compute_blur_alpha_mask, overlay_alpha_mask
from app.ui.handlers import ui_handler as ui_handler_module
from app.ui.handlers.ui_handler import UIHandler
from app.ui.qt.sections.bottom_data_panel import BottomDataPanelContainer
from app.ui.qt.widgets.preview.preview_container import PreviewContainer
from app.ui.view_state.bbox_selection_state import BBoxSelectionState

pytestmark = pytest.mark.skipif(
    not isinstance(QApplication, type), reason="Requires a real PySide6 installation"
)


@pytest.mark.parametrize("tab", [VideoDataLayerGroup.DETECTION, VideoDataLayerGroup.TRACKING])
@pytest.mark.parametrize("populated", [False, True])
@pytest.mark.parametrize(
    "blur_enabled,preview_blur_enabled,show_preview_mask",
    [
        (False, False, False),
        (False, True, False),
        (True, False, False),
        (True, True, False),
        (False, False, True),
        (True, True, True),
    ],
)
def test_outline_toggle_preserves_tables_selection_and_render_settings(
    qtbot, monkeypatch, tab, populated, blur_enabled, preview_blur_enabled, show_preview_mask
):
    table = QTableWidget(1, 6)
    preview = PreviewContainer()
    qtbot.addWidget(table)
    qtbot.addWidget(preview)
    box = BBoxViewModel(
        id="box-1", source=BoxSource.DETECTION, label="person",
        bbox_xyxy=(16, 16, 48, 48), color_hex="#00FF00", confidence=0.9, key="box-key",
    )
    boxes = [box] if populated else []
    selection = BBoxSelectionState()
    selection.set_selection([box.key] if populated else [])
    selected_keys = selection.get_selected_keys()
    settings = SessionSettingsViewModel(
        blur_enabled=blur_enabled,
        preview_blur_enabled=preview_blur_enabled,
        show_preview_mask=show_preview_mask,
        box_border_width=3,
    )
    original_settings = asdict(settings)
    session = SimpleNamespace(
        state=SimpleNamespace(settings=settings, playback=SimpleNamespace(current_frame_index=7)),
        data=SimpleNamespace(
            has_boxes_for_layer=MagicMock(return_value=False),
            get_boxes_for_layer_at_frame_index_as_list=MagicMock(return_value=boxes),
        ),
    )
    s_id = SessionId("sample.mp4")
    app = SimpleNamespace(
        get_session_by_id=MagicMock(return_value=session),
        get_tab_frame_boxes_for_session_id=MagicMock(
            return_value=SimpleNamespace(frame_data_boxes=boxes)
        ),
    )
    populate_table = MagicMock(
        side_effect=lambda frame_boxes, active_tab: BottomDataPanelContainer.set_data_table_boxes(
            frame_boxes, table, set(selection.get_selected_keys())
        )
    )
    window = SimpleNamespace(
        active_tab_index=tab,
        preview_container=preview,
        selected_frame_box_keys=selected_keys,
        bottom_panel=SimpleNamespace(set_data_boxes_for_tab=populate_table),
    )
    handler = UIHandler(SimpleNamespace(window=window, app=app))
    logger = MagicMock()
    monkeypatch.setattr(ui_handler_module, "logger", logger)
    blur = MagicMock(wraps=ui_handler_module.apply_masked_blur)
    mask = MagicMock(wraps=ui_handler_module.compute_blur_alpha_mask)
    convert_image = MagicMock(wraps=ui_handler_module.rgb_frame_to_q_image)
    monkeypatch.setattr(ui_handler_module, "apply_masked_blur", blur)
    monkeypatch.setattr(ui_handler_module, "compute_blur_alpha_mask", mask)
    monkeypatch.setattr(ui_handler_module, "rgb_frame_to_q_image", convert_image)
    frame = np.random.default_rng(0).integers(0, 256, (64, 64, 3), dtype=np.uint8)
    original_frame = frame.copy()
    table_snapshots = []
    display_annotations = MagicMock(wraps=preview.set_annotations)
    monkeypatch.setattr(preview, "set_annotations", display_annotations)

    for draw_boxes in (True, False, True):
        settings.draw_boxes = draw_boxes
        handler._draw_boxes_on_frame_for_session_id(s_id, frame)

        populate_table.assert_called_with(boxes, tab)
        app.get_tab_frame_boxes_for_session_id.assert_called_with(s_id, tab)
        session.data.get_boxes_for_layer_at_frame_index_as_list.assert_called_with(VideoDataLayer.C, 7)
        assert table.rowCount() == len(boxes)
        table_snapshots.append([
            [table.item(row, column).text() for column in range(table.columnCount())]
            for row in range(table.rowCount())
        ])
        assert table_snapshots[-1] == table_snapshots[0]
        if populated:
            assert table.item(0, 0).text() == box.id
            assert table.item(0, 0).data(Qt.ItemDataRole.UserRole) == box.key
            assert table.item(0, 2).text() == box.label
            assert table.item(0, 0).isSelected()
        assert selection.get_selected_keys() == selected_keys
        assert preview.bbox_layer._active_bboxes == (
            {box.key: box.bbox_xyxy} if draw_boxes and populated else {}
        )
        assert preview.bbox_layer._selected_bbox_keys == (
            set(selected_keys) if draw_boxes else set()
        )
        assert display_annotations.call_args.args[0] == (boxes if draw_boxes else [])
        assert preview.bbox_layer._box_border_width == settings.box_border_width
        assert preview.empty_state_layer.isHidden()
        displayed_frame = convert_image.call_args.args[0]
        expected_frame = original_frame.copy()
        if populated and blur_enabled and preview_blur_enabled:
            expected_frame = apply_masked_blur(expected_frame, boxes, settings.blur_strength)
        if populated and show_preview_mask:
            alpha_mask = compute_blur_alpha_mask(expected_frame.shape, boxes)
            expected_frame = overlay_alpha_mask(expected_frame, alpha_mask)
        np.testing.assert_array_equal(displayed_frame, expected_frame)
        expected_blur_calls = (
            populate_table.call_count if populated and blur_enabled and preview_blur_enabled else 0
        )
        assert blur.call_count == expected_blur_calls
        assert mask.call_count == (populate_table.call_count if populated and show_preview_mask else 0)
        assert {key: value for key, value in asdict(settings).items() if key != "draw_boxes"} == {
            key: value for key, value in original_settings.items() if key != "draw_boxes"
        }
        np.testing.assert_array_equal(frame, original_frame)
        logger.opt.assert_not_called()
