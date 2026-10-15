from __future__ import annotations

from unittest.mock import MagicMock

from app.domain import VideoDataLayer
from app.infrastructure.export.export_all_worker import ExportAllWorker


def test_export_all_falls_back_to_layer_a_when_configured_layer_b_is_empty(tmp_path):
    s_id = MagicMock()
    s_id.basename_without_extension = "sample"
    session = MagicMock()
    session.state.settings.tracking_source = VideoDataLayer.B.value
    session.state.settings.tracking_strategy = "hungarian"
    session.has_boxes_for_layer.side_effect = lambda layer: layer == VideoDataLayer.A
    session.get_layer_by_name.return_value = {}
    session.has_running_tracking_worker = False

    app = MagicMock()
    app.sm.get_session_by_id.return_value = session
    app.session_is_ready_for_export.return_value = True
    worker = ExportAllWorker(app, [s_id], str(tmp_path), "pre_", "_post")

    assert worker._process_session(s_id)

    app.start_tracking_worker.assert_called_once_with(
        s_id, "hungarian", VideoDataLayer.A
    )
    app.sync_tracking_cache.assert_called_once_with(s_id)
    app.export_session.assert_called_once()


def test_export_all_does_not_fall_back_when_layer_b_has_initialized_empty_frames(tmp_path):
    s_id = MagicMock()
    s_id.basename_without_extension = "sample"
    session = MagicMock()
    session.state.settings.tracking_source = VideoDataLayer.B.value
    session.state.settings.tracking_strategy = "hungarian"
    session.has_boxes_for_layer.side_effect = lambda layer: layer == VideoDataLayer.A
    session.get_layer_by_name.return_value = {4: []}
    session.has_running_tracking_worker = False

    app = MagicMock()
    app.sm.get_session_by_id.return_value = session
    app.session_is_ready_for_export.return_value = True
    worker = ExportAllWorker(app, [s_id], str(tmp_path), "", "")

    assert worker._process_session(s_id)

    app.start_tracking_worker.assert_called_once_with(
        s_id, "hungarian", VideoDataLayer.B
    )
